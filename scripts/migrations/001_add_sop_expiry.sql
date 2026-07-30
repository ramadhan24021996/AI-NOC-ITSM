-- Migration 001: Add SOP Expiration Date and Success/Failure Trackers to governance_sops
ALTER TABLE governance_sops ADD COLUMN IF NOT EXISTS expires_at TIMESTAMP WITH TIME ZONE;
ALTER TABLE governance_sops ADD COLUMN IF NOT EXISTS success_count INTEGER DEFAULT 0;
ALTER TABLE governance_sops ADD COLUMN IF NOT EXISTS failure_count INTEGER DEFAULT 0;
ALTER TABLE governance_sops ADD COLUMN IF NOT EXISTS success_rate NUMERIC(5,2) DEFAULT 100.00;
ALTER TABLE governance_sops ADD COLUMN IF NOT EXISTS status VARCHAR(32) DEFAULT 'ACTIVE';
