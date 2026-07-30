# PHASE 2 INTEGRATION GUIDE
## Complete Data Flow & Architecture

---

## 🏗️ SYSTEM ARCHITECTURE

```
┌─────────────────────────────────────────────────────────────────┐
│                        ADMIN DASHBOARD                           │
│                    (02_DASHBOARD_PORTAL)                         │
│                                                                  │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  Remote Access Settings Modal (Phase 3)                │   │
│  │  - 7 tabs for configuration                            │   │
│  │  - Store/retrieve credentials                          │   │
│  │  - Display auto-discovered IDs                         │   │
│  └─────────────────────────────────────────────────────────┘   │
└────┬────────────────────────────────────────────────────────────┘
     │ HTTP/REST
     ↓
┌─────────────────────────────────────────────────────────────────┐
│              BACKEND API SERVER (Flask)                          │
│                  (portal/remote_service.py)                      │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ API Endpoints                                           │   │
│  │ ✅ POST /api/remote/device/credentials (Store)         │   │
│  │ ✅ GET /api/remote/device/credentials/<tool> (Get)     │   │
│  │ ✅ POST /api/remote/device/auto-discover (Discovery)   │   │
│  │ ✅ PUT /api/remote/device/<id>/config (Update)         │   │
│  │ ✅ GET /api/remote/devices (List)                      │   │
│  │ ✅ GET /api/remote/sites (List)                        │   │
│  │ ✅ POST /api/remote/sites (Create)                     │   │
│  │ ✅ GET /api/remote/sessions (Active)                   │   │
│  └──────────────────────────────────────────────────────────┘   │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │ Encryption & Credential Management                      │   │
│  │ • AES-256-GCM (crypto.py)                               │   │
│  │ • CredentialManager (credentials.py)                    │   │
│  └──────────────────────────────────────────────────────────┘   │
└────┬────────────────────────────────────────────────────────────┘
     │ Database ORM (SQLAlchemy)
     ↓
┌─────────────────────────────────────────────────────────────────┐
│                    PostgreSQL DATABASE                           │
│                   (DATABASE/models.py)                           │
│                                                                  │
│  Tables:                                                        │
│  ✅ remote_sites - Multi-site configuration                   │
│  ✅ devices - PC inventory with agent_id                      │
│  ✅ remote_config - IDs per device (anydesk, rustdesk, vnc)  │
│  ✅ credentials - Encrypted passwords (AES-256-GCM)          │
│  ✅ remote_sessions - Session tracking                        │
│  ✅ remote_audit_logs - Audit trail                           │
│  ✅ launcher_config - Launcher service config                 │
└─────────────────────────────────────────────────────────────────┘
     ↑
     │ Discovery Report (HTTP)
     │
┌────┴──────────────────────────────────────────────────────────┐
│                  CLIENT PC (Target Device)                    │
│             (CLIENT_DISTRIBUSI/agent/)                        │
│                                                               │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │  Auto-Discovery Service (discovery.py)                 │ │
│  │  Runs every 5 minutes                                   │ │
│  │                                                         │ │
│  │  1. Detect AnyDesk ID (from registry)                  │ │
│  │     HKEY_CURRENT_USER\Software\AnyDesk\user            │ │
│  │     └─ Returns: 123456789                              │ │
│  │                                                         │ │
│  │  2. Detect RustDesk ID (from config file)              │ │
│  │     ~/.rustdesk/config.toml                             │ │
│  │     └─ Returns: 987654321                              │ │
│  │                                                         │ │
│  │  3. Detect VNC Port (port scanning)                    │ │
│  │     Check ports 5900-5902                              │ │
│  │     └─ Returns: 5900                                   │ │
│  │                                                         │ │
│  │  4. Report to Dashboard                                │ │
│  │     POST /api/remote/device/auto-discover              │ │
│  │     └─ Sends all detected IDs                          │ │
│  └─────────────────────────────────────────────────────────┘ │
└───────────────────────────────────────────────────────────────┘
     │ Local API (localhost:45600)
     ↓
┌─────────────────────────────────────────────────────────────┐
│               LAUNCHER SERVICE (Phase 1)                     │
│            (LAUNCHER_SERVICE/launcher/)                      │
│                                                             │
│  ┌─────────────────────────────────────────────────────────┐ │
│  │ Endpoints                                              │ │
│  │ ✅ POST /launch (with encrypted password)             │ │
│  │ ✅ GET /detect (return cached detected tools)         │ │
│  │ ✅ POST /detect (run fresh detection)                 │ │
│  └─────────────────────────────────────────────────────────┘ │
│                                                             │
│  ✅ Launch Modules:                                         │
│  • AnyDesk Launcher (subprocess with password)             │
│  • RustDesk Launcher (subprocess with password)            │
│  • VNC Launcher (subprocess with host:port)                │
└─────────────────────────────────────────────────────────────┘
     │ Execute Local Application
     ↓
┌─────────────────────────────────────────────────────────────┐
│              Remote Access Applications                      │
│                                                             │
│  ✅ AnyDesk (Unattended Access with password)              │
│  ✅ RustDesk (Unattended Access with password)             │
│  ✅ VNC Viewer (Connection to host:port)                   │
└─────────────────────────────────────────────────────────────┘
```

