CREATE TABLE IF NOT EXISTS ai_playbooks (
    playbook_id SERIAL PRIMARY KEY,
    name TEXT UNIQUE NOT NULL,
    description TEXT,
    script TEXT NOT NULL,
    target_layer INTEGER,
    status TEXT DEFAULT 'DRAFT',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

INSERT INTO ai_playbooks (name, description, script, target_layer, status)
VALUES 
('Restart PostgreSQL', 'SOP to restart Postgres when deadlock occurs', 'systemctl restart postgresql', 6, 'ACTIVE'),
('Clear Temp Files', 'Clear system temp files if disk is full', 'rm -rf /tmp/*; rm -rf /var/tmp/*', 1, 'ACTIVE')
ON CONFLICT DO NOTHING;
