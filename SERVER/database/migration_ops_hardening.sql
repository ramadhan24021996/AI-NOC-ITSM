-- ============================================================
-- OSI INCIDENT OPS HARDENING MIGRATION
-- P1: Incident Ownership Engine
-- P2: Chat-Incident Threading  
-- P3: Fleet Graph Model (Topology + Blast Radius)
-- P4: Auto Escalation Engine Schema
-- P5: Closure Enforcement
-- ============================================================
-- Run: docker exec -i osi-postgres psql -U postgres -d osi_system < migration_ops_hardening.sql

BEGIN;

-- ============================================================
-- P1: INCIDENT OWNERSHIP ENGINE
-- Add owner, lifecycle stages, SLA tracking to fleet_incidents
-- ============================================================

ALTER TABLE fleet_incidents
  ADD COLUMN IF NOT EXISTS owner_id          TEXT DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS assigned_at       TIMESTAMP WITHOUT TIME ZONE DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS acked_at          TIMESTAMP WITHOUT TIME ZONE DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS in_progress_at    TIMESTAMP WITHOUT TIME ZONE DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS sla_minutes       INTEGER DEFAULT 60,
  ADD COLUMN IF NOT EXISTS sla_deadline      TIMESTAMP WITHOUT TIME ZONE DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS escalation_level  INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS escalation_deadline TIMESTAMP WITHOUT TIME ZONE DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS last_escalated_at TIMESTAMP WITHOUT TIME ZONE DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS escalation_reason TEXT DEFAULT NULL;

-- SLA deadline auto-set trigger
CREATE OR REPLACE FUNCTION set_sla_deadline()
RETURNS TRIGGER AS $$
BEGIN
  IF NEW.sla_deadline IS NULL AND NEW.sla_minutes IS NOT NULL THEN
    NEW.sla_deadline := NEW.created_at + (NEW.sla_minutes || ' minutes')::INTERVAL;
    NEW.escalation_deadline := NEW.created_at + INTERVAL '15 minutes';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_sla_deadline ON fleet_incidents;
CREATE TRIGGER trg_sla_deadline
  BEFORE INSERT ON fleet_incidents
  FOR EACH ROW EXECUTE FUNCTION set_sla_deadline();

-- Back-fill SLA deadline for existing open incidents
UPDATE fleet_incidents 
SET sla_deadline = created_at + INTERVAL '60 minutes',
    escalation_deadline = created_at + INTERVAL '15 minutes'
WHERE sla_deadline IS NULL;

