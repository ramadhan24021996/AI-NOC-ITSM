# PHASE 3 INTEGRATION GUIDE
## React UI Components with Phase 1 & 2 Backend

---

## 🏗️ COMPLETE SYSTEM ARCHITECTURE (Phase 1+2+3)

```
┌──────────────────────────────────────────────────────────────────┐
│               REACT UI - DASHBOARD                              │
│                                                                  │
│  ┌──────────────────────────────────────────────────────────┐  │
│  │  Device List Panel                                       │  │
│  │  ┌────────────────────────────────────────────────────┐ │  │
│  │  │ PC-001 | Status: Online |  ⚙ [AnyDesk] [RustDesk]│ │  │
│  │  │        └─ Hostname: office-pc-001                │ │  │
│  │  │          IP: 192.168.1.100                       │ │  │
│  │  │          Last Online: 2 hours ago                │ │  │
│  │  └────────────────────────────────────────────────────┘ │  │
│  │  ┌────────────────────────────────────────────────────┐ │  │
│  │  │ PC-002 | Status: Offline | ⚙ [AnyDesk] [RustDesk]│ │  │
│  │  │        └─ Hostname: lab-pc-002                   │ │  │
│  │  │          IP: 192.168.1.101                       │ │  │
│  │  │          Last Online: 1 week ago                 │ │  │
│  │  └────────────────────────────────────────────────────┘ │  │
│  └──────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────────┘
                           ↓ Click ⚙
┌──────────────────────────────────────────────────────────────────┐
│              REMOTE SETTINGS MODAL (Phase 3)                    │
│                                                                  │
│  ┌────────────────────────────────────────────────────────────┐│
│  │ Remote Access Settings               PC-001 | device-id-123││
│  ├────────────────────────────────────────────────────────────┤│
│  │ 📋 🔴 🔵 🟢 🌐 🔒 ✓  [Tab Navigation]                      ││
│  ├────────────────────────────────────────────────────────────┤│
│  │                                                            ││
│  │  General Tab Content:                                      ││
│  │  ┌──────────────────────────────────────────────────┐    ││
│  │  │ Device Name: PC-001                              │    ││
│  │  │ Device ID: device-id-123                         │    ││
│  │  │ Status: Online ✓                                 │    ││
│  │  │ Last Online: Now                                 │    ││
│  │  │                                                  │    ││
│  │  │ Preferred Tool: [RustDesk ▼]                    │    ││
│  │  │ Auto-connect: ☑ Enabled                         │    ││
│  │  │ [Save Settings]                                 │    ││
│  │  │                                                  │    ││
│  │  │ Detected:                                        │    ││
│  │  │ • AnyDesk: 123456789 (from registry)            │    ││
│  │  │ • RustDesk: 987654321 (from config)             │    ││
│  │  │ • VNC: 127.0.0.1:5900 (from port scan)         │    ││
│  │  └──────────────────────────────────────────────────┘    ││
│  │                                                            ││
│  ├────────────────────────────────────────────────────────────┤│
│  │                              [Close]  ⟳ Saving...          ││
│  └────────────────────────────────────────────────────────────┘│
└──────────────────────────────────────────────────────────────────┘
              ↓ Click AnyDesk Tab
┌──────────────────────────────────────────────────────────────────┐
│  AnyDesk Tab Content:                                            │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ 🔴 AnyDesk Configuration                                  │ │
│  │                                                            │ │
│  │ ✓ Detected AnyDesk ID: 123456789                          │ │
│  │   (from Windows registry)                                 │ │
│  │                                                            │ │
│  │ Manual Configuration:                                     │ │
│  │ AnyDesk ID: [___________ ]                               │ │
│  │            (optional manual entry)                        │ │
│  │                                                            │ │
│  │ Credentials:                                              │ │
│  │ [+ Add/Update Password]                                  │ │
│  │                                                            │ │
│  │ Actions:                                                  │ │
│  │ [🔴 Launch AnyDesk]                                      │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
              ↓ Click [+ Add/Update Password]
┌──────────────────────────────────────────────────────────────────┐
│  Credential Form:                                                │
│  ┌────────────────────────────────────────────────────────────┐ │
│  │ Password: [***************************] [👁]             │ │
│  │ Confirm: [***************************]                   │ │
│  │ ☑ Remember this password                                 │ │
│  │                                                            │ │
│  │ [💾 Save Password] [Cancel]                              │ │
│  │                                                            │ │
│  │ 🔒 AES-256-GCM encrypted                                 │ │
│  │ Never stored/logged in plaintext                         │ │
│  └────────────────────────────────────────────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
              ↓ Submit
┌──────────────────────────────────────────────────────────────────┐
│  BACKEND FLOW:                                                   │
│                                                                  │
│  POST /api/remote/device/device-123/credentials                │
│  {                                                               │
│    "tool_type": "anydesk",                                     │
│    "password": "my-secret-password",                           │
│    "remember_password": true                                   │
│  }                                                              │
│                           ↓                                     │
│                 Flask Backend (Phase 2)                         │
│                     ↓                                           │
│              encrypt_password() [AES-256-GCM]                   │
│              ↓ Generates: IV + SALT + CT + TAG                │
│              ↓ Base64 encoded                                 │
│                     ↓                                          │
│            PostgreSQL Database                                 │
│            ├─ credentials.encrypted_password = "abc123xyz..."│
│            └─ credentials.updated_at = now()                 │
│                                                                │
│  Response: 201 Created                                         │
│  { "status": "stored", "credential_id": "..." }              │
└──────────────────────────────────────────────────────────────────┘
              ↓ Show Success Message
┌──────────────────────────────────────────────────────────────────┐
│  ✓ Credential saved successfully                               │
│  [🔴 Launch AnyDesk] button now enabled                        │
└──────────────────────────────────────────────────────────────────┘
```

