-- Sprint D: Multi-Agent Collaboration & Enterprise AI Orchestration

CREATE TABLE IF NOT EXISTS agent_registry (
    agent_id VARCHAR(100) PRIMARY KEY,
    agent_type VARCHAR(100),
    capabilities JSONB,
    skills JSONB,
    trust_score NUMERIC(5,2) DEFAULT 100.0,
    confidence NUMERIC(5,2) DEFAULT 100.0,
    version VARCHAR(50),
    status VARCHAR(50) DEFAULT 'Active', -- Active, Canary, Offline
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_health (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(100) REFERENCES agent_registry(agent_id),
    cpu_usage NUMERIC(5,2),
    ram_usage NUMERIC(5,2),
    queue_size INTEGER,
    latency_ms NUMERIC(10,2),
    crash_count INTEGER DEFAULT 0,
    heartbeat_status VARCHAR(50),
    checked_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_performance (
    id SERIAL PRIMARY KEY,
    agent_id VARCHAR(100) REFERENCES agent_registry(agent_id),
    accuracy NUMERIC(5,2),
    latency NUMERIC(10,2),
    success_rate NUMERIC(5,2),
    failure_rate NUMERIC(5,2),
    precision NUMERIC(5,2),
    recall NUMERIC(5,2),
    f1_score NUMERIC(5,2),
    recorded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS consensus_history (
    id SERIAL PRIMARY KEY,
    incident_id VARCHAR(100),
    majority_opinion JSONB,
    minority_opinion JSONB,
    confidence NUMERIC(5,2),
    has_conflict BOOLEAN,
    conflict_resolution_reason TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS agent_communication_audit (
    id SERIAL PRIMARY KEY,
    sender_agent_id VARCHAR(100),
    receiver_agent_id VARCHAR(100),
    topic VARCHAR(255),
    payload JSONB,
    latency_ms NUMERIC(10,2),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
