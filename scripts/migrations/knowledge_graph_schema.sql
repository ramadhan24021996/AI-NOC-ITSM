-- Migration: Knowledge Graph Schema Expansion
-- Production Enterprise AIOps Knowledge Graph Tables

CREATE TABLE IF NOT EXISTS knowledge_graph_nodes (
    node_id VARCHAR(255) PRIMARY KEY,
    node_type VARCHAR(64) NOT NULL DEFAULT 'Unknown',
    criticality INT NOT NULL DEFAULT 1,
    status VARCHAR(32) NOT NULL DEFAULT 'HEALTHY',
    site_id VARCHAR(128) DEFAULT 'GLOBAL',
    ip_address VARCHAR(64),
    properties JSONB DEFAULT '{}'::jsonb,
    last_status_change TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    last_incident TIMESTAMPTZ,
    last_recovery TIMESTAMPTZ,
    last_metric_update TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

-- Ensure missing columns exist if table was previously created
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS node_type VARCHAR(64) NOT NULL DEFAULT 'Unknown';
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS criticality INT NOT NULL DEFAULT 1;
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS status VARCHAR(32) NOT NULL DEFAULT 'HEALTHY';
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS site_id VARCHAR(128) DEFAULT 'GLOBAL';
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS ip_address VARCHAR(64);
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS properties JSONB DEFAULT '{}'::jsonb;
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS last_status_change TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS last_incident TIMESTAMPTZ;
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS last_recovery TIMESTAMPTZ;
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS last_metric_update TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE knowledge_graph_nodes ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_kg_nodes_type ON knowledge_graph_nodes(node_type);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_site ON knowledge_graph_nodes(site_id);
CREATE INDEX IF NOT EXISTS idx_kg_nodes_status ON knowledge_graph_nodes(status);

CREATE TABLE IF NOT EXISTS knowledge_graph_edges (
    id BIGSERIAL PRIMARY KEY,
    source_id VARCHAR(255) NOT NULL,
    target_id VARCHAR(255) NOT NULL,
    relationship VARCHAR(64) NOT NULL DEFAULT 'DEPENDS_ON',
    confidence FLOAT NOT NULL DEFAULT 1.0,
    weight FLOAT NOT NULL DEFAULT 1.0,
    source_engine VARCHAR(64) DEFAULT 'CMDB',
    properties JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

ALTER TABLE knowledge_graph_edges ADD COLUMN IF NOT EXISTS relationship VARCHAR(64) NOT NULL DEFAULT 'DEPENDS_ON';
ALTER TABLE knowledge_graph_edges ADD COLUMN IF NOT EXISTS confidence FLOAT NOT NULL DEFAULT 1.0;
ALTER TABLE knowledge_graph_edges ADD COLUMN IF NOT EXISTS weight FLOAT NOT NULL DEFAULT 1.0;
ALTER TABLE knowledge_graph_edges ADD COLUMN IF NOT EXISTS source_engine VARCHAR(64) DEFAULT 'CMDB';
ALTER TABLE knowledge_graph_edges ADD COLUMN IF NOT EXISTS properties JSONB DEFAULT '{}'::jsonb;
ALTER TABLE knowledge_graph_edges ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;
ALTER TABLE knowledge_graph_edges ADD COLUMN IF NOT EXISTS updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP;

CREATE INDEX IF NOT EXISTS idx_kg_edges_src ON knowledge_graph_edges(source_id);
CREATE INDEX IF NOT EXISTS idx_kg_edges_tgt ON knowledge_graph_edges(target_id);
CREATE INDEX IF NOT EXISTS idx_kg_edges_rel ON knowledge_graph_edges(relationship);

CREATE TABLE IF NOT EXISTS knowledge_graph_history (
    version_id BIGSERIAL PRIMARY KEY,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    nodes_count INT NOT NULL DEFAULT 0,
    edges_count INT NOT NULL DEFAULT 0,
    disconnected_nodes INT NOT NULL DEFAULT 0,
    coverage_score FLOAT NOT NULL DEFAULT 0.0,
    change_summary JSONB DEFAULT '{}'::jsonb
);

CREATE TABLE IF NOT EXISTS knowledge_graph_weights (
    id SERIAL PRIMARY KEY,
    weight_key VARCHAR(128) UNIQUE NOT NULL,
    weight_value FLOAT NOT NULL,
    description TEXT,
    updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS knowledge_graph_feedback (
    id BIGSERIAL PRIMARY KEY,
    incident_id VARCHAR(255) NOT NULL,
    candidate_node_id VARCHAR(255) NOT NULL,
    feedback_type VARCHAR(64) NOT NULL,
    reviewer VARCHAR(128) DEFAULT 'OPERATOR',
    score_delta FLOAT DEFAULT 0.0,
    notes TEXT,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kg_fb_inc ON knowledge_graph_feedback(incident_id);
CREATE INDEX IF NOT EXISTS idx_kg_fb_node ON knowledge_graph_feedback(candidate_node_id);

CREATE TABLE IF NOT EXISTS knowledge_graph_evidence (
    id BIGSERIAL PRIMARY KEY,
    rca_trace_id VARCHAR(128) NOT NULL,
    candidate_node_id VARCHAR(255) NOT NULL,
    source_type VARCHAR(64) NOT NULL,
    evidence_text TEXT NOT NULL,
    confidence FLOAT NOT NULL DEFAULT 0.8,
    timestamp TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP,
    metadata JSONB DEFAULT '{}'::jsonb
);

CREATE INDEX IF NOT EXISTS idx_kg_ev_trace ON knowledge_graph_evidence(rca_trace_id);

CREATE TABLE IF NOT EXISTS knowledge_graph_predictions (
    id BIGSERIAL PRIMARY KEY,
    trace_id VARCHAR(128) NOT NULL,
    symptom_node_id VARCHAR(255) NOT NULL,
    predicted_root_cause_id VARCHAR(255) NOT NULL,
    score FLOAT NOT NULL,
    confidence FLOAT NOT NULL,
    counterfactual_valid BOOLEAN DEFAULT TRUE,
    blast_radius_json JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_kg_pred_trace ON knowledge_graph_predictions(trace_id);
