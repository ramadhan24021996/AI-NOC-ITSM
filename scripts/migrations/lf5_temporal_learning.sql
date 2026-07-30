CREATE TABLE IF NOT EXISTS temporal_registry (
    temporal_id VARCHAR(100) PRIMARY KEY,
    tenant_id VARCHAR(50),
    device_id VARCHAR(100) NOT NULL,
    timezone VARCHAR(50) DEFAULT 'UTC',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS temporal_calendar (
    calendar_id SERIAL PRIMARY KEY,
    temporal_id VARCHAR(100) REFERENCES temporal_registry(temporal_id),
    day_of_week VARCHAR(15),
    is_working_day BOOLEAN,
    is_holiday BOOLEAN,
    business_start_time TIME,
    business_end_time TIME,
    maintenance_start_time TIME,
    maintenance_end_time TIME
);

CREATE TABLE IF NOT EXISTS temporal_baseline (
    baseline_id SERIAL PRIMARY KEY,
    temporal_id VARCHAR(100) REFERENCES temporal_registry(temporal_id),
    peak_start_time TIME,
    peak_end_time TIME,
    confidence DOUBLE PRECISION,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS temporal_patterns (
    pattern_id SERIAL PRIMARY KEY,
    temporal_id VARCHAR(100) REFERENCES temporal_registry(temporal_id),
    pattern_type VARCHAR(50), -- WEEKLY_LOAD, MONTHLY_END, PATCH_TUESDAY
    description TEXT,
    confidence DOUBLE PRECISION,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS temporal_timeline (
    timeline_id SERIAL PRIMARY KEY,
    temporal_id VARCHAR(100) REFERENCES temporal_registry(temporal_id),
    sequence_order INTEGER,
    event_time TIMESTAMP,
    event_type VARCHAR(100),
    metric_value DOUBLE PRECISION,
    context TEXT
);

CREATE TABLE IF NOT EXISTS temporal_audit (
    audit_id SERIAL PRIMARY KEY,
    temporal_id VARCHAR(100) REFERENCES temporal_registry(temporal_id),
    event VARCHAR(100),
    reason TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