---

## 🔄 DATA FLOW DIAGRAMS

### Scenario 1: Initial Load

```
User clicks ⚙ Settings
  ↓
RemoteAccessTools.handleSettingsClick()
  ├─ setShowModal(true)
  └─ RemoteSettingsModal mounts
      ├─ useEffect on mount
      └─ fetchDeviceConfig(deviceId)
          ├─ GET /api/remote/device/{deviceId}
          └─ setConfig(data)
              ├─ config.anydesk_id = "123456789"
              ├─ config.rustdesk_id = "987654321"
              └─ config.vnc_port = 5900
                  ↓
          GeneralTab renders with detected IDs
```

### Scenario 2: Add Password

```
User clicks [+ Add/Update Password]
  ↓
CredentialForm renders
  ├─ Password input focused
  └─ User enters password
      ↓
User clicks [💾 Save Password]
  ├─ validateForm() checks password match
  └─ storeCredential()
      ├─ POST /api/remote/device/{deviceId}/credentials
      │  {
      │    "tool_type": "anydesk",
      │    "password": "plaintext-pass",
      │    "remember_password": true
      │  }
      └─ Backend encrypts:
         ├─ Generate random IV (12 bytes)
         ├─ Generate random SALT (16 bytes)
         ├─ Derive key: PBKDF2(master_key, salt, 100k)
         ├─ Encrypt: AES256GCM(plaintext, key, IV)
         └─ Store: IV + SALT + CIPHERTEXT + TAG
             ↓
        Database saved
             ↓
        Response: 201 Created
             ↓
        onSuccess() called
             ↓
        CredentialForm closes
             ↓
        Success message shown: "Credential saved successfully"
```

### Scenario 3: Launch Remote

```
User clicks [🔴 Launch AnyDesk]
  ↓
onLaunchRequest("device-123", "anydesk")
  ↓
Backend POST /api/remote/launch
{
  "device_id": "device-123",
  "tool": "anydesk"
}
  ├─ Find Device by device_id
  ├─ Get RemoteConfig → anydesk_id = "123456789"
  ├─ Get Credential → encrypted_password
  ├─ Decrypt password (AES256GCM)
  └─ Call Launcher Service:
     POST http://localhost:45600/launch
     {
       "tool": "anydesk",
       "id": "123456789",
       "password": "plaintext-pass",
       "exe_path": "C:\\...\\AnyDesk.exe"
     }
      ├─ Launcher Service launches subprocess
      ├─ AnyDesk window opens on admin PC
      └─ Auto-connects to device
          ↓
       Database: RemoteSession created
       ├─ session_id = UUID
       ├─ device_id = device-123
       ├─ admin_id = current_user
       ├─ remote_tool = anydesk
       ├─ status = "connected"
       ├─ connection_start = now()
       └─ Audit log entry created
          ├─ action = "launch_request"
          ├─ status = "success"
          └─ timestamp = now()
```

---

## 📦 COMPONENT INTEGRATION POINTS

