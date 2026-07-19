-- Phase 3: Knowledge Freshness & Provenance
ALTER TABLE knowledge_vectors 
ADD COLUMN IF NOT EXISTS status          VARCHAR(20) DEFAULT 'GOLDEN',
ADD COLUMN IF NOT EXISTS last_validated  TIMESTAMP  DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS usage_count     INTEGER    DEFAULT 0,
ADD COLUMN IF NOT EXISTS success_count   INTEGER    DEFAULT 0,
ADD COLUMN IF NOT EXISTS failure_count   INTEGER    DEFAULT 0,
ADD COLUMN IF NOT EXISTS freshness_score FLOAT      DEFAULT 1.0,
ADD COLUMN IF NOT EXISTS source_doc      TEXT,
ADD COLUMN IF NOT EXISTS source_version  VARCHAR(50),
ADD COLUMN IF NOT EXISTS telemetry_version INTEGER DEFAULT 1;

CREATE TABLE IF NOT EXISTS knowledge_provenance (
    id              SERIAL PRIMARY KEY,
    vector_id       INTEGER REFERENCES knowledge_vectors(id),
    source_type     VARCHAR(50), 
    source_url      TEXT,
    doc_version     VARCHAR(50),
    ingested_by     VARCHAR(100),
    approved_by     VARCHAR(100),
    status          VARCHAR(20) DEFAULT 'DRAFT', 
    created_at      TIMESTAMP DEFAULT NOW(),
    approved_at     TIMESTAMP
);

-- Phase 4: Goal Engine
CREATE TABLE IF NOT EXISTS ai_goals (
    id            SERIAL PRIMARY KEY,
    goal_name     VARCHAR(100) NOT NULL,
    target_metric VARCHAR(100),  
    target_value  FLOAT,
    current_value FLOAT,
    priority      INTEGER DEFAULT 5,
    is_active     BOOLEAN DEFAULT TRUE,
    updated_at    TIMESTAMP DEFAULT NOW()
);

INSERT INTO ai_goals (goal_name, target_metric, target_value, priority)
SELECT 'High Availability', 'uptime_pct', 99.9, 1
WHERE NOT EXISTS (SELECT 1 FROM ai_goals WHERE goal_name = 'High Availability');

INSERT INTO ai_goals (goal_name, target_metric, target_value, priority)
SELECT 'MTTR Reduction', 'mttr_minutes', 30, 2
WHERE NOT EXISTS (SELECT 1 FROM ai_goals WHERE goal_name = 'MTTR Reduction');

INSERT INTO ai_goals (goal_name, target_metric, target_value, priority)
SELECT 'Knowledge Coverage', 'coverage_pct', 90, 3
WHERE NOT EXISTS (SELECT 1 FROM ai_goals WHERE goal_name = 'Knowledge Coverage');

INSERT INTO ai_goals (goal_name, target_metric, target_value, priority)
SELECT 'Low False Positive', 'false_positive_rate', 0.05, 4
WHERE NOT EXISTS (SELECT 1 FROM ai_goals WHERE goal_name = 'Low False Positive');

-- Phase 5: Digital Twin
CREATE TABLE IF NOT EXISTS simulation_results (
    id              SERIAL PRIMARY KEY,
    simulation_id   UUID DEFAULT gen_random_uuid(),
    incident_type   VARCHAR(100),
    knowledge_ids   INTEGER[],
    input_payload   JSONB,
    ai_response     TEXT,
    reasoning_trace JSONB,
    passed          BOOLEAN,
    score           FLOAT,
    created_at      TIMESTAMP DEFAULT NOW()
);

-- Phase 6: Meta-Cognition
CREATE TABLE IF NOT EXISTS meta_cognition_logs (
    id              SERIAL PRIMARY KEY,
    incident_id     INTEGER,
    worker_name     VARCHAR(100),
    reasoning_depth INTEGER,
    token_used      INTEGER,
    tool_accuracy   FLOAT,
    planning_cycles INTEGER,
    bias_detected   BOOLEAN DEFAULT FALSE,
    bias_type       VARCHAR(100),
    efficiency_score FLOAT,
    recommendations JSONB,
    evaluated_at    TIMESTAMP DEFAULT NOW()
);
