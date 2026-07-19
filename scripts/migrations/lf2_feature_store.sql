CREATE TABLE IF NOT EXISTS feature_registry (
    feature_id VARCHAR(100) PRIMARY KEY,
    feature_name VARCHAR(150) NOT NULL,
    category VARCHAR(100) NOT NULL,
    description TEXT,
    tenant_id VARCHAR(50) NOT NULL,
    source VARCHAR(100) NOT NULL,
    collector VARCHAR(100),
    created_by VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    current_version VARCHAR(50) NOT NULL,
    schema_version INTEGER NOT NULL,
    status VARCHAR(50) NOT NULL,
    tags JSONB,
    checksum VARCHAR(256) NOT NULL
);

CREATE TABLE IF NOT EXISTS feature_versions (
    version_id SERIAL PRIMARY KEY,
    feature_id VARCHAR(100) REFERENCES feature_registry(feature_id),
    version VARCHAR(50) NOT NULL,
    feature_value JSONB NOT NULL,
    unit VARCHAR(50),
    confidence DOUBLE PRECISION,
    evidence TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    checksum VARCHAR(256) NOT NULL,
    UNIQUE(feature_id, version)
);

CREATE TABLE IF NOT EXISTS feature_lineage (
    lineage_id SERIAL PRIMARY KEY,
    feature_id VARCHAR(100) REFERENCES feature_registry(feature_id),
    version VARCHAR(50) NOT NULL,
    telemetry_id VARCHAR(100),
    collector_id VARCHAR(100),
    normalizer_version VARCHAR(50),
    extractor_version VARCHAR(50),
    validator_version VARCHAR(50),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feature_quality (
    quality_id SERIAL PRIMARY KEY,
    feature_id VARCHAR(100) REFERENCES feature_registry(feature_id),
    version VARCHAR(50) NOT NULL,
    completeness DOUBLE PRECISION,
    consistency DOUBLE PRECISION,
    freshness DOUBLE PRECISION,
    confidence_score DOUBLE PRECISION,
    evidence_score DOUBLE PRECISION,
    reuse_score DOUBLE PRECISION,
    calculated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS feature_audit (
    audit_id SERIAL PRIMARY KEY,
    correlation_id VARCHAR(100),
    feature_id VARCHAR(100),
    tenant_id VARCHAR(50),
    user_service VARCHAR(100),
    event VARCHAR(100),
    reason TEXT,
    version VARCHAR(50),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