### 1. **RemoteAccessTools** (Entry Point)
```jsx
// Place in device list/panel
<RemoteAccessTools
  deviceId={device.id}
  deviceName={device.hostname}
  onLaunchRequest={handleLaunch}
/>

// Shows:
// - ⚙ Settings button
// - Quick launch buttons (AnyDesk, RustDesk, VNC)
// - Opens modal on click
```

### 2. **RemoteSettingsModal** (Main Container)
```jsx
// Opened by RemoteAccessTools
// Shows 7 tabs:
//   1. General (device info + detected tools)
//   2. AnyDesk (AnyDesk config + password)
//   3. RustDesk (RustDesk config + password)
//   4. VNC (VNC config + password)
//   5. SiteRouter (multi-site routing - Phase 4)
//   6. Security (best practices + features)
//   7. TestConnection (connectivity check)

// Calls:
// - fetchDeviceConfig() on mount
// - updateDeviceConfig() on save
```

### 3. **GeneralTab** (Device Overview)
```jsx
// Displays:
// - Device name, ID, status
// - Preferred tool selector
// - Auto-connect toggle
// - Detected IDs from Phase 2 auto-discovery

// Calls:
// - updateDeviceConfig() on save

// Data from:
// - config.anydesk_id (Phase 2)
// - config.rustdesk_id (Phase 2)
// - config.vnc_host (Phase 2)
// - config.vnc_port (Phase 2)
```

### 4. **AnyDeskTab, RustDeskTab, VNCTab** (Tool Config)
```jsx
// Each displays:
// - Detected tool ID (from Phase 2)
// - Manual entry field
// - CredentialForm button
// - Launch button

// Calls:
// - updateDeviceConfig() on ID save
// - storeCredential() via CredentialForm
// - launchRemoteTool() on launch click

// Encryption:
// - Backend handles AES-256-GCM
// - Frontend only sends plaintext password
// - Backend stores encrypted in database
```

### 5. **CredentialForm** (Password Management)
```jsx
// Shows:
// - Password input (masked)
// - Confirm password
// - Show/hide toggle
// - Remember checkbox

// Calls:
// - storeCredential(deviceId, toolType, { password, remember_password })

// API:
// POST /api/remote/device/<id>/credentials
// Response: 201 Created with credential_id
```

### 6. **API Service** (Backend Integration)
```javascript
// remoteApi.js exports:

fetchDeviceConfig(deviceId)
  → GET /api/remote/device/<id> (Phase 2)
  → Returns: config with detected IDs

updateDeviceConfig(deviceId, updates)
  → PUT /api/remote/device/<id>/config (Phase 2)
  → Updates: anydesk_id, rustdesk_id, vnc_host, vnc_port, preferred_tool

storeCredential(deviceId, toolType, data)
  → POST /api/remote/device/<id>/credentials (Phase 2)
  → Encrypts & stores password backend

getCredential(deviceId, toolType)
  → GET /api/remote/device/<id>/credentials/<tool> (Phase 2)
  → Returns decrypted password

launchRemoteTool(deviceId, toolType)
  → POST /api/remote/launch (Phase 4)
  → Calls Launcher Service (Phase 1)

testConnection(deviceId)
  → POST /api/remote/device/<id>/test (Future)
  → Tests device connectivity
```

---

## 🔐 SECURITY FLOW

```
FRONTEND (React)
├─ User enters password: "my-secret-pass"
├─ Form validates locally
└─ Sends to backend in HTTPS POST

        ↓

BACKEND (Flask - Phase 2)
├─ Receive: { tool_type, password, remember_password }
├─ Validate JWT token from Authorization header
├─ Call encrypt_password(password)
│   ├─ Generate random IV (12 bytes)
│   ├─ Generate random SALT (16 bytes)
│   ├─ Derive key: PBKDF2(MASTER_KEY, SALT, 100k, SHA256)
│   ├─ Create AES-256-GCM cipher: AES(key, IV)
│   ├─ Encrypt: cipher.encrypt(password)
│   ├─ Tag: cipher.digest() [authentication]
│   └─ Combine: IV + SALT + CIPHERTEXT + TAG
├─ Encode to Base64: "abc123xyz..."
└─ Store in database:
   Credential.encrypted_password = "abc123xyz..."

        ↓

DATABASE (PostgreSQL)
├─ Table: credentials
├─ Column: encrypted_password (BYTEA/LargeBinary)
├─ Value: Base64-encoded encrypted bytes
├─ NEVER plaintext
└─ NEVER decrypted at rest

        ↓

RETRIEVAL FLOW:
├─ Admin clicks [Launch AnyDesk]
├─ Backend receives request
├─ Query: SELECT encrypted_password FROM credentials WHERE ...
├─ Decrypt: decrypt_password(encrypted_b64)
│   ├─ Decode Base64 → bytes
│   ├─ Extract IV, SALT, CIPHERTEXT, TAG
│   ├─ Derive key: PBKDF2(MASTER_KEY, SALT, 100k)
│   ├─ Create AES-256-GCM cipher: AES(key, IV)
│   ├─ Decrypt & verify: cipher.decrypt_and_verify(CT, TAG)
│   └─ Returns: "my-secret-pass"
├─ Use plaintext only in memory
├─ Pass to Launcher Service (localhost:45600)
└─ Launcher executes tool with password
    └─ AnyDesk window auto-connects

        ↓

AUDIT LOGGING:
├─ Every action logged to RemoteAuditLog
├─ Admin ID recorded
├─ Action: launch_request
├─ Device ID recorded
├─ Status: success/failed
├─ Timestamp recorded
└─ No password logged
```