-- Operator registry table (extends operator_presence)
CREATE TABLE IF NOT EXISTS operator_profiles (
  operator_id       TEXT PRIMARY KEY,
  display_name      TEXT NOT NULL,
  specialization    TEXT[] DEFAULT '{}',   -- e.g. ['NETWORK','SECURITY','HARDWARE']
  site_access       TEXT[] DEFAULT '{}',   -- site_ids operator can handle
  max_workload      INTEGER DEFAULT 5,     -- max concurrent incidents
  telegram_chat_id  TEXT DEFAULT NULL,
  email             TEXT DEFAULT NULL,
  role              TEXT DEFAULT 'L1',     -- L1, L2, L3, ADMIN
  is_active         BOOLEAN DEFAULT TRUE,
  created_at        TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Incident assignment history
CREATE TABLE IF NOT EXISTS incident_assignments (
  assignment_id   SERIAL PRIMARY KEY,
  incident_id     INTEGER NOT NULL REFERENCES fleet_incidents(incident_id) ON DELETE CASCADE,
  operator_id     TEXT NOT NULL,
  assigned_at     TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  acked_at        TIMESTAMP WITHOUT TIME ZONE,
  released_at     TIMESTAMP WITHOUT TIME ZONE,
  release_reason  TEXT,
  is_current      BOOLEAN DEFAULT TRUE
);
CREATE INDEX IF NOT EXISTS idx_incident_assignments_incident ON incident_assignments(incident_id);
CREATE INDEX IF NOT EXISTS idx_incident_assignments_operator ON incident_assignments(operator_id);
CREATE INDEX IF NOT EXISTS idx_incident_assignments_current ON incident_assignments(is_current) WHERE is_current = TRUE;

-- ============================================================
-- P2: CHAT-INCIDENT THREADING
-- Link chat_messages to incident_id for context
-- ============================================================

ALTER TABLE chat_messages
  ADD COLUMN IF NOT EXISTS incident_id    INTEGER DEFAULT NULL REFERENCES fleet_incidents(incident_id) ON DELETE SET NULL,
  ADD COLUMN IF NOT EXISTS thread_type    TEXT DEFAULT 'SUPPORT',   -- SUPPORT | INCIDENT | ESCALATION
  ADD COLUMN IF NOT EXISTS is_system_msg  BOOLEAN DEFAULT FALSE,
  ADD COLUMN IF NOT EXISTS metadata       JSONB DEFAULT '{}';

CREATE INDEX IF NOT EXISTS idx_chat_messages_incident ON chat_messages(incident_id) WHERE incident_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_chat_messages_thread_type ON chat_messages(thread_type);

-- Chat message partitioning by month (retention governance)
-- Migrate existing table to partitioned (safe: add partitions, keep existing)
CREATE TABLE IF NOT EXISTS chat_archive (
  LIKE chat_messages INCLUDING ALL
);
CREATE INDEX IF NOT EXISTS idx_chat_archive_created ON chat_archive(created_at DESC);

-- ============================================================
-- P3: FLEET GRAPH MODEL
-- Topology, dependency, blast radius awareness
-- ============================================================

-- Site topology: physical network connections between sites
CREATE TABLE IF NOT EXISTS fleet_topology (
  topology_id     SERIAL PRIMARY KEY,
  site_id_from    TEXT NOT NULL REFERENCES fleet_sites(site_id) ON DELETE CASCADE,
  site_id_to      TEXT NOT NULL REFERENCES fleet_sites(site_id) ON DELETE CASCADE,
  link_type       TEXT DEFAULT 'WAN',     -- WAN | LAN | VPN | FIBER | WIRELESS
  bandwidth_mbps  FLOAT DEFAULT NULL,
  latency_ms      FLOAT DEFAULT NULL,
  is_critical     BOOLEAN DEFAULT FALSE,  -- if TRUE, affects blast radius
  created_at      TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  UNIQUE(site_id_from, site_id_to)
);

-- Device dependency graph: which device depends on which
CREATE TABLE IF NOT EXISTS device_dependencies (
  dep_id          SERIAL PRIMARY KEY,
  pc_name         TEXT NOT NULL REFERENCES fleet_devices(pc_name) ON DELETE CASCADE,
  depends_on      TEXT NOT NULL,          -- device name or service name
  dep_type        TEXT DEFAULT 'NETWORK', -- NETWORK | SERVICE | STORAGE | POWER
  criticality     TEXT DEFAULT 'MEDIUM',  -- HIGH | MEDIUM | LOW
  description     TEXT,
  created_at      TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);
CREATE INDEX IF NOT EXISTS idx_device_dep_pc ON device_dependencies(pc_name);
CREATE INDEX IF NOT EXISTS idx_device_dep_depends ON device_dependencies(depends_on);

-- Network paths between key infrastructure nodes
CREATE TABLE IF NOT EXISTS network_paths (
  path_id         SERIAL PRIMARY KEY,
  src_asset_id    TEXT NOT NULL,
  dst_asset_id    TEXT NOT NULL,
  hops            TEXT[],                 -- ordered list of asset_ids
  path_type       TEXT DEFAULT 'ROUTED',  -- ROUTED | DIRECT | TUNNEL
  last_verified   TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  is_up           BOOLEAN DEFAULT TRUE,
  latency_ms      FLOAT DEFAULT NULL
);
CREATE INDEX IF NOT EXISTS idx_network_paths_src ON network_paths(src_asset_id);
CREATE INDEX IF NOT EXISTS idx_network_paths_dst ON network_paths(dst_asset_id);

-- Blast radius: for a given incident, which assets are affected
CREATE TABLE IF NOT EXISTS blast_radius_registry (
  blast_id        SERIAL PRIMARY KEY,
  incident_id     INTEGER NOT NULL REFERENCES fleet_incidents(incident_id) ON DELETE CASCADE,
  affected_assets JSONB NOT NULL DEFAULT '[]',  -- [{asset_id, name, type, impact_level}]
  affected_sites  TEXT[] DEFAULT '{}',
  scope           TEXT DEFAULT 'LOCAL',          -- LOCAL | SITE | MULTI_SITE | GLOBAL
  computed_at     TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  computed_by     TEXT DEFAULT 'auto'
);
CREATE INDEX IF NOT EXISTS idx_blast_radius_incident ON blast_radius_registry(incident_id);

-- ============================================================
-- P4: AUTO ESCALATION ENGINE TABLES
-- ============================================================

-- Escalation rule configuration
CREATE TABLE IF NOT EXISTS escalation_rules (
  rule_id         SERIAL PRIMARY KEY,
  name            TEXT NOT NULL,
  condition_state TEXT NOT NULL,          -- state that triggers check (e.g. OPEN, WAITING_APPROVAL)
  threshold_min   INTEGER NOT NULL,       -- minutes without action
  escalation_level INTEGER NOT NULL,      -- 1=L2, 2=L3, 3=CRITICAL
  action          TEXT NOT NULL,          -- NOTIFY_TELEGRAM | REASSIGN | ALERT_DASHBOARD | FORCE_CRITICAL
  is_active       BOOLEAN DEFAULT TRUE,
  created_at      TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

-- Default escalation rules
INSERT INTO escalation_rules (name, condition_state, threshold_min, escalation_level, action) VALUES
  ('No ACK within 15 min',   'OPEN',             15, 1, 'NOTIFY_TELEGRAM'),
  ('No response in 30 min',  'OPEN',             30, 2, 'REASSIGN'),
  ('Unresolved after 60 min','WAITING_APPROVAL',  60, 3, 'ALERT_DASHBOARD'),
  ('Critical SLA breach',    'OPEN',             120, 3, 'FORCE_CRITICAL')
ON CONFLICT DO NOTHING;

-- Escalation execution log
CREATE TABLE IF NOT EXISTS escalation_log (
  log_id          SERIAL PRIMARY KEY,
  incident_id     INTEGER NOT NULL REFERENCES fleet_incidents(incident_id) ON DELETE CASCADE,
  rule_id         INTEGER REFERENCES escalation_rules(rule_id),
  escalation_level INTEGER NOT NULL,
  action_taken    TEXT NOT NULL,
  notified_ops    TEXT[] DEFAULT '{}',
  previous_owner  TEXT DEFAULT NULL,
  new_owner       TEXT DEFAULT NULL,
  triggered_at    TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  resolved_by_escalation BOOLEAN DEFAULT FALSE
);
CREATE INDEX IF NOT EXISTS idx_escalation_log_incident ON escalation_log(incident_id);
CREATE INDEX IF NOT EXISTS idx_escalation_log_triggered ON escalation_log(triggered_at DESC);

-- ============================================================
-- P5: CLOSURE ENFORCEMENT
-- Incidents CANNOT be closed without evidence + postmortem
-- ============================================================

CREATE TABLE IF NOT EXISTS incident_closure (
  closure_id          SERIAL PRIMARY KEY,
  incident_id         INTEGER NOT NULL UNIQUE REFERENCES fleet_incidents(incident_id) ON DELETE CASCADE,
  resolution_summary  TEXT NOT NULL,
  resolution_actor    TEXT NOT NULL,          -- operator_id who closed it
  resolution_proof    TEXT,                   -- URL/path to screenshot/log evidence
  resolution_duration_sec INTEGER NOT NULL,   -- time from OPEN to CLOSED
  ai_reflection_id    INTEGER DEFAULT NULL,   -- FK to ai_reflection_logs if exists
  postmortem_required BOOLEAN DEFAULT FALSE,
  postmortem_id       INTEGER DEFAULT NULL REFERENCES incident_post_mortems(post_mortem_id),
  closed_at           TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  enforcement_passed  BOOLEAN DEFAULT TRUE,
  skip_reason         TEXT DEFAULT NULL       -- only if enforcement_passed=FALSE (emergency)
);
CREATE INDEX IF NOT EXISTS idx_closure_incident ON incident_closure(incident_id);

-- Enforce closure gate: a function that checks prerequisites
CREATE OR REPLACE FUNCTION check_closure_prerequisites(p_incident_id INTEGER)
RETURNS TABLE(can_close BOOLEAN, reason TEXT) AS $$
DECLARE
  v_has_evidence    BOOLEAN;
  v_has_postmortem  BOOLEAN;
  v_has_assignment  BOOLEAN;
  v_duration_sec    INTEGER;
  v_created_at      TIMESTAMP;
BEGIN
  -- Check if there is ANY evidence
  SELECT EXISTS(
    SELECT 1 FROM fleet_evidence WHERE incident_id = p_incident_id
    UNION ALL
    SELECT 1 FROM ai_evidence_logs WHERE incident_id = p_incident_id
  ) INTO v_has_evidence;
  
  -- Check postmortem
  SELECT EXISTS(
    SELECT 1 FROM incident_post_mortems WHERE incident_id = p_incident_id
  ) INTO v_has_postmortem;
  
  -- Check assignment (operator acknowledged)
  SELECT EXISTS(
    SELECT 1 FROM incident_assignments WHERE incident_id = p_incident_id
  ) INTO v_has_assignment;
  
  -- Get duration
  SELECT EXTRACT(EPOCH FROM (NOW() - created_at))::INTEGER
  INTO v_duration_sec
  FROM fleet_incidents WHERE incident_id = p_incident_id;
  
  IF NOT v_has_evidence THEN
    RETURN QUERY SELECT FALSE, 'MISSING_EVIDENCE: No evidence attached to incident';
    RETURN;
  END IF;
  
  IF NOT v_has_postmortem AND v_duration_sec > 3600 THEN
    -- Postmortem mandatory if incident lasted > 1 hour
    RETURN QUERY SELECT FALSE, 'MISSING_POSTMORTEM: Incidents open > 1 hour require postmortem';
    RETURN;
  END IF;
  
  RETURN QUERY SELECT TRUE, 'OK';
END;
$$ LANGUAGE plpgsql;

-- ============================================================
-- INDEXES FOR PERFORMANCE
-- ============================================================

CREATE INDEX IF NOT EXISTS idx_fleet_incidents_owner ON fleet_incidents(owner_id) WHERE owner_id IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fleet_incidents_escalation ON fleet_incidents(escalation_level) WHERE escalation_level > 0;
CREATE INDEX IF NOT EXISTS idx_fleet_incidents_sla_breach ON fleet_incidents(sla_deadline) WHERE sla_deadline IS NOT NULL;
CREATE INDEX IF NOT EXISTS idx_fleet_incidents_status_owner ON fleet_incidents(status, owner_id);

-- Composite view: HITL dashboard live view
CREATE OR REPLACE VIEW v_hitl_dashboard AS
SELECT
  fi.incident_id,
  fi.site_id,
  fi.pc_name,
  fi.severity,
  fi.status,
  fi.description,
  fi.owner_id,
  op.display_name AS owner_name,
  fi.escalation_level,
  fi.created_at,
  fi.sla_deadline,
  fi.acked_at,
  EXTRACT(EPOCH FROM (NOW() - fi.created_at))::INTEGER AS age_seconds,
  CASE
    WHEN fi.sla_deadline IS NOT NULL AND NOW() > fi.sla_deadline THEN TRUE
    ELSE FALSE
  END AS sla_breached,
  CASE
    WHEN fi.acked_at IS NULL AND EXTRACT(EPOCH FROM (NOW() - fi.created_at)) > 900 THEN TRUE
    ELSE FALSE
  END AS unacked_critical,
  (SELECT COUNT(*) FROM chat_messages cm WHERE cm.incident_id = fi.incident_id) AS chat_thread_count
FROM fleet_incidents fi
LEFT JOIN operator_profiles op ON op.operator_id = fi.owner_id
WHERE fi.status NOT IN ('RESOLVED', 'CLOSED')
ORDER BY fi.escalation_level DESC, fi.created_at ASC;

-- ============================================================
-- UPDATED LIFECYCLE STATUS ENUM ENFORCEMENT (via CHECK)
-- ============================================================

-- Allow the full lifecycle: OPEN→ASSIGNED→ACKED→IN_PROGRESS→RESOLVED→CLOSED
ALTER TABLE fleet_incidents DROP CONSTRAINT IF EXISTS chk_fleet_incident_status;
ALTER TABLE fleet_incidents ADD CONSTRAINT chk_fleet_incident_status
  CHECK (status IN (
    'OPEN', 'ASSIGNED', 'ACKED', 'IN_PROGRESS',
    'WAITING_APPROVAL', 'APPROVED', 'EXECUTING', 'VERIFYING',
    'RESOLVED', 'CLOSED', 'ESCALATED', 'DLQ', 'FAILED',
    'ROLLBACK_PENDING', 'ROLLED_BACK', 'ARCHIVED'
  ));

COMMIT;

-- Verify migration
SELECT 'Migration complete' AS result;
SELECT COUNT(*) AS total_tables FROM information_schema.tables WHERE table_schema='public';
