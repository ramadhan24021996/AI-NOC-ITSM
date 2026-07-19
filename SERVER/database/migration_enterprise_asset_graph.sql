-- TARGET SPRINT A: ENTERPRISE ASSET GRAPH & WORLD MODEL
-- MODULE 1: Enterprise Asset Graph
CREATE TABLE IF NOT EXISTS sites (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS assets (
    asset_id VARCHAR(100) PRIMARY KEY,
    hostname VARCHAR(255) NOT NULL,
    ip_address VARCHAR(45),
    mac_address VARCHAR(17),
    serial_number VARCHAR(100),
    vendor VARCHAR(100),
    model VARCHAR(100),
    operating_system VARCHAR(100),
    os_version VARCHAR(50),
    agent_version VARCHAR(50),
    device_type VARCHAR(50), -- Windows PC, Linux, Server, VM, Switch, Router, Printer, etc.
    location VARCHAR(255),
    latitude DECIMAL(10, 8),
    longitude DECIMAL(11, 8),
    site_id INTEGER REFERENCES sites(id) ON DELETE SET NULL,
    building VARCHAR(100),
    floor VARCHAR(50),
    rack VARCHAR(50),
    department VARCHAR(100),
    business_owner VARCHAR(100),
    technical_owner VARCHAR(100),
    support_team VARCHAR(100),
    maintenance_window VARCHAR(100),
    warranty_expiry DATE,
    status VARCHAR(50) DEFAULT 'ACTIVE', -- ACTIVE, INACTIVE, MAINTENANCE, RETIRED
    last_seen TIMESTAMP WITH TIME ZONE,
    last_telemetry JSONB,
    trust_score DECIMAL(5, 2) DEFAULT 100.0,
    health_score DECIMAL(5, 2) DEFAULT 100.0,
    criticality VARCHAR(50) DEFAULT 'LOW', -- LOW, MEDIUM, HIGH, CRITICAL, BUSINESS CRITICAL
    availability DECIMAL(5, 2) DEFAULT 100.0,
    sla DECIMAL(5, 2) DEFAULT 99.9,
    mttr_seconds INTEGER DEFAULT 0,
    mtbf_seconds INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Indexes for fast querying
CREATE INDEX idx_assets_hostname ON assets(hostname);
CREATE INDEX idx_assets_ip ON assets(ip_address);
CREATE INDEX idx_assets_mac ON assets(mac_address);
CREATE INDEX idx_assets_type ON assets(device_type);
CREATE INDEX idx_assets_site ON assets(site_id);
CREATE INDEX idx_assets_status ON assets(status);

-- MODULE 2 & 4: Dependency Graph & Service Map
CREATE TABLE IF NOT EXISTS asset_dependencies (
    id SERIAL PRIMARY KEY,
    source_asset_id VARCHAR(100) REFERENCES assets(asset_id) ON DELETE CASCADE,
    target_asset_id VARCHAR(100) REFERENCES assets(asset_id) ON DELETE CASCADE,
    dependency_type VARCHAR(50), -- UPSTREAM, DOWNSTREAM, PARENT, CHILD, PEER, GATEWAY, SERVICE, VM_HOST
    priority VARCHAR(50) DEFAULT 'NORMAL',
    weight INTEGER DEFAULT 1,
    bandwidth_mbps INTEGER,
    latency_ms DECIMAL(10, 2),
    redundancy_level INTEGER DEFAULT 0,
    critical_path BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    UNIQUE(source_asset_id, target_asset_id, dependency_type)
);

CREATE INDEX idx_asset_dep_source ON asset_dependencies(source_asset_id);
CREATE INDEX idx_asset_dep_target ON asset_dependencies(target_asset_id);

-- MODULE 3: Business Impact Engine
CREATE TABLE IF NOT EXISTS asset_business_impacts (
    id SERIAL PRIMARY KEY,
    asset_id VARCHAR(100) UNIQUE REFERENCES assets(asset_id) ON DELETE CASCADE,
    mission_critical BOOLEAN DEFAULT FALSE,
    revenue_impact_per_hour DECIMAL(15, 2) DEFAULT 0.0,
    compliance_requirement VARCHAR(255),
    customer_impact VARCHAR(50) DEFAULT 'LOW',
    operational_impact VARCHAR(50) DEFAULT 'LOW',
    recovery_priority INTEGER DEFAULT 99,
    maximum_downtime_minutes INTEGER,
    affected_users INTEGER DEFAULT 0,
    affected_applications TEXT[],
    affected_branch TEXT[],
    affected_services TEXT[],
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- MODULE 10: Asset Change Detection (Audit Trail)
CREATE TABLE IF NOT EXISTS asset_audit_trail (
    id SERIAL PRIMARY KEY,
    asset_id VARCHAR(100) REFERENCES assets(asset_id) ON DELETE CASCADE,
    change_type VARCHAR(50), -- CREATED, UPDATED, DELETED, STATUS_CHANGE
    field_changed VARCHAR(100),
    old_value TEXT,
    new_value TEXT,
    changed_by VARCHAR(100) DEFAULT 'SYSTEM',
    reason TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_asset_audit_asset ON asset_audit_trail(asset_id);
CREATE INDEX idx_asset_audit_time ON asset_audit_trail(created_at);

-- Update fleet_devices to bridge legacy devices
-- In module 9 we will discover and populate the assets table from fleet_devices and others
