-- =============================================================================
-- Migration: 010_jarvis_enterprise_memory_system.sql
-- Description: Database Schema for Jarvis AI 5-Layer Enterprise Memory Architecture
-- Author: Principal AI Architect
-- PostgreSQL Version: 15+ (with pgvector extension)
-- =============================================================================

CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS vector;

-- -----------------------------------------------------------------------------
-- 1. SHORT-TERM MEMORY SESSION BACKUP TABLE (RAM/Redis Persistence Backup)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jarvis_short_term_sessions (
    session_id VARCHAR(128) PRIMARY KEY,
    user_id VARCHAR(128) NOT NULL DEFAULT 'system_operator',
    active_device VARCHAR(128),
    incident_id INT,
    conversation_state JSONB NOT NULL DEFAULT '{}'::jsonb,
    troubleshooting_steps JSONB NOT NULL DEFAULT '[]'::jsonb,
    workflow_context JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMPTZ NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_jst_expires_at ON jarvis_short_term_sessions (expires_at);

-- -----------------------------------------------------------------------------
-- 2. LONG-TERM MEMORY STORE
-- Stores operator preferences, incident history, RCA, resolution, SOP success,
-- approval trails, HITL history, recovery history, and verification history.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jarvis_long_term_records (
    uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    record_type VARCHAR(64) NOT NULL, -- OPERATOR_PREF, INCIDENT_HISTORY, RCA, RESOLUTION, SOP_SUCCESS, APPROVAL, HITL, RECOVERY, VERIFICATION
    entity_id VARCHAR(128),
    author VARCHAR(128) NOT NULL DEFAULT 'JARVIS_ENGINE',
    confidence FLOAT NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    source VARCHAR(256) NOT NULL DEFAULT 'OSI_SYSTEM',
    version INT NOT NULL DEFAULT 1,
    data JSONB NOT NULL DEFAULT '{}'::jsonb,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jlt_record_type ON jarvis_long_term_records (record_type);
CREATE INDEX IF NOT EXISTS idx_jlt_entity_id ON jarvis_long_term_records (entity_id);
CREATE INDEX IF NOT EXISTS idx_jlt_timestamp ON jarvis_long_term_records (timestamp DESC);

-- -----------------------------------------------------------------------------
-- 3. KNOWLEDGE MEMORY STORE (pgvector + Hybrid Search BM25)
-- Stores SOPs, documentation, vendor runbooks, RCAs, lessons learned, and resolutions.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jarvis_knowledge_store (
    uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(512) NOT NULL,
    description TEXT,
    category VARCHAR(128) NOT NULL DEFAULT 'GENERAL_KNOWLEDGE', -- SOP, MIKROTIK, CISCO, LINUX, RUNBOOK, RCA, LESSON_LEARNED, RESOLUTION, POLICY
    tags TEXT[] NOT NULL DEFAULT '{}',
    symptoms TEXT,
    root_cause TEXT,
    solution TEXT,
    reference VARCHAR(512),
    environment VARCHAR(128) NOT NULL DEFAULT 'PRODUCTION',
    validation_status VARCHAR(64) NOT NULL DEFAULT 'VALIDATED', -- PENDING, VALIDATED, DEPRECATED
    severity VARCHAR(32) NOT NULL DEFAULT 'MEDIUM', -- LOW, MEDIUM, HIGH, CRITICAL
    confidence FLOAT NOT NULL DEFAULT 1.0 CHECK (confidence >= 0.0 AND confidence <= 1.0),
    source VARCHAR(256) NOT NULL DEFAULT 'USER_TEACHING',
    author VARCHAR(128) NOT NULL DEFAULT 'OPERATOR',
    validator VARCHAR(128) NOT NULL DEFAULT 'JARVIS_VALIDATOR',
    version INT NOT NULL DEFAULT 1,
    embedding_version VARCHAR(64) NOT NULL DEFAULT 'gemini-text-embedding-004',
    knowledge_score FLOAT NOT NULL DEFAULT 1.0,
    freshness_score FLOAT NOT NULL DEFAULT 1.0,
    usage_count INT NOT NULL DEFAULT 0,
    success_rate FLOAT NOT NULL DEFAULT 1.0,
    failure_rate FLOAT NOT NULL DEFAULT 0.0,
    related_incident VARCHAR(128),
    related_rca VARCHAR(128),
    related_sop VARCHAR(128),
    related_policy VARCHAR(128),
    content_tsvector TSVECTOR,
    embedding VECTOR(768),
    created TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jks_category ON jarvis_knowledge_store (category);
CREATE INDEX IF NOT EXISTS idx_jks_severity ON jarvis_knowledge_store (severity);
CREATE INDEX IF NOT EXISTS idx_jks_validation_status ON jarvis_knowledge_store (validation_status);
CREATE INDEX IF NOT EXISTS idx_jks_tags ON jarvis_knowledge_store USING GIN (tags);
CREATE INDEX IF NOT EXISTS idx_jks_tsvector ON jarvis_knowledge_store USING GIN (content_tsvector);
CREATE INDEX IF NOT EXISTS idx_jks_embedding_hnsw ON jarvis_knowledge_store USING hnsw (embedding vector_cosine_ops);

-- -----------------------------------------------------------------------------
-- 4. EXPERIENCE MEMORY STORE (Closed-Loop Learning Outcomes)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jarvis_experience_lessons (
    uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    incident_id INT NOT NULL,
    device_name VARCHAR(128),
    rca_id VARCHAR(128),
    recovery_action VARCHAR(256),
    verification_status VARCHAR(64) NOT NULL DEFAULT 'SUCCESS',
    lesson_learned TEXT NOT NULL,
    executive_summary TEXT NOT NULL,
    knowledge_uuid UUID REFERENCES jarvis_knowledge_store(uuid) ON DELETE SET NULL,
    confidence FLOAT NOT NULL DEFAULT 1.0,
    source VARCHAR(256) NOT NULL DEFAULT 'CLOSED_LOOP_LEARNING',
    author VARCHAR(128) NOT NULL DEFAULT 'EXPERIENCE_ENGINE',
    version INT NOT NULL DEFAULT 1,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    last_updated TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jel_incident_id ON jarvis_experience_lessons (incident_id);
CREATE INDEX IF NOT EXISTS idx_jel_device_name ON jarvis_experience_lessons (device_name);

-- -----------------------------------------------------------------------------
-- 5. POLICY MEMORY STORE (Immutable Permanent Governance Policies)
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jarvis_policy_rules (
    uuid UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    policy_code VARCHAR(128) UNIQUE NOT NULL,
    title VARCHAR(256) NOT NULL,
    description TEXT NOT NULL,
    rule_effect VARCHAR(64) NOT NULL DEFAULT 'FORCE_HITL', -- FORCE_HITL, REQUIRE_APPROVAL, DENY, ALLOW
    target_command_pattern VARCHAR(256) NOT NULL,
    target_risk_level VARCHAR(32) NOT NULL DEFAULT 'HIGH', -- LOW, MEDIUM, HIGH, CRITICAL
    requires_approval BOOLEAN NOT NULL DEFAULT TRUE,
    requires_hitl BOOLEAN NOT NULL DEFAULT TRUE,
    requires_rollback_plan BOOLEAN NOT NULL DEFAULT TRUE,
    requires_audit_logging BOOLEAN NOT NULL DEFAULT TRUE,
    confidence FLOAT NOT NULL DEFAULT 1.0,
    source VARCHAR(256) NOT NULL DEFAULT 'ENTERPRISE_GOVERNANCE',
    author VARCHAR(128) NOT NULL DEFAULT 'CHIEF_SECURITY_OFFICER',
    validator VARCHAR(128) NOT NULL DEFAULT 'POLICY_ENGINE',
    version INT NOT NULL DEFAULT 1,
    created TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

-- Seed default enterprise governance policies
INSERT INTO jarvis_policy_rules (
    policy_code, title, description, rule_effect, target_command_pattern, target_risk_level,
    requires_approval, requires_hitl, requires_rollback_plan, requires_audit_logging
) VALUES
(
    'NO_UNAPPROVED_ROUTER_REBOOT',
    'Restriksi Reboot Router Tanpa Approval',
    'Dilarang melakukan reboot atau restart pada router/gateway tanpa persetujuan (approval) resmi.',
    'REQUIRE_APPROVAL', 'reboot|restart|reload router', 'HIGH',
    TRUE, TRUE, TRUE, TRUE
),
(
    'NO_UNAPPROVED_PROD_SHUTDOWN',
    'Restriksi Shutdown Service Production',
    'Dilarang mematikan atau memberhentikan service/server production tanpa approval.',
    'REQUIRE_APPROVAL', 'shutdown|stop|kill service production', 'CRITICAL',
    TRUE, TRUE, TRUE, TRUE
),
(
    'HIGH_COMMAND_HITL',
    'Mandatori HITL Perintah Risiko HIGH',
    'Setiap eksekusi perintah dengan tingkat risiko HIGH wajib melalui pengawasan Human-In-The-Loop.',
    'FORCE_HITL', 'config change|routing change|firewall rule', 'HIGH',
    TRUE, TRUE, TRUE, TRUE
),
(
    'CRITICAL_COMMAND_APPROVAL',
    'Mandatori Approval Perintah Risiko CRITICAL',
    'Setiap eksekusi perintah dengan tingkat risiko CRITICAL wajib melalui persetujuan 2 orang (Human Approval).',
    'REQUIRE_APPROVAL', 'firmware flash|factory reset|purge data', 'CRITICAL',
    TRUE, TRUE, TRUE, TRUE
)
ON CONFLICT (policy_code) DO NOTHING;

-- -----------------------------------------------------------------------------
-- 6. IMMUTABLE AUDIT TRAIL FOR MEMORY SYSTEM
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jarvis_audit_trail (
    audit_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    memory_layer VARCHAR(64) NOT NULL, -- SHORT_TERM, LONG_TERM, KNOWLEDGE, EXPERIENCE, POLICY
    operation VARCHAR(64) NOT NULL, -- INSERT, UPDATE, DELETE, SEARCH, TEACH, EVALUATE
    target_uuid UUID,
    operator VARCHAR(128) NOT NULL DEFAULT 'SYSTEM',
    status VARCHAR(32) NOT NULL DEFAULT 'SUCCESS',
    details JSONB NOT NULL DEFAULT '{}'::jsonb,
    ip_address VARCHAR(64),
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jat_memory_layer ON jarvis_audit_trail (memory_layer);
CREATE INDEX IF NOT EXISTS idx_jat_operation ON jarvis_audit_trail (operation);
CREATE INDEX IF NOT EXISTS idx_jat_timestamp ON jarvis_audit_trail (timestamp DESC);