---

## 🔄 DATA FLOW SCENARIOS

### Scenario 1: Auto-Discovery → Store Config

```
TIMELINE:
T=0min:   Agent starts (agent/main.py)
          Loads agent_device_config.json
          Gets agent_id="agent-001"

T=0min:   AutoDiscovery.discover_all() runs:
          ├─ Scan registry for AnyDesk: 123456789
          ├─ Parse config for RustDesk: 987654321
          └─ Check ports for VNC: 5900

T=0min:   Report to Dashboard:
          POST /api/remote/device/auto-discover
          {
            "agent_id": "agent-001",
            "discovery": {
              "anydesk": {"id": "123456789"},
              "rustdesk": {"id": "987654321"},
              "vnc": {"port": 5900}
            }
          }

T=0min:   Dashboard API handler:
          1. Find device by agent_id
          2. Create/update remote_config
          3. Set anydesk_id, rustdesk_id, vnc_host
          4. Save to database
          5. Return 200 OK

T=5min:   Agent runs again (discovery loop)
          └─ Repeat same flow
          └─ Same IDs (no changes)

T=10min:  Agent discovers change (if any)
          └─ Report new config
          └─ Dashboard updates database
```

### Scenario 2: Admin Stores Credential

```
TIMELINE:
T=0s:     Admin clicks "Settings" icon (⚙)
          Modal opens → RustDesk tab

T=5s:     Admin enters password: "my-secret-pass"
          Clicks "Save"

T=5s:     Frontend sends:
          POST /api/remote/device/device-123/credentials
          {
            "tool_type": "rustdesk",
            "password": "my-secret-pass",
            "remember_password": true
          }

T=5s:     Backend API handler:
          1. Validate JWT token
          2. Decrypt request (if TLS used)
          3. Call encrypt_password("my-secret-pass")
             └─ AES256GCM.encrypt() in crypto.py
             └─ Generates: IV + SALT + CIPHERTEXT + TAG
             └─ Returns Base64: "abc123xyz..."
          
          4. Create Credential record:
             credential = Credential(
               config_id=config_id,
               tool_type='rustdesk',
               encrypted_password="abc123xyz...".encode()
             )
          
          5. Save to database
             db.add(credential)
             db.commit()
          
          6. Return 201 Created

T=6s:     Frontend shows "Credential saved"
          Password never logged, never stored plaintext
          Never sent again to frontend
```

### Scenario 3: Launcher Fetches Credential & Launches

```
TIMELINE:
T=0s:     Admin clicks "Launch RustDesk" on device panel

T=0s:     Frontend sends:
          POST /api/remote/launch
          {
            "device_id": "device-123",
            "tool": "rustdesk"
          }

T=1s:     Backend API handler:
          1. Validate JWT token
          2. Query Device by device_id
          3. Get RemoteConfig → rustdesk_id = "987654321"
          4. Get Credential for rustdesk:
             credential = db.query(Credential).filter(
               Credential.config_id == config_id,
               Credential.tool_type == 'rustdesk'
             ).first()
          
          5. Decrypt password:
             encrypted = credential.encrypted_password.decode()
             password = decrypt_password(encrypted)
             └─ AES256GCM.decrypt() in crypto.py
             └─ Validates authentication tag
             └─ Returns plaintext: "my-secret-pass"
          
          6. Call Launcher Service:
             requests.post(
               'http://localhost:45600/launch',
               json={
                 'tool': 'rustdesk',
                 'id': '987654321',
                 'password': 'my-secret-pass',
                 'exe_path': 'C:\\...\\rustdesk.exe'
               }
             )
          
          7. Audit log entry created:
             RemoteAuditLog(
               action='launch_request',
               device_id=device_id,
               remote_tool='rustdesk',
               status='success'
             )
          
          8. Return 200 OK

T=2s:     Launcher Service receives request:
          1. Validate request format
          2. Execute RustDeskModule.launch():
             cmd = ['C:\\...\\rustdesk.exe', '987654321', '--password', 'my-secret-pass']
             process = subprocess.Popen(cmd, CREATE_NEW_CONSOLE)
          
          3. Return 200 "launching"

T=3s:     RustDesk window opens on admin's PC
          Auto-connects to target device
          Session established

T=3s:     Backend creates RemoteSession:
          RemoteSession(
            session_id=uuid4(),
            admin_id=admin_id,
            device_id=device_id,
            remote_tool='rustdesk',
            status='connected',
            connection_start=now()
          )
          db.add(session)
          db.commit()

T=End:    Admin disconnects from RustDesk
          Backend updates RemoteSession:
          session.status = 'disconnected'
          session.connection_end = now()
          session.duration_seconds = calculated
          db.commit()
          
          Audit log updated with session_id
```

