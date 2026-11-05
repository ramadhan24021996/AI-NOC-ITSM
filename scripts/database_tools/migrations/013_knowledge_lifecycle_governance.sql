-- =============================================================================
-- Migration: 013_knowledge_lifecycle_governance.sql
-- Description: Add Lifecycle & Governance Columns to jarvis_knowledge_store
-- Author: Principal AI Architect
-- =============================================================================

ALTER TABLE jarvis_knowledge_store 
ADD COLUMN IF NOT EXISTS is_active BOOLEAN NOT NULL DEFAULT TRUE,
ADD COLUMN IF NOT EXISTS superseded_by UUID REFERENCES jarvis_knowledge_store(uuid) ON DELETE SET NULL,
ADD COLUMN IF NOT EXISTS review_notes TEXT;

CREATE INDEX IF NOT EXISTS idx_jks_is_active ON jarvis_knowledge_store (is_active);
CREATE INDEX IF NOT EXISTS idx_jks_version ON jarvis_knowledge_store (version);
