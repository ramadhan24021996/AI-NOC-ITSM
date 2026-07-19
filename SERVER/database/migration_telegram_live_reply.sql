-- Migration: P7.1 Telegram Live Reply Engine
-- Adds necessary columns to telegram_chat_mappings and inserts mock operators

-- 1. Add fields to telegram_chat_mappings
ALTER TABLE telegram_chat_mappings ADD COLUMN IF NOT EXISTS telegram_user_id bigint;
ALTER TABLE telegram_chat_mappings ADD COLUMN IF NOT EXISTS operator_id text;
ALTER TABLE telegram_chat_mappings ADD COLUMN IF NOT EXISTS operator_level text;
ALTER TABLE telegram_chat_mappings ADD COLUMN IF NOT EXISTS site_access text[];
ALTER TABLE telegram_chat_mappings ADD COLUMN IF NOT EXISTS verified boolean DEFAULT false;

-- 2. Insert mock operator profiles for local dev mapping if they do not exist
INSERT INTO operator_profiles (operator_id, display_name, role, max_workload, site_access, is_active)
VALUES 
    ('admin', 'Admin Operator', 'L3', 10, '{}'::text[], true),
    ('operator', 'Standard Operator', 'L2', 5, '{}'::text[], true),
    ('noc_operator', 'NOC Engineer', 'L1', 5, '{}'::text[], true)
ON CONFLICT (operator_id) DO NOTHING;

-- 3. Seed telegram chat mappings for authorized administrators
INSERT INTO telegram_chat_mappings (telegram_user_id, operator_id, operator_level, site_access, verified, created_at)
VALUES 
    (123456789, 'admin', 'L3', '{}'::text[], true, NOW()),
    (987654321, 'operator', 'L2', '{}'::text[], true, NOW())
ON CONFLICT DO NOTHING;