---

## 🔐 ENCRYPTION FLOW IN DETAIL

### Storing Credential (Encryption)

```
Input: "my-secret-password"
       ↓
Step 1: Generate random IV (12 bytes)
       ↓
Step 2: Generate random SALT (16 bytes)
       ↓
Step 3: Derive key using PBKDF2
       PBKDF2(
         password="ENCRYPTION_MASTER_KEY",
         salt=SALT,
         iterations=100,000,
         dkLen=32 bytes (256 bits)
       )
       ↓
Step 4: Encrypt password using AES-256-GCM
       cipher = AES.new(key, MODE_GCM, nonce=IV)
       ciphertext = cipher.encrypt("my-secret-password".encode())
       tag = cipher.digest()  ← Authentication tag
       ↓
Step 5: Combine components
       encrypted_bytes = IV + SALT + CIPHERTEXT + TAG
       ↓
Step 6: Encode to Base64
       encrypted_b64 = "abc123xyz..."
       ↓
Step 7: Store in database
       Credential.encrypted_password = encrypted_b64.encode('utf-8')
       
Result: Stored in database as LargeBinary field
        Never plaintext
        Includes authentication tag (prevents tampering)
        Unique IV ensures same plaintext → different ciphertext
```

### Retrieving Credential (Decryption)

```
Input: Encrypted bytes from database
       ↓
Step 1: Decode from Base64
       encrypted_b64 → encrypted_bytes
       ↓
Step 2: Extract components
       IV = encrypted_bytes[0:12]
       SALT = encrypted_bytes[12:28]
       CIPHERTEXT = encrypted_bytes[28:-16]
       TAG = encrypted_bytes[-16:]
       ↓
Step 3: Derive key using same PBKDF2
       key = PBKDF2(
         password="ENCRYPTION_MASTER_KEY",
         salt=SALT,  ← Same salt as encryption
         iterations=100,000,
         dkLen=32
       )
       ↓
Step 4: Decrypt and verify using AES-256-GCM
       cipher = AES.new(key, MODE_GCM, nonce=IV)
       plaintext = cipher.decrypt_and_verify(
         ciphertext=CIPHERTEXT,
         received_tag=TAG
       )
       
       If TAG doesn't match → ValueError (tampering detected)
       ↓
Step 5: Return plaintext
       "my-secret-password"
       
Result: Decrypted safely
        Tampering detected if authentication fails
        Only valid with correct ENCRYPTION_MASTER_KEY
```

---

## 🔌 API ENDPOINT REFERENCE

### Device Auto-Discovery Report

**Endpoint**: `POST /api/remote/device/auto-discover`

**Request**:
```json
{
  "agent_id": "agent-001",
  "discovery": {
    "anydesk": {
      "installed": true,
      "id": "123456789",
      "detected_at": "2026-06-17T14:30:00"
    },
    "rustdesk": {
      "installed": true,
      "id": "987654321",
      "detected_at": "2026-06-17T14:30:00"
    },
    "vnc": {
      "installed": true,
      "port": 5900,
      "host": "127.0.0.1",
      "detected_at": "2026-06-17T14:30:00"
    }
  }
}
```

