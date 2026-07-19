CREATE TABLE IF NOT EXISTS remediation_registry (
    remediation_id VARCHAR(100) PRIMARY KEY,
    incident_id VARCHAR(100) NOT NULL,
    tenant_id VARCHAR(50) NOT NULL,
    device_id VARCHAR(100) NOT NULL,
    action_name VARCHAR(150) NOT NULL,
    executor VARCHAR(100) NOT NULL,
    execution_time TIMESTAMP,
    rollback_available BOOLEAN DEFAULT FALSE,
    execution_status VARCHAR(50) NOT NULL,
    confidence_before DOUBLE PRECISION,
    confidence_after DOUBLE PRECISION,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS remediation_results (
    result_id SERIAL PRIMARY KEY,
    remediation_id VARCHAR(100) REFERENCES remediation_registry(remediation_id),
    resolution_time_ms INTEGER,
    rollback_needed BOOLEAN DEFAULT FALSE,
    service_restored BOOLEAN DEFAULT FALSE,
    manual_intervention BOOLEAN DEFAULT FALSE,
    error_count INTEGER DEFAULT 0,
    downtime_ms INTEGER,
    sla_impact BOOLEAN DEFAULT FALSE,
    failure_type VARCHAR(100),
    failure_cause TEXT,
    evidence TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS remediation_scores (
    score_id SERIAL PRIMARY KEY,
    remediation_id VARCHAR(100) REFERENCES remediation_registry(remediation_id),
    action_name VARCHAR(150) NOT NULL,
    success_score DOUBLE PRECISION NOT NULL,
    confidence_delta DOUBLE PRECISION,
    rank_value INTEGER,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS remediation_feedback (
    feedback_id SERIAL PRIMARY KEY,
    remediation_id VARCHAR(100) REFERENCES remediation_registry(remediation_id),
    engineer_id VARCHAR(100) NOT NULL,
    action_taken VARCHAR(50) NOT NULL, -- APPROVE, REJECT, MODIFY, OVERRIDE
    comments TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS remediation_audit (
    audit_id SERIAL PRIMARY KEY,
    remediation_id VARCHAR(100) REFERENCES remediation_registry(remediation_id),
    event VARCHAR(100) NOT NULL,
    reason TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
