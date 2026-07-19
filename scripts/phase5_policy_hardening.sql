-- ============================================================
-- Phase 5: Policy Engine Hardening DDL
-- NOC IT AI v3.0
-- ============================================================

-- 1. Alter fleet_sites to support site_criticality
ALTER TABLE fleet_sites ADD COLUMN IF NOT EXISTS criticality TEXT DEFAULT 'MEDIUM';

-- Update initial sites with criticality
UPDATE fleet_sites SET criticality = 'HIGH' WHERE site_id = 'idm';
UPDATE fleet_sites SET criticality = 'MEDIUM' WHERE site_id = 'kantor_cabang';

-- 2. Policy Versioning Table
CREATE TABLE IF NOT EXISTS policy_versions (
    id SERIAL PRIMARY KEY,
    version INTEGER NOT NULL UNIQUE,
    rules_json JSONB NOT NULL,
    description TEXT,
    is_active BOOLEAN DEFAULT FALSE,
    created_by TEXT DEFAULT 'system',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_policy_versions_active ON policy_versions(is_active) WHERE is_active = TRUE;

-- 3. Policy Audit Trail Table
CREATE TABLE IF NOT EXISTS policy_audit_trail (
    id SERIAL PRIMARY KEY,
    incident_id INTEGER,
    policy_version INTEGER,
    input_context JSONB NOT NULL,
    matched_rule TEXT,
    effect TEXT NOT NULL,
    evaluated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_policy_audit_incident ON policy_audit_trail(incident_id);
CREATE INDEX IF NOT EXISTS idx_policy_audit_effect ON policy_audit_trail(effect);

-- 4. Rollback Policy Table
CREATE TABLE IF NOT EXISTS rollback_policies (
    id SERIAL PRIMARY KEY,
    action_type TEXT NOT NULL UNIQUE,
    max_rollback_attempts INTEGER DEFAULT 1,
    trigger_on_verification_failure BOOLEAN DEFAULT TRUE,
    trigger_on_trust_drop BOOLEAN DEFAULT TRUE,
    trust_threshold NUMERIC(5,2) DEFAULT 70.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Insert initial OPA policy rules into active rules if they do not exist
-- First let's clean up or update opa_policy_rules to enforce Phase 5 rules:
-- Severity=CRITICAL -> FORCE_HITL
-- confidence<0.85 -> REQUIRE_APPROVAL
-- trust_score<70 -> REQUIRE_APPROVAL
-- blast_radius>3 -> REQUIRE_APPROVAL
-- risk=LOW and confidence>0.92 -> AUTO_EXECUTE

DELETE FROM opa_policy_rules WHERE rule_name IN (
    'Phase 5: Force HITL on Critical Severity',
    'Phase 5: Require Approval on Low Confidence',
    'Phase 5: Require Approval on Low Trust Score',
    'Phase 5: Require Approval on High Blast Radius',
    'Phase 5: Auto Execute on Low Risk High Confidence'
);

INSERT INTO opa_policy_rules (rule_name, condition_expr, effect, priority) VALUES
('Phase 5: Force HITL on Critical Severity', 'severity == "CRITICAL"', 'FORCE_HITL', 100),
('Phase 5: Require Approval on Low Confidence', 'confidence < 0.85', 'REQUIRE_APPROVAL', 90),
('Phase 5: Require Approval on Low Trust Score', 'trust_score < 70', 'REQUIRE_APPROVAL', 80),
('Phase 5: Require Approval on High Blast Radius', 'blast_radius > 3', 'REQUIRE_APPROVAL', 70),
('Phase 5: Auto Execute on Low Risk High Confidence', 'risk_str == "LOW" and confidence > 0.92', 'AUTO_EXECUTE', 50)
ON CONFLICT DO NOTHING;

-- Seed initial policy version
INSERT INTO policy_versions (version, rules_json, description, is_active, created_by) VALUES
(1, '{
  "rules": [
    {"name": "Phase 5: Force HITL on Critical Severity", "condition": "severity == \"CRITICAL\"", "effect": "FORCE_HITL", "priority": 100},
    {"name": "Phase 5: Require Approval on Low Confidence", "condition": "confidence < 0.85", "effect": "REQUIRE_APPROVAL", "priority": 90},
    {"name": "Phase 5: Require Approval on Low Trust Score", "condition": "trust_score < 70", "effect": "REQUIRE_APPROVAL", "priority": 80},
    {"name": "Phase 5: Require Approval on High Blast Radius", "condition": "blast_radius > 3", "effect": "REQUIRE_APPROVAL", "priority": 70},
    {"name": "Phase 5: Auto Execute on Low Risk High Confidence", "condition": "risk_str == \"LOW\" and confidence > 0.92", "effect": "AUTO_EXECUTE", "priority": 50}
  ]
}', 'Initial Phase 5 hardening ruleset', TRUE, 'system')
ON CONFLICT (version) DO NOTHING;

-- Seed default rollback policies
INSERT INTO rollback_policies (action_type, max_rollback_attempts, trigger_on_verification_failure, trigger_on_trust_drop, trust_threshold) VALUES
('AUTO_MITIGATE', 1, TRUE, TRUE, 70.0)
ON CONFLICT (action_type) DO NOTHING;
