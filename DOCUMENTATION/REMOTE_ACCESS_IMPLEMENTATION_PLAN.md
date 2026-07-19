# REMOTE ACCESS TOOLS - IMPLEMENTATION PLAN
## Phase 1 & 2: Settings Manager + Device Configuration

**Status**: 📋 PLANNING  
**Target**: Enterprise-Grade Remote Access Management System  
**Reference**: intruksi1.md + Current UI Mock  

---

## 1. EXECUTIVE SUMMARY

Implementasi Remote Access Settings Manager pada panel Remote Access Tools dengan:
- ✅ Settings Icon (⚙) di pojok kanan atas
- ✅ Modal konfigurasi multi-tab
- ✅ Auto-detection aplikasi remote (AnyDesk, RustDesk, VNC)
- ✅ Encrypted credential storage (AES-256-GCM)
- ✅ One-click remote access dengan auto-launch
- ✅ Audit logging untuk compliance
- ✅ Role-based access control

---

## 2. CURRENT UI ANALYSIS (dari gambar)

### Existing Remote Access Tools Panel
```
┌─ Remote Access Tools ────────────────────────────┐
│                                                  │
│ Device: PC-MKT-NUC (dropdown)    Target: 10.20.0.49 │
│                                                  │
│ [RustDesk] [VNC Viewer] [RDP] [AnyDesk]         │
│ [Wake on LAN] [Ping Device] [Restart PC]        │
│ [Shutdown PC] [Run CMD] [PowerShell]            │
│ [Add Route] [Sync Site Route] [Show Routes]     │
│ [File Transfer] [Task Manager]                  │
│                                                  │
│ ✅ Ping 10.20.0.70: 8ms (status indicator)      │
│                                                  │
└──────────────────────────────────────────────────┘
```

### New UI dengan Settings Manager
```
┌─ Remote Access Tools ⚙ Remote Settings ──────────────┐
│                                                      │
│ Device: PC-MKT-NUC (dropdown)    Target: 10.20.0.49 │
│                                                      │
│ [RustDesk] [VNC Viewer] [RDP] [AnyDesk]            │
│ [Wake on LAN] [Ping Device] [Restart PC]           │
│ [Shutdown PC] [Run CMD] [PowerShell]               │
│ [Add Route] [Sync Site Route] [Show Routes]        │
│ [File Transfer] [Task Manager]                     │
│                                                      │
│ ✅ Ping 10.20.0.70: 8ms                            │
│                                                      │
└──────────────────────────────────────────────────────┘
       ↑
       └─ Click ⚙ → Modal popup
```

---

## 3. ARCHITECTURE OVERVIEW

### Layer Stack
```
┌────────────────────────────────────────┐
│  FRONTEND (React/Vue)                  │
│  - Remote Access Tools Panel           │
│  - Settings Modal (Multi-tab)          │
│  - Device Selector                     │
├────────────────────────────────────────┤
│  API GATEWAY                           │
│  - /api/remote/config/*                │
│  - /api/remote/launch/*                │
│  - /api/remote/detect/*                │
│  - /api/remote/audit/*                 │
├────────────────────────────────────────┤
│  REMOTE SERVICE (Python)               │
│  - Device Manager                      │
│  - Credential Manager                  │
│  - Launcher Controller                 │
│  - Site Router                         │
├────────────────────────────────────────┤
│  DATABASE (PostgreSQL)                 │
│  - Devices                             │
│  - RemoteConfig                        │
│  - Credentials (Encrypted)             │
│  - Sites                               │
│  - AuditLogs                           │
├────────────────────────────────────────┤
│  LAUNCHER SERVICE (Windows)            │
│  - AnyDesk Module                      │
│  - RustDesk Module                     │
│  - VNC Module                          │
│  - Auto-Detector                       │
│  - Credential Decryption               │
│  - Process Manager                     │
└────────────────────────────────────────┘
```

---

## 4. DATABASE SCHEMA

