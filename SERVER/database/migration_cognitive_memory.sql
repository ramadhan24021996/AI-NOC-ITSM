-- Sprint C: Cognitive Memory & Knowledge Evolution

CREATE TABLE IF NOT EXISTS incident_memory (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(100) UNIQUE NOT NULL,
    root_cause TEXT,
    evidence JSONB,
    action TEXT,
    verification JSONB,
    rollback JSONB,
    engineer_decision VARCHAR(100),
    final_outcome VARCHAR(100),
    confidence NUMERIC(5,2),
    trust_score NUMERIC(5,2),
    business_impact VARCHAR(100),
    learning_score NUMERIC(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS episodic_memory (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(100) NOT NULL REFERENCES incident_memory(incident_id),
    event_time TIMESTAMP NOT NULL,
    description TEXT,
    telemetry_snapshot JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS semantic_memory (
    id SERIAL PRIMARY KEY,
    knowledge_id VARCHAR(100) UNIQUE NOT NULL,
    knowledge_type VARCHAR(50), -- Best Practice, Knowledge, SOP, Playbook, Vendor Recommendation, Known Issue, Historical Solution
    content JSONB,
    confidence NUMERIC(5,2) DEFAULT 100.0,
    support_count INTEGER DEFAULT 0,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    last_used TIMESTAMP,
    last_verified TIMESTAMP,
    decay_score NUMERIC(5,2) DEFAULT 0.0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS procedural_memory (
    id SERIAL PRIMARY KEY,
    procedure_id VARCHAR(100) UNIQUE NOT NULL,
    action_type VARCHAR(100) NOT NULL, -- Restart, Rollback, Verification, Maintenance, Recovery, Diagnosis
    steps JSONB,
    skill_accuracy NUMERIC(5,2),
    skill_success INTEGER DEFAULT 0,
    skill_failure INTEGER DEFAULT 0,
    average_runtime NUMERIC(10,2),
    average_verification NUMERIC(10,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS playbook_history (
    id SERIAL PRIMARY KEY,
    playbook_id VARCHAR(100) NOT NULL,
    recovery_time NUMERIC(10,2),
    success_rate NUMERIC(5,2),
    rollback_rate NUMERIC(5,2),
    human_override INTEGER DEFAULT 0,
    business_impact VARCHAR(100),
    playbook_score NUMERIC(5,2),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feedback_history (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(100) NOT NULL,
    engineer_id VARCHAR(100) NOT NULL,
    action VARCHAR(50), -- Approve, Reject, Modify, Cancel, Override
    details JSONB,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_proposal (
    id SERIAL PRIMARY KEY,
    proposal_id VARCHAR(100) UNIQUE NOT NULL,
    proposal_type VARCHAR(50), -- Knowledge, Playbook, Rule, Skill, RCA
    reason TEXT,
    expected_benefit TEXT,
    risk TEXT,
    evidence JSONB,
    status VARCHAR(50) DEFAULT 'Pending Review', -- Pending Review, Approved, Staging, Canary, Production
    who_created VARCHAR(100),
    approval_signature VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS audit_trail (
    id SERIAL PRIMARY KEY,
    who VARCHAR(100),
    when_timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    why TEXT,
    evidence JSONB,
    before_state JSONB,
    after_state JSONB,
    approval VARCHAR(100),
    signature VARCHAR(255)
);
