-- =============================================================================
-- Migration: 011_jarvis_tools_memory.sql
-- Description: Tools Memory Registry and Execution History for Jarvis AI NOC
-- Author: Principal AI Architect
-- PostgreSQL Version: 15+
-- =============================================================================

-- -----------------------------------------------------------------------------
-- 1. TOOLS REGISTRY TABLE
-- Stores metadata, parameter schemas, risk levels, and execution stats for tools.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jarvis_tools_registry (
    tool_id VARCHAR(128) PRIMARY KEY,
    tool_name VARCHAR(256) NOT NULL,
    category VARCHAR(128) NOT NULL DEFAULT 'SYSTEM_OPS', -- NETWORK, SERVER, SECURITY, STORAGE, DATABASE, UTILITY
    description TEXT NOT NULL,
    risk_level VARCHAR(32) NOT NULL DEFAULT 'MEDIUM', -- LOW, MEDIUM, HIGH, CRITICAL
    requires_approval BOOLEAN NOT NULL DEFAULT FALSE,
    requires_hitl BOOLEAN NOT NULL DEFAULT FALSE,
    parameter_schema JSONB NOT NULL DEFAULT '{}'::jsonb,
    rollback_procedure TEXT,
    author VARCHAR(128) NOT NULL DEFAULT 'SYSTEM',
    version INT NOT NULL DEFAULT 1,
    is_active BOOLEAN NOT NULL DEFAULT TRUE,
    total_executions INT NOT NULL DEFAULT 0,
    successful_executions INT NOT NULL DEFAULT 0,
    failed_executions INT NOT NULL DEFAULT 0,
    last_executed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jtr_category ON jarvis_tools_registry (category);
CREATE INDEX IF NOT EXISTS idx_jtr_risk_level ON jarvis_tools_registry (risk_level);
CREATE INDEX IF NOT EXISTS idx_jtr_is_active ON jarvis_tools_registry (is_active);

-- -----------------------------------------------------------------------------
-- 2. TOOLS EXECUTION HISTORY TABLE
-- Logs every tool execution, parameters passed, duration, outcome, and errors.
-- -----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS jarvis_tools_execution_history (
    execution_id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    tool_id VARCHAR(128) NOT NULL REFERENCES jarvis_tools_registry(tool_id) ON DELETE CASCADE,
    incident_id INT,
    device_name VARCHAR(128),
    operator VARCHAR(128) NOT NULL DEFAULT 'JARVIS_AGENT',
    parameters JSONB NOT NULL DEFAULT '{}'::jsonb,
    execution_duration_ms INT NOT NULL DEFAULT 0,
    status VARCHAR(32) NOT NULL DEFAULT 'SUCCESS', -- SUCCESS, FAILED, TIMEOUT, ROLLED_BACK
    output_summary TEXT,
    error_details TEXT,
    timestamp TIMESTAMPTZ NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_jteh_tool_id ON jarvis_tools_execution_history (tool_id);
CREATE INDEX IF NOT EXISTS idx_jteh_incident_id ON jarvis_tools_execution_history (incident_id);
CREATE INDEX IF NOT EXISTS idx_jteh_device_name ON jarvis_tools_execution_history (device_name);
CREATE INDEX IF NOT EXISTS idx_jteh_timestamp ON jarvis_tools_execution_history (timestamp DESC);

-- -----------------------------------------------------------------------------
-- SEED DEFAULT AI NOC TOOLS REGISTRY
-- -----------------------------------------------------------------------------
INSERT INTO jarvis_tools_registry (
    tool_id, tool_name, category, description, risk_level, requires_approval, requires_hitl, parameter_schema, rollback_procedure
) VALUES
(
    'restart_service',
    'Restart Systemd / Docker Service',
    'SERVER',
    'Restarts a specific systemd daemon or container service on a target node.',
    'MEDIUM', FALSE, FALSE,
    '{"service_name": "string", "target_host": "string"}'::jsonb,
    'Systemd will automatically attempt restart; manual rollback via systemctl start'
),
(
    'flush_routing_cache',
    'Flush L3 IP Route Cache',
    'NETWORK',
    'Flushes kernel route cache and socket buffer state to clear stale BGP/OSPF routes.',
    'MEDIUM', FALSE, TRUE,
    '{"interface": "string", "target_host": "string"}'::jsonb,
    'ip route reload / systemctl restart networking'
),
(
    'sysctl_tuning',
    'Apply Sysctl Kernel Parameter Tuning',
    'SERVER',
    'Applies live sysctl kernel parameter tuning (e.g. net.ipv4.tcp_tw_reuse = 1).',
    'MEDIUM', FALSE, FALSE,
    '{"parameter": "string", "value": "string"}'::jsonb,
    'Revert sysctl parameter to previous baseline value'
),
(
    'ping_check',
    'Execute ICMP Ping Diagnostics',
    'UTILITY',
    'Performs ICMP latency and packet loss diagnostic check against a target IP/hostname.',
    'LOW', FALSE, FALSE,
    '{"target_ip": "string", "count": "int"}'::jsonb,
    'N/A (Read-only tool)'
),
(
    'shutdown_prod_service',
    'Shutdown Production Service',
    'SERVER',
    'Shuts down a critical production service daemon. Requires mandatory approval.',
    'CRITICAL', TRUE, TRUE,
    '{"service_name": "string", "reason": "string"}'::jsonb,
    'Immediate execution of systemctl start / docker start'
)
ON CONFLICT (tool_id) DO NOTHING;
