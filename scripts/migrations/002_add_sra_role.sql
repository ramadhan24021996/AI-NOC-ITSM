-- Migration 002: Add SITE_RELIABILITY_ARCHITECT (SRA) role to RBAC users table
ALTER TABLE users ADD COLUMN IF NOT EXISTS role VARCHAR(64) DEFAULT 'NOC_OPERATOR';
CREATE INDEX IF NOT EXISTS idx_users_role ON users(role);
-- Insert system SRA default role reference if missing
INSERT INTO users (username, role, created_at)
VALUES ('sra_architect_admin', 'SITE_RELIABILITY_ARCHITECT', NOW())
ON CONFLICT (username) DO UPDATE SET role = 'SITE_RELIABILITY_ARCHITECT';