---

## 🧪 TESTING WORKFLOW

### 1. Manual Testing

```
Setup:
  □ Backend running (python portal/dashboard_server.py)
  □ Database configured (PostgreSQL)
  □ Agent discovery running
  □ React dev server running (npm start)

Test Case 1: Open Settings Modal
  □ Click ⚙ Settings icon
  □ Modal opens with animation
  □ Device config loads
  □ Tabs render

Test Case 2: View Detected IDs
  □ Click General tab
  □ See detected IDs:
    - AnyDesk: 123456789
    - RustDesk: 987654321
    - VNC: 127.0.0.1:5900

Test Case 3: Add Password
  □ Click AnyDesk tab
  □ Click [+ Add/Update Password]
  □ CredentialForm appears
  □ Enter password
  □ Confirm password
  □ Click [💾 Save Password]
  □ Check browser Network tab:
    POST /api/remote/device/.../credentials
    Status: 201 Created
  □ Success message appears
  □ Form closes

Test Case 4: Launch Remote
  □ Click [🔴 Launch AnyDesk]
  □ Check browser console for launchRemoteTool call
  □ Check backend logs:
    POST /api/remote/launch
    Launcher Service call
  □ AnyDesk window opens on admin PC

Test Case 5: Error Handling
  □ Try password mismatch
  □ See form error: "Passwords do not match"
  □ Try invalid credentials
  □ See API error message
  □ Check browser console for error logs
```

### 2. API Testing

```bash
# 1. Fetch device config
curl -X GET http://localhost:5000/api/remote/device/device-123 \
  -H "Authorization: Bearer <token>"

# 2. Update device config
curl -X PUT http://localhost:5000/api/remote/device/device-123/config \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "anydesk_id": "123456789",
    "preferred_tool": "rustdesk"
  }'

# 3. Store credential
curl -X POST http://localhost:5000/api/remote/device/device-123/credentials \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer <token>" \
  -d '{
    "tool_type": "anydesk",
    "password": "my-secret",
    "remember_password": true
  }'
# Response: 201 Created

# 4. Verify in database
psql -U postgres -d osi_ai_dashboard -c "
  SELECT credential_id, tool_type, encrypted_password 
  FROM credentials 
  WHERE config_id = <config_id>;
"
# Should show encrypted_password value (not plaintext)
```

---

## 📋 DEPLOYMENT CHECKLIST

```
Pre-deployment:
  □ Set ENCRYPTION_MASTER_KEY environment variable
  □ Verify DATABASE_URL connection
  □ Run database migrations: alembic upgrade head
  □ Verify JWT secret key configured
  □ Verify Launcher Service running on localhost:45600

Frontend Build:
  □ npm install (install dependencies)
  □ npm run build (create production build)
  □ Verify build output in dist/
  □ Test built components locally

Integration Tests:
  □ Run PHASE_2_INTEGRATION_TESTS.py
  □ Verify encryption/decryption works
  □ Verify credential storage/retrieval
  □ Verify API endpoints respond

Deployment:
  □ Copy React build to server
  □ Configure REACT_APP_API_URL
  □ Start backend server
  □ Start agent discovery service
  □ Test Settings modal in production
  □ Monitor logs for errors

Post-deployment:
  □ Verify device discovery working
  □ Test credential storage
  □ Test remote tool launch
  □ Check audit logs
  □ Monitor performance
```

---

**Phase 3 Complete!**  
React UI components successfully integrated with Phase 1 & 2 backend.

Ready for Phase 4: One-Click Launch Implementation