**Response** (200 OK):
```json
{
  "status": "updated",
  "device_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Database Changes**:
- Finds Device by agent_id
- Updates RemoteConfig:
  - anydesk_id = "123456789"
  - rustdesk_id = "987654321"
  - vnc_host = "127.0.0.1"
  - vnc_port = 5900
  - last_detected = now()
  - detection_status = "success"

### Store Credential

**Endpoint**: `POST /api/remote/device/<device_id>/credentials`

**Request**:
```json
{
  "tool_type": "rustdesk",
  "password": "my-secret-password",
  "remember_password": true
}
```

**Response** (201 Created):
```json
{
  "status": "stored",
  "credential_id": "660e8400-e29b-41d4-a716-446655440001"
}
```

**Database Changes**:
- Creates or updates Credential record
- Encrypts password with AES-256-GCM
- Stores encrypted_password as LargeBinary
- Links to RemoteConfig via config_id

### Get Credential

**Endpoint**: `GET /api/remote/device/<device_id>/credentials/<tool_type>`

**Response** (200 OK):
```json
{
  "tool_type": "rustdesk",
  "password": "my-secret-password",
  "updated_at": "2026-06-17T14:30:00"
}
```

**Process**:
1. Query Credential by config_id + tool_type
2. Decrypt encrypted_password
3. Validate authentication tag
4. Return plaintext password

### Update Device Config

**Endpoint**: `PUT /api/remote/device/<device_id>/config`

**Request**:
```json
{
  "anydesk_id": "new-id-123",
  "preferred_tool": "anydesk",
  "auto_connect": true
}
```

**Response** (200 OK):
```json
{
  "status": "updated",
  "config_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

---

## 📊 DATABASE RELATIONSHIPS

```
RemoteSite
  ├─ 1..* Device
  │   ├─ 0..1 RemoteConfig
  │   │   ├─ 0..* Credential (encrypted)
  │   │   │   └─ tool_type: [anydesk, rustdesk, vnc]
  │   │   └─ Tracks: anydesk_id, rustdesk_id, vnc_host, vnc_port
  │   ├─ 0..* RemoteSession
  │   └─ 0..* RemoteAuditLog
  └─ 0..* RemoteSession

LauncherConfig
  └─ Separate table (one per launcher service)

RemoteSession
  ├─ admin_id (from users table)
  ├─ device_id (FK → Device)
  ├─ site_id (FK → RemoteSite)
  └─ Tracks connection lifecycle

RemoteAuditLog
  ├─ admin_id (from users table)
  ├─ device_id (FK → Device)
  └─ Logs all actions (view, modify, launch)
```

---

## 🧪 TESTING CHECKLIST

```
✅ Encryption
  □ AES256GCM.encrypt() returns valid format
  □ AES256GCM.decrypt() recovers original plaintext
  □ Same plaintext → different ciphertext (due to random salt/IV)
  □ Invalid format rejected by is_valid_encrypted()
  □ Tampered ciphertext fails verification

✅ Credential Manager
  □ Store credential → file persists
  □ Retrieve credential → decrypts correctly
  □ Multiple tools per device
  □ Delete credential removes from storage
  □ Get all credentials returns all tools

✅ Auto-Discovery
  □ AnyDesk ID detection works
  □ RustDesk ID detection works
  □ VNC port detection works
  □ Discovery results structure valid
  □ Report to dashboard succeeds

✅ Database Models
  □ All models instantiate correctly
  □ Foreign keys validate
  □ Relationships work (reverse access)
  □ Cascade delete works

✅ API Endpoints
  □ /api/remote/device/auto-discover creates/updates device
  □ /api/remote/device/<id>/credentials stores encrypted pwd
  □ /api/remote/device/<id>/credentials/<tool> returns decrypted
  □ /api/remote/device/<id>/config updates configuration
  □ /api/remote/devices lists all devices
  □ /api/remote/sessions shows active sessions

✅ Integration
  □ Full flow: Store → Encrypt → Persist → Retrieve → Decrypt
  □ Agent discovery → Dashboard update → DB commit
  □ Launcher fetch credential → Decrypt → Launch
```

---

## 🚀 DEPLOYMENT STEPS

### 1. Database Setup
```bash
cd DATABASE
alembic upgrade head
```

### 2. Install Dependencies
```bash
pip install -r LAUNCHER_SERVICE/requirements.txt
pip install -r PHASE_2_REQUIREMENTS.txt
```

### 3. Set Environment Variables
```bash
export ENCRYPTION_MASTER_KEY="strong-key-here"
export DATABASE_URL="postgresql://user:pass@localhost/osi_ai_dashboard"
export DASHBOARD_URL="http://localhost:5000"
```

### 4. Start Services
```bash
# Terminal 1: Launcher Service
cd LAUNCHER_SERVICE
python run_launcher.py

# Terminal 2: Dashboard Backend
cd portal
python dashboard_server.py

# Terminal 3: Agent (on each client PC)
cd CLIENT_DISTRIBUSI/agent
python main.py
```

### 5. Verify Integration
```bash
# Check launcher health
curl http://localhost:45600/health

# Check auto-discovery
curl -X POST http://localhost:45600/detect

# Check dashboard API
curl http://localhost:5000/health
```

---

**Architecture Complete!**  
Phase 2 integrates with Phase 1 and provides complete device management + credential encryption infrastructure.

Ready for Phase 3 (React UI).

