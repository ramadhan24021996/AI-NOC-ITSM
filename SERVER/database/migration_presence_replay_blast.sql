-- ============================================================
-- OSI INCIDENT OPS SYSTEM INTEGRATION MIGRATION
-- P6: Operator Presence Engine Fields
-- P8: Blast Radius Registry Updates
-- P9: Replay Simulation Engine Table
-- ============================================================

BEGIN;

-- P6: Update operator_presence table with new tracking fields
ALTER TABLE operator_presence
  ADD COLUMN IF NOT EXISTS heartbeat_at      TIMESTAMP WITHOUT TIME ZONE DEFAULT CURRENT_TIMESTAMP,
  ADD COLUMN IF NOT EXISTS active_incidents   INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS max_capacity       INTEGER DEFAULT 5,
  ADD COLUMN IF NOT EXISTS current_load       INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS current_site       TEXT DEFAULT 'global',
  ADD COLUMN IF NOT EXISTS current_shift      TEXT DEFAULT NULL,
  ADD COLUMN IF NOT EXISTS specialization     TEXT[] DEFAULT '{}',
  ADD COLUMN IF NOT EXISTS availability_score FLOAT DEFAULT 0.0;

-- Ensure operator_presence has typing_to
ALTER TABLE operator_presence
  ADD COLUMN IF NOT EXISTS typing_to TEXT DEFAULT '';

-- P8: Update blast_radius_registry with process columns if missing
ALTER TABLE blast_radius_registry
  ADD COLUMN IF NOT EXISTS root_device         TEXT,
  ADD COLUMN IF NOT EXISTS severity_multiplier FLOAT DEFAULT 1.0,
  ADD COLUMN IF NOT EXISTS dependency_depth   INTEGER DEFAULT 0,
  ADD COLUMN IF NOT EXISTS critical_paths      JSONB DEFAULT '[]',
  ADD COLUMN IF NOT EXISTS blast_score         FLOAT DEFAULT 0.0;

-- P9: Replay Simulation Engine Sessions Table
CREATE TABLE IF NOT EXISTS replay_sessions (
  replay_id       SERIAL PRIMARY KEY,
  incident_id     INTEGER NOT NULL,
  mode            TEXT NOT NULL, -- FORENSIC | TRAINING | SIMULATION | AI_REFLECTION
  started_at      TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW(),
  completed_at    TIMESTAMP WITHOUT TIME ZONE,
  replay_result   JSONB DEFAULT '{}',
  anomaly_found   BOOLEAN DEFAULT FALSE,
  lessons_learned TEXT,
  created_at      TIMESTAMP WITHOUT TIME ZONE DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_replay_sessions_incident ON replay_sessions(incident_id);

COMMIT;
