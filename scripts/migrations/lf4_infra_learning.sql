CREATE TABLE IF NOT EXISTS infra_registry (
    device_id VARCHAR(100) PRIMARY KEY,
    hostname VARCHAR(150),
    vendor VARCHAR(50),
    role VARCHAR(50),
    first_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS infra_baseline (
    baseline_id SERIAL PRIMARY KEY,
    device_id VARCHAR(100) REFERENCES infra_registry(device_id),
    metric_name VARCHAR(50), -- CPU, RAM, Disk, Latency
    p95_value DOUBLE PRECISION,
    p99_value DOUBLE PRECISION,
    avg_value DOUBLE PRECISION,
    std_dev DOUBLE PRECISION,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(device_id, metric_name)
);

CREATE TABLE IF NOT EXISTS infra_patterns (
    pattern_id SERIAL PRIMARY KEY,
    device_id VARCHAR(100) REFERENCES infra_registry(device_id),
    pattern_type VARCHAR(50), -- TREND, SEASONALITY, CORRELATION
    description TEXT,
    confidence DOUBLE PRECISION,
    detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS infra_degradation_history (
    history_id SERIAL PRIMARY KEY,
    device_id VARCHAR(100) REFERENCES infra_registry(device_id),
    metric_name VARCHAR(50),
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    severity VARCHAR(20),
    peak_value DOUBLE PRECISION
);

CREATE TABLE IF NOT EXISTS infra_audit (
    audit_id SERIAL PRIMARY KEY,
    device_id VARCHAR(100),
    event VARCHAR(100),
    details TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