### Table: remote_sites
```sql
CREATE TABLE remote_sites (
    site_id UUID PRIMARY KEY,
    site_name VARCHAR(255) NOT NULL,
    gateway VARCHAR(255),
    subnet VARCHAR(255),
    dns_server VARCHAR(255),
    default_remote_tool ENUM('anydesk', 'rustdesk', 'vnc'),
    preferred_route VARCHAR(255),
    priority INT DEFAULT 0,
    description TEXT,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(site_name)
);
```

### Table: devices
```sql
CREATE TABLE devices (
    device_id UUID PRIMARY KEY,
    hostname VARCHAR(255) NOT NULL,
    ip_address INET NOT NULL,
    agent_id UUID UNIQUE,
    site_id UUID REFERENCES remote_sites(site_id),
    os_type VARCHAR(50),
    agent_version VARCHAR(50),
    status ENUM('online', 'offline', 'unknown') DEFAULT 'unknown',
    last_online TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    UNIQUE(hostname, ip_address)
);
```

### Table: remote_config
```sql
CREATE TABLE remote_config (
    config_id UUID PRIMARY KEY,
    device_id UUID REFERENCES devices(device_id) ON DELETE CASCADE,
    anydesk_id VARCHAR(255),
    rustdesk_id VARCHAR(255),
    vnc_host VARCHAR(255),
    vnc_port INT DEFAULT 5900,
    preferred_tool ENUM('anydesk', 'rustdesk', 'vnc'),
    auto_connect BOOLEAN DEFAULT TRUE,
    last_detected TIMESTAMP,
    detection_status VARCHAR(50),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Table: credentials (ENCRYPTED)
```sql
CREATE TABLE credentials (
    credential_id UUID PRIMARY KEY,
    config_id UUID REFERENCES remote_config(config_id) ON DELETE CASCADE,
    tool_type ENUM('anydesk', 'rustdesk', 'vnc') NOT NULL,
    encrypted_password BYTEA NOT NULL,
    encryption_version VARCHAR(20),
    encryption_algorithm VARCHAR(50) DEFAULT 'AES-256-GCM',
    encryption_key_id VARCHAR(255),
    remember_password BOOLEAN DEFAULT FALSE,
    created_by UUID REFERENCES users(user_id),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Table: launcher_config
```sql
CREATE TABLE launcher_config (
    launcher_id UUID PRIMARY KEY,
    launcher_key VARCHAR(255) UNIQUE NOT NULL,
    launcher_ip VARCHAR(255),
    launcher_port INT DEFAULT 45600,
    launcher_status ENUM('online', 'offline') DEFAULT 'offline',
    anydesk_exe_path VARCHAR(500),
    rustdesk_exe_path VARCHAR(500),
    vnc_viewer_path VARCHAR(500),
    auto_detect_enabled BOOLEAN DEFAULT TRUE,
    last_heartbeat TIMESTAMP,
    jwt_secret BYTEA,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);
```

### Table: remote_sessions
```sql
CREATE TABLE remote_sessions (
    session_id UUID PRIMARY KEY,
    administrator_id UUID REFERENCES users(user_id),
    device_id UUID REFERENCES devices(device_id),
    remote_tool ENUM('anydesk', 'rustdesk', 'vnc', 'rdp') NOT NULL,
    site_id UUID REFERENCES remote_sites(site_id),
    target_ip INET,
    connection_start TIMESTAMP DEFAULT NOW(),
    connection_end TIMESTAMP,
    duration_seconds INT,
    status ENUM('connected', 'disconnected', 'failed') DEFAULT 'connected',
    failure_reason TEXT,
    session_key VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW()
);
```

### Table: remote_audit_logs
```sql
CREATE TABLE remote_audit_logs (
    audit_id UUID PRIMARY KEY,
    administrator_id UUID REFERENCES users(user_id),
    action VARCHAR(255),
    resource_type VARCHAR(50),
    resource_id UUID,
    device_id UUID REFERENCES devices(device_id),
    remote_tool VARCHAR(50),
    ip_address INET,
    user_agent TEXT,
    status VARCHAR(50),
    details JSONB,
    created_at TIMESTAMP DEFAULT NOW()
);
```

---

## 5. API ENDPOINTS

### 5.1 Remote Configuration Endpoints

#### GET /api/remote/config/{device_id}
**Purpose**: Ambil konfigurasi remote untuk device tertentu
```json
Response:
{
  "device_id": "uuid-device-001",
  "hostname": "PC-MKT-NUC",
  "ip_address": "10.20.0.49",
  "site_id": "uuid-site-hq",
  "remote_config": {
    "anydesk_id": "123456789",
    "rustdesk_id": "rustdesk-id-abc",
    "vnc_host": "10.20.0.49",
    "vnc_port": 5900,
    "preferred_tool": "rustdesk",
    "auto_connect": true
  },
  "launcher_status": "online"
}
```

#### POST /api/remote/config
**Purpose**: Simpan/update konfigurasi remote
```json
Request:
{
  "device_id": "uuid-device-001",
  "preferred_tool": "rustdesk",
  "auto_connect": true,
  "credentials": {
    "anydesk_id": "123456789",
    "anydesk_password": "encrypted...",
    "rustdesk_id": "rustdesk-id-abc",
    "rustdesk_password": "encrypted...",
    "vnc_port": 5900,
    "vnc_password": "encrypted..."
  }
}

Response:
{
  "status": "success",
  "config_id": "uuid-config-001",
  "message": "Configuration saved"
}
```

### 5.2 Settings Modal Endpoints

#### GET /api/remote/settings
**Purpose**: Ambil semua pengaturan remote
```json
Response:
{
  "general": {
    "default_remote_tool": "rustdesk",
    "auto_launch_remote": true,
    "auto_connect": true,
    "remember_last_device": true,
    "connection_timeout": 30,
    "retry_count": 3
  },
  "anydesk": {
    "exe_path": "C:\\Program Files (x86)\\AnyDesk\\AnyDesk.exe",
    "auto_detected": true,
    "remember_password": true,
    "use_unattended_access": true,
    "launch_fullscreen": false,
    "launch_minimized": false
  },
  "rustdesk": {
    "exe_path": "C:\\Program Files\\RustDesk\\rustdesk.exe",
    "auto_detected": true,
    "server": "relay.rustdesk.com",
    "relay": "relay.rustdesk.com",
    "api": "api.rustdesk.com",
    "encryption_key": "key...",
    "remember_password": true,
    "auto_connect": true
  },
  "vnc": {
    "viewer": "UltraVNC",
    "exe_path": "C:\\Program Files\\UltraVNC\\vncviewer.exe",
    "auto_detected": true,
    "default_port": 5900,
    "remember_password": true
  },
  "sites": [...]
}
```

#### PUT /api/remote/settings
**Purpose**: Update pengaturan remote
```json
Request:
{
  "general": {
    "default_remote_tool": "anydesk",
    "connection_timeout": 60,
    "retry_count": 5
  }
}

Response:
{
  "status": "success",
  "message": "Settings updated"
}
```

### 5.3 Auto-Detection Endpoints

#### POST /api/remote/detect
**Purpose**: Auto-detect instalasi aplikasi remote
```json
Response:
{
  "detection_results": {
    "anydesk": {
      "installed": true,
      "exe_path": "C:\\Program Files (x86)\\AnyDesk\\AnyDesk.exe",
      "version": "8.0.42"
    },
    "rustdesk": {
      "installed": true,
      "exe_path": "C:\\Program Files\\RustDesk\\rustdesk.exe",
      "version": "1.2.3"
    },
    "vnc": {
      "viewers": [
        {
          "name": "UltraVNC",
          "installed": true,
          "exe_path": "C:\\Program Files\\UltraVNC\\vncviewer.exe"
        },
        {
          "name": "TigerVNC",
          "installed": false
        },
        {
          "name": "RealVNC",
          "installed": false
        }
      ]
    }
  },
  "timestamp": "2026-06-17T12:00:00Z"
}
```

### 5.4 Device Auto-Discovery Endpoints

#### POST /api/remote/device/auto-discover
**Purpose**: Agent mengirim informasi remote device
```json
Request (dari Agent):
{
  "agent_id": "uuid-agent-001",
  "hostname": "PC-MKT-NUC",
  "ip_address": "10.20.0.49",
  "os": "Windows 10",
  "remote_info": {
    "anydesk_id": "123456789",
    "rustdesk_id": "rustdesk-id-abc",
    "vnc_port": 5900,
    "vnc_display": 0
  }
}

Response:
{
  "status": "success",
  "device_id": "uuid-device-001",
  "message": "Device info updated"
}
```

### 5.5 Remote Launch Endpoints

#### POST /api/remote/launch
**Purpose**: Minta launcher untuk membuka remote session
```json
Request:
{
  "device_id": "uuid-device-001",
  "tool": "rustdesk",
  "administrator_id": "uuid-admin-001",
  "site_id": "uuid-site-hq"
}

Response:
{
  "status": "launching",
  "session_id": "uuid-session-001",
  "message": "Launching RustDesk...",
  "launcher_status": "online"
}
```

#### GET /api/remote/launch/{session_id}/status
**Purpose**: Check status session remote
```json
Response:
{
  "session_id": "uuid-session-001",
  "status": "connected",
  "tool": "rustdesk",
  "connected_at": "2026-06-17T12:00:00Z",
  "duration_seconds": 120
}
```

### 5.6 Site Management Endpoints

#### GET /api/remote/sites
**Purpose**: List semua sites
```json
Response:
{
  "sites": [
    {
      "site_id": "uuid-site-hq",
      "site_name": "Head Office",
      "gateway": "10.20.0.1",
      "subnet": "10.20.0.0/24",
      "dns_server": "8.8.8.8",
      "default_remote_tool": "rustdesk",
      "priority": 1,
      "device_count": 45
    },
    {
      "site_id": "uuid-site-bnd",
      "site_name": "Bandung",
      "gateway": "10.21.0.1",
      "subnet": "10.21.0.0/24",
      "dns_server": "8.8.8.8",
      "default_remote_tool": "anydesk",
      "priority": 2,
      "device_count": 23
    }
  ]
}
```

#### POST /api/remote/sites
**Purpose**: Tambah site baru
```json
Request:
{
  "site_name": "Singapore",
  "gateway": "192.168.1.1",
  "subnet": "192.168.1.0/24",
  "dns_server": "8.8.8.8",
  "default_remote_tool": "rustdesk",
  "description": "Singapore Branch"
}

Response:
{
  "status": "success",
  "site_id": "uuid-site-sgp",
  "message": "Site created"
}
```

### 5.7 Test Connection Endpoints

#### POST /api/remote/test/anydesk
**Purpose**: Test AnyDesk configuration
```json
Response:
{
  "executable_found": true,
  "exe_path": "C:\\Program Files (x86)\\AnyDesk\\AnyDesk.exe",
  "version": "8.0.42",
  "ready": true,
  "message": "✅ AnyDesk is ready for remote access"
}
```

#### POST /api/remote/test/rustdesk
**Purpose**: Test RustDesk configuration
```json
Response:
{
  "executable_found": true,
  "exe_path": "C:\\Program Files\\RustDesk\\rustdesk.exe",
  "server_reachable": true,
  "relay_configured": true,
  "ready": true,
  "message": "✅ RustDesk is ready for remote access"
}
```

#### POST /api/remote/test/vnc
**Purpose**: Test VNC configuration
```json
Response:
{
  "viewer_found": true,
  "viewer": "UltraVNC",
  "exe_path": "C:\\Program Files\\UltraVNC\\vncviewer.exe",
  "ready": true,
  "message": "✅ UltraVNC is ready for remote access"
}
```

### 5.8 Audit Log Endpoints

#### GET /api/remote/audit
**Purpose**: Ambil remote access audit logs
```json
Response:
{
  "audit_logs": [
    {
      "audit_id": "uuid-audit-001",
      "administrator": "mkt@domain.com",
      "action": "remote_connect",
      "tool": "rustdesk",
      "device": "PC-MKT-NUC",
      "target_ip": "10.20.0.49",
      "connection_start": "2026-06-17T12:00:00Z",
      "connection_end": "2026-06-17T12:15:30Z",
      "duration_seconds": 930,
      "status": "success"
    },
    ...
  ],
  "total": 42,
  "page": 1
}
```

---

## 6. FRONTEND COMPONENTS

### 6.1 Remote Access Tools Panel Update
```jsx
File: /portal/templates/components/RemoteAccessTools.jsx

Features:
- Device selector dropdown
- Target IP display
- Remote tool buttons (RustDesk, VNC, RDP, AnyDesk, etc.)
- Settings icon (⚙) top-right corner
- Tooltip: "Remote Access Settings"
- Ping status indicator
- Quick action buttons
```

### 6.2 Remote Settings Modal (New)
```jsx
File: /portal/templates/components/RemoteSettingsModal.jsx

Tabs:
1. General
   - Default Remote Tool (radio buttons)
   - Auto Launch Remote (toggle)
   - Auto Connect (toggle)
   - Remember Last Device (toggle)
   - Connection Timeout (input)
   - Retry Count (input)

2. AnyDesk
   - Executable Path (input + Browse + Auto Detect)
   - Default Password (password input with show/hide)
   - Remember Password (checkbox)
   - Use Unattended Access (checkbox)
   - Launch Fullscreen (checkbox)
   - Launch Minimized (checkbox)
   - Test Connection (button)

3. RustDesk
   - Executable Path (input + Browse + Auto Detect)
   - Server (input)
   - Relay (input)
   - API (input)
   - Encryption Key (input)
   - Remember Password (checkbox)
   - Auto Connect (checkbox)
   - Test Connection (button)

4. VNC
   - Viewer selector (UltraVNC / TigerVNC / RealVNC)
   - Executable Path (input + Browse + Auto Detect)
   - Default Port (input)
   - Default Password (password input)
   - Remember Password (checkbox)
   - Test Connection (button)

5. Site Router
   - Table dengan columns: Site Name, Gateway, Subnet, DNS, Default Tool
   - Buttons: Add Site, Edit, Delete, Test Route

6. Security
   - Master Key Status
   - Encryption Algorithm (info)
   - Key Rotation Schedule
   - Backup Encryption Key (button)
   - Password Encryption Status

7. Test Connection
   - Test Results display
   - Status untuk: Executable, Server Connectivity, Password Availability
   - Overall Ready/Not Ready status
```

### 6.3 Device Remote Configuration Panel (New)
```jsx
File: /portal/templates/components/DeviceRemoteConfig.jsx

Display:
- Device Information
  - Hostname
  - IP Address
  - Agent ID
  - Site
  - Last Online
  
- Remote IDs
  - AnyDesk ID (auto-filled)
  - RustDesk ID (auto-filled)
  - VNC Host (auto-filled)
  - VNC Port (auto-filled)
  
- Preferred Tool selector
- Manual update button (untuk refresh data dari agent)
```

---

## 7. BACKEND SERVICES

### 7.1 Remote Service Module
```python
File: /02_DASHBOARD_PORTAL/remote_service.py

Classes:
- RemoteConfigManager
  - load_config(device_id)
  - save_config(device_id, config)
  - detect_installations()
  
- CredentialManager
  - encrypt_password(password)
  - decrypt_password(encrypted_password)
  - verify_credential(tool, credential)
  
- LauncherController
  - get_launcher_status()
  - send_launch_command(device_id, tool)
  - get_session_status(session_id)
  
- SiteManager
  - list_sites()
  - create_site(site_data)
  - get_default_tool_for_site(site_id)
  
- AuditLogger
  - log_remote_access(admin_id, device_id, tool, result)
  - get_audit_logs(filters)
```

### 7.2 Encryption Module (AES-256-GCM)
```python
File: /02_DASHBOARD_PORTAL/encryption.py

Functions:
- generate_master_key() → bytes
- encrypt_password(password, master_key) → encrypted_bytes
- decrypt_password(encrypted_bytes, master_key) → password
- verify_encryption_integrity(encrypted_data) → bool
```

### 7.3 Agent Communication Module
```python
File: /CLIENT_DISTRIBUSI/agent_remote_discovery.py

Functions:
- discover_anydesk_id() → str
- discover_rustdesk_id() → str
- discover_vnc_info() → dict
- send_remote_info_to_server(device_info)
```

---

## 8. LAUNCHER SERVICE (Windows)

### 8.1 Launcher Architecture
```
NOC_LAUNCHER.exe
├── Main Service
│   ├── Heart Beat (setiap 30 detik)
│   ├── API Server (localhost:45600)
│   └── Process Monitor
│
├── AutoDetector
│   ├── detect_anydesk()
│   ├── detect_rustdesk()
│   └── detect_vnc()
│
├── Modules
│   ├── AnyDeskModule
│   ├── RustDeskModule
│   └── VNCModule
│
├── Security
│   ├── JWT Verification
│   ├── HMAC Validation
│   └── TLS Support
│
└── Logger
    └── Local audit log
```

### 8.2 Launcher API
```
POST http://localhost:45600/launch
Body:
{
  "tool": "rustdesk",
  "id": "rustdesk-id-abc",
  "password": "decrypted_password",
  "jwt": "launcher_jwt_token"
}

Response:
{
  "status": "launching",
  "pid": 12345
}
```

---

## 9. SECURITY CONSIDERATIONS

### 9.1 Encryption
- ✅ AES-256-GCM untuk password storage
- ✅ Master key di file terpisah (launcher.key)
- ✅ Password hanya di-decrypt di Launcher, bukan di Dashboard
- ✅ In-transit encryption (TLS/HTTPS)

### 9.2 Access Control
- ✅ JWT untuk Launcher authentication
- ✅ HMAC untuk message integrity
- ✅ Role-based access control (admin/supervisor/helpdesk/viewer)
- ✅ Audit logging untuk semua operasi
- ✅ IP whitelisting untuk Launcher (localhost only)

### 9.3 Audit & Compliance
- ✅ Log semua remote access attempts
- ✅ Record: admin, device, tool, time, duration, result
- ✅ Retention policy (default 90 hari)
- ✅ Export audit logs capability

---

## 10. IMPLEMENTATION PHASES

### Phase 1: Foundation (Week 1-2)
**Goal**: Launcher Service + Auto-Detection

```
✅ Launcher Service:
   - Windows service infrastructure
   - API endpoint (localhost:45600)
   - Auto-detection module
   - Process manager

✅ Auto-Detection:
   - Scan registry untuk AnyDesk
   - Scan registry untuk RustDesk
   - Scan Program Files untuk VNC
   - Cache results untuk 1 jam

✅ Database:
   - Create launcher_config table
   - Create remote_config table
   - Create devices table (basic)

✅ Backend:
   - Launcher controller service
   - Auto-detection API endpoints
   - Test detection endpoints

✅ Testing:
   - Unit test untuk launcher
   - Integration test dengan Windows Service
```

### Phase 2: Device & Credential Management (Week 3-4)
**Goal**: Device auto-discovery + Encrypted credentials

```
✅ Agent Enhancement:
   - Add auto-discovery module
   - Detect remote IDs (AnyDesk, RustDesk, VNC)
   - Send info to Dashboard every 5 menit

✅ Database:
   - Create remote_sessions table
   - Create credentials table (encrypted)
   - Create remote_audit_logs table

✅ Encryption:
   - Implement AES-256-GCM encryption
   - Master key management
   - Credential storage & retrieval

✅ Backend APIs:
   - Device configuration endpoints
   - Credential storage endpoints
   - Site management endpoints

✅ Frontend:
   - Device remote config panel
   - Show auto-detected IDs
   - Manual update capability

✅ Testing:
   - Test auto-discovery
   - Test credential encryption
   - Test database operations
```

### Phase 3: Settings Modal & UI (Week 5-6)
**Goal**: Complete UI implementation

```
✅ Frontend:
   - Settings icon (⚙) in panel
   - Modal component with tabs
   - General settings tab
   - AnyDesk settings tab
   - RustDesk settings tab
   - VNC settings tab
   - Site router tab
   - Security tab
   - Test connection tab

✅ Settings Modal Features:
   - Browse for executable
   - Auto-detect installations
   - Save/load settings
   - Test connection buttons
   - Password encryption toggle

✅ Validation:
   - Executable path validation
   - Configuration completeness check
   - Test connection validation

✅ Testing:
   - Unit tests untuk components
   - Integration tests dengan backend
   - E2E tests untuk modal workflows
```

### Phase 4: One-Click Remote Access (Week 7-8)
**Goal**: Auto-launch dengan satu klik

```
✅ Launch Flow:
   - Click tool button (RustDesk, AnyDesk, VNC)
   - Dashboard determines preferred tool (dari device/site config)
   - Dashboard calls Launcher API
   - Launcher decrypts password
   - Launcher opens tool dengan parameters
   - Window focus shifts ke tool
   - Session logged

✅ Launcher Integration:
   - RustDesk launch dengan ID + password
   - AnyDesk launch dengan ID + password
   - VNC launch dengan host + port + password

✅ Backend:
   - Launch API endpoints
   - Session tracking
   - Auto tool selection logic

✅ Testing:
   - Test RustDesk launch
   - Test AnyDesk launch
   - Test VNC launch
   - Test tool fallback logic
```

### Phase 5: Enterprise Features (Week 9-10)
**Goal**: RBAC, audit, compliance

```
✅ Access Control:
   - Role-based permissions
   - Admin: Full access
   - Supervisor: Device groups
   - Helpdesk: Assigned devices
   - Viewer: Read-only, no remote access

✅ Audit & Logging:
   - Comprehensive audit log
   - Remote session recording (optional)
   - Export capability
   - Retention policies

✅ Multi-Site:
   - Site policies
   - Site-specific tools
   - Cross-site access control
   - Routing policies

✅ Advanced:
   - Session approval workflow
   - Time-based restrictions
   - Device group templates
   - Mass configuration deployment

✅ Testing:
   - RBAC permission tests
   - Audit log accuracy tests
   - Multi-site scenarios
```

---

## 11. DATABASE MIGRATION PLAN

### Migration Step 1: Create Tables
```sql
-- Run against PostgreSQL
-- Migration: 001_remote_access_schema.sql

CREATE TABLE remote_sites (...)
CREATE TABLE devices (...)
CREATE TABLE remote_config (...)
CREATE TABLE credentials (...)
CREATE TABLE launcher_config (...)
CREATE TABLE remote_sessions (...)
CREATE TABLE remote_audit_logs (...)

CREATE INDEX idx_device_site ON devices(site_id);
CREATE INDEX idx_config_device ON remote_config(device_id);
CREATE INDEX idx_sessions_admin ON remote_sessions(administrator_id);
CREATE INDEX idx_audit_device ON remote_audit_logs(device_id);
```

### Migration Step 2: Initial Data
```sql
-- Insert default launcher configuration
INSERT INTO launcher_config (launcher_key, launcher_port, jwt_secret)
VALUES ('default-launcher', 45600, gen_random_bytes(32));

-- Insert default sites
INSERT INTO remote_sites (site_name, default_remote_tool)
VALUES 
  ('Head Office', 'rustdesk'),
  ('Default Site', 'anydesk');
```

---

## 12. DEPLOYMENT CHECKLIST

### Pre-Deployment
- [ ] Database migrations tested
- [ ] All API endpoints tested
- [ ] Launcher service tested on Windows
- [ ] Encryption/decryption verified
- [ ] Security audit completed
- [ ] Documentation complete
- [ ] User training material ready

### Deployment Day
- [ ] Backup production database
- [ ] Run database migrations
- [ ] Deploy backend code
- [ ] Deploy frontend code
- [ ] Install Launcher service on admin PC
- [ ] Verify auto-detection works
- [ ] Test one complete workflow (click button → remote access)
- [ ] Monitor logs for errors

### Post-Deployment
- [ ] Verify all users can access Remote Access Tools
- [ ] Monitor audit logs
- [ ] Collect user feedback
- [ ] Fix any issues identified
- [ ] Document lessons learned

---

## 13. TESTING STRATEGY

### Unit Tests
```python
# test_encryption.py
- test_encrypt_decrypt_roundtrip()
- test_different_passwords()
- test_encryption_integrity()
- test_corrupted_data_handling()

# test_credential_manager.py
- test_store_credential()
- test_retrieve_credential()
- test_credential_not_found()

# test_launcher_controller.py
- test_launcher_online_status()
- test_launch_command_creation()
- test_command_validation()
```

### Integration Tests
```python
# test_device_remote_config.py
- test_device_with_auto_discovery()
- test_save_device_config()
- test_retrieve_device_config()

# test_remote_launch_workflow.py
- test_complete_launch_workflow()
- test_failed_launch_handling()
- test_session_tracking()

# test_site_routing.py
- test_site_device_assignment()
- test_preferred_tool_selection()
- test_site_based_routing()
```

### E2E Tests
```javascript
// test_settings_modal.cypress.js
- test_open_settings_modal()
- test_general_settings_tab()
- test_anydesk_settings_tab()
- test_rustdesk_settings_tab()
- test_vnc_settings_tab()
- test_site_router_tab()
- test_test_connection_button()
- test_save_settings()

// test_remote_access_flow.cypress.js
- test_select_device()
- test_click_rustdesk()
- test_auto_launch()
- test_session_connects()
- test_audit_log_recorded()
```

---

## 14. DOCUMENTATION REQUIREMENTS

### Technical Documentation
- [ ] Architecture design document
- [ ] API reference (OpenAPI/Swagger)
- [ ] Database schema documentation
- [ ] Launcher service manual
- [ ] Encryption algorithm documentation
- [ ] Security guidelines

### User Documentation
- [ ] Settings Manager user guide
- [ ] Device configuration guide
- [ ] Site management guide
- [ ] Troubleshooting guide
- [ ] Audit log guide

### Developer Documentation
- [ ] Development setup guide
- [ ] Code walkthrough
- [ ] Extension guide
- [ ] Testing guide

---

## 15. RISK ASSESSMENT & MITIGATION

| Risk | Severity | Mitigation |
|------|----------|-----------|
| Launcher service crashes | HIGH | Watchdog timer + auto-restart |
| Password decryption fails | HIGH | Fallback to manual entry |
| Auto-detection misses tools | MEDIUM | Manual path configuration option |
| Network latency for Launcher API | MEDIUM | Implement timeout + retry logic |
| Audit log grows too large | MEDIUM | Implement retention policy + archiving |
| Encryption key compromise | CRITICAL | Secure key storage + rotation policy |

---

## 16. SUCCESS CRITERIA

✅ **Phase 1 Complete** (Week 2):
- Launcher service installed and running
- Auto-detection identifies all tools
- API endpoints responding

✅ **Phase 2 Complete** (Week 4):
- Agents sending remote IDs
- Credentials encrypted and stored
- Database operations working

✅ **Phase 3 Complete** (Week 6):
- Settings modal fully functional
- All tabs working
- Test connection buttons working

✅ **Phase 4 Complete** (Week 8):
- One-click launch working for all tools
- Sessions tracked correctly
- No manual entry required

✅ **Phase 5 Complete** (Week 10):
- RBAC working correctly
- Audit logs comprehensive
- Multi-site routing working

---

## 17. TIMELINE SUMMARY

```
Week 1-2:  Phase 1 - Foundation
Week 3-4:  Phase 2 - Device Management
Week 5-6:  Phase 3 - Settings Modal UI
Week 7-8:  Phase 4 - One-Click Launch
Week 9-10: Phase 5 - Enterprise Features

Total: 10 weeks (70 days)
```

---

## 18. TEAM REQUIREMENTS

### Backend Developer
- Python/Flask expertise
- PostgreSQL
- Encryption (PyCryptodome)
- API design

### Frontend Developer
- React/Vue.js
- Modal components
- Form handling
- API integration

### DevOps/Infrastructure
- Windows service development
- Launcher service deployment
- Database administration
- Monitoring & logging

### QA/Testing
- API testing (Postman/REST Client)
- UI testing (Cypress)
- Security testing
- Performance testing

---

## 19. NEXT STEPS

1. **Approve** implementation plan
2. **Setup** development environment
3. **Create** feature branch (`feature/remote-access-settings`)
4. **Begin** Phase 1 development
5. **Schedule** weekly status meetings
6. **Document** progress and blockers

---

**Document Status**: 📋 DRAFT READY FOR REVIEW  
**Last Updated**: 2026-06-17  
**Version**: 1.0

