# REMOTE ACCESS TOOLS - UI/UX DESIGN SPECIFICATION
## Sesuai Gambar Mock + Instruksi1.md

**Status**: ✅ DESIGN COMPLETE  
**Reference**: Gambar Remote Access Tools + intruksi1.md section 1-17  
**Target**: Enterprise RMM UI Pattern  

---

## 1. CURRENT UI ANALYSIS (Gambar Existing)

### Panel Header
```
┌─────────────────────────────────────────────────────┐
│ Remote Access Tools                                 │
│                                                     │
│ Device: PC-MKT-NUC (dropdown)  Target: 10.20.0.49 │
└─────────────────────────────────────────────────────┘
```

### Tool Buttons (Grid Layout)
```
┌──────┬──────┬────────┬──────┬────────────┬──────┐
│ Rust │ VNC  │  RDP   │ Any  │ Wake on    │ Ping │
│ Desk │View- │        │Desk  │ LAN        │Dev-  │
│      │er    │        │      │            │ice   │
├──────┼──────┼────────┼──────┼────────────┼──────┤
│ Rest │Shut- │ Run    │Power │            │ Add  │
│ PC   │down  │ CMD    │Shell │            │Route │
│      │ PC   │        │      │            │      │
├──────┼──────┼────────┼──────┼────────────┼──────┤
│ Sync │Show  │ File   │ Task │            │      │
│ Site │Rout- │Trans- │Mana- │            │      │
│Route │es    │fer     │ger   │            │      │
└──────┴──────┴────────┴──────┴────────────┴──────┘
```

### Status Footer
```
✅ Ping 10.20.0.70: 8ms (green indicator = online)
```

---

## 2. NEW UI WITH SETTINGS MANAGER

### Panel Header + Settings Icon
```
┌─────────────────────────────────────────────────────┐
│ 🖥 Remote Access Tools            ⚙ Remote Settings │  ← NEW
│                                                     │
│ Device: PC-MKT-NUC (dropdown)  Target: 10.20.0.49 │
└─────────────────────────────────────────────────────┘
```

**Icon Position**: Top-right corner of panel  
**Icon**: ⚙ (Gear icon) or Font Awesome `fa-cog`  
**Tooltip**: "Remote Access Settings"  
**Click Action**: Opens Remote Settings Modal

### Tool Buttons (Grid - UNCHANGED)
```
[RustDesk] [VNC Viewer] [RDP] [AnyDesk]
[Wake on LAN] [Ping Device] [Restart PC]
[Shutdown PC] [Run CMD] [PowerShell]
[Add Route] [Sync Site Route] [Show Routes]
[File Transfer] [Task Manager]
```

---

## 3. REMOTE SETTINGS MODAL

### Modal Structure
```
┌─────────────────────────────────────────────────────────────┐
│  Remote Access Settings                                  × │
├─────────────────────────────────────────────────────────────┤
│ ┌─────┬─────────┬──────┬──────┬──────┬────────┬────────┐   │
│ │ Gen │ AnyDesk │Rust- │ VNC  │ Site │Security│ Test   │   │
│ │eral │         │Desk  │      │Router│        │Connec- │   │
│ │     │         │      │      │      │        │tion    │   │
│ └─────┴─────────┴──────┴──────┴──────┴────────┴────────┘   │
│                                                             │
│ ┌─── GENERAL TAB ──────────────────────────────────────┐   │
│ │                                                      │   │
│ │ Default Remote Tool                                  │   │
│ │ ◉ RustDesk   ○ AnyDesk   ○ VNC                       │   │
│ │                                                      │   │
│ │ ☑ Auto Launch Remote                                │   │
│ │ ☑ Auto Connect                                      │   │
│ │ ☑ Remember Last Device                              │   │
│ │                                                      │   │
│ │ Connection Timeout (seconds): [30]                  │   │
│ │ Retry Count: [3]                                    │   │
│ │                                                      │   │
│ └──────────────────────────────────────────────────────┘   │
│                                                             │
│ ┌─────────────────────────────────────────────────────┐   │
│ │ [← PREV]                        [SAVE]  [CANCEL] ▶ │   │
│ └─────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────┘
```

### Tab 1: General Settings
```
┌─────────────────────────────────────────────┐
│ Default Remote Tool                         │
│ ◉ RustDesk  ○ AnyDesk  ○ VNC               │
│                                             │
│ Behavior Settings                           │
│ ☑ Auto Launch Remote                        │
│ ☑ Auto Connect                              │
│ ☑ Remember Last Device                      │
│                                             │
│ Connection Parameters                       │
│ Connection Timeout (seconds): [ 30  ]       │
│ Retry Count: [ 3 ]                          │
│                                             │
│ [Set as Default]  [Reset to Factory]       │
└─────────────────────────────────────────────┘
```

### Tab 2: AnyDesk Settings
```
┌─────────────────────────────────────────────┐
│ ANYDESK CONFIGURATION                       │
│                                             │
│ Executable Path                             │
│ ┌──────────────────────────────────────┐   │
│ │ C:\Program Files (x86)\AnyDesk\...  │   │
│ └──────────────────────────────────────┘   │
│ [Browse...]  [Auto Detect]                 │
│                                             │
│ Default Password                            │
│ ┌──────────────────────────────────────┐   │
│ │ ••••••••••                           │   │
│ └──────────────────────────────────────┘   │
│ [👁 Show]  [🔒 Hide]                      │
│                                             │
│ Features                                    │
│ ☑ Remember Password                        │
│ ☑ Use Unattended Access                    │
│ ☑ Launch Fullscreen                        │
│ ☐ Launch Minimized                         │
│                                             │
│ [Test AnyDesk]                              │
└─────────────────────────────────────────────┘
```

### Tab 3: RustDesk Settings
```
┌─────────────────────────────────────────────┐
│ RUSTDESK CONFIGURATION                      │
│                                             │
│ Executable Path                             │
│ ┌──────────────────────────────────────┐   │
│ │ C:\Program Files\RustDesk\...        │   │
│ └──────────────────────────────────────┘   │
│ [Browse]  [Auto Detect]                    │
│                                             │
│ Connection Settings                         │
│ Server:   [ relay.rustdesk.com ]            │
│ Relay:    [ relay.rustdesk.com ]            │
│ API:      [ api.rustdesk.com ]              │
│                                             │
│ Encryption Key                              │
│ ┌──────────────────────────────────────┐   │
│ │ [paste your encryption key]          │   │
│ └──────────────────────────────────────┘   │
│                                             │
│ Features                                    │
│ ☑ Remember Password                        │
│ ☑ Auto Connect                              │
│                                             │
│ [Test RustDesk]                             │
└─────────────────────────────────────────────┘
```

### Tab 4: VNC Settings
```
┌─────────────────────────────────────────────┐
│ VNC CONFIGURATION                           │
│                                             │
│ Preferred Viewer                            │
│ ┌─────────────────────────────┐             │
│ │ UltraVNC ▼                  │             │
│ └─────────────────────────────┘             │
│ • UltraVNC                                  │
│ • TigerVNC                                  │
│ • RealVNC                                   │
│                                             │
│ Executable Path                             │
│ ┌──────────────────────────────────────┐   │
│ │ C:\Program Files\UltraVNC\...        │   │
│ └──────────────────────────────────────┘   │
│ [Browse]  [Auto Detect]                    │
│                                             │
│ Connection Settings                         │
│ Default Port: [ 5900 ]                      │
│                                             │
│ Default Password                            │
│ ┌──────────────────────────────────────┐   │
│ │ ••••••••••                           │   │
│ └──────────────────────────────────────┘   │
│                                             │
│ ☑ Remember Password                        │
│                                             │
│ [Test VNC]                                  │
└─────────────────────────────────────────────┘
```

### Tab 5: Site Router
```
┌──────────────────────────────────────────────┐
│ SITE MANAGEMENT                              │
│                                              │
│ ┌──────────────────────────────────────────┐ │
│ │ Site Name │Gateway  │Subnet │Tool │...  │ │
│ ├──────────┬─────────┬────────┼─────┤     │ │
│ │Head Off. │10.20.0.1│10.20.. │RD   │ ... │ │
│ │Bandung   │10.21.0.1│10.21.. │AD   │ ... │ │
│ │Surabaya  │10.22.0.1│10.22.. │VNC  │ ... │ │
│ │Singapore │192.168..│192.168.│RD   │ ... │ │
│ └──────────┴─────────┴────────┴─────┴─────┘ │
│                                              │
│ [+ Add Site]  [Edit]  [Delete]  [Test Route]│
│                                              │
│ ┌─ ADD SITE DIALOG ──────────────────────┐  │
│ │ Site Name: [ ________________ ]        │  │
│ │ Gateway:   [ ________________ ]        │  │
│ │ Subnet:    [ ________________ ]        │  │
│ │ DNS Server:[ 8.8.8.8_________]        │  │
│ │ Default Tool: [RustDesk ▼]             │  │
│ │ Priority: [ 1 ]                        │  │
│ │ Description: [____________ ]           │  │
│ │                                        │  │
│ │ [Create]  [Cancel]                     │  │
│ └────────────────────────────────────────┘  │
└──────────────────────────────────────────────┘
```

### Tab 6: Security Settings
```
┌────────────────────────────────────────────┐
│ SECURITY & ENCRYPTION                      │
│                                            │
│ Master Key Status                          │
│ Status: ✅ Configured & Protected         │
│ Encryption: AES-256-GCM                    │
│ Last Rotated: 2026-06-01                   │
│                                            │
│ Password Encryption                        │
│ Algorithm: AES-256-GCM                     │
│ Salt: Generated from master key            │
│ Integrity Check: ✅ Enabled                │
│                                            │
│ Key Management                              │
│ [🔄 Rotate Key]                            │
│ [💾 Backup Encryption Key]                │
│ [📥 Import Key]                            │
│                                            │
│ Password Policies                          │
│ ☑ Never save plaintext passwords          │
│ ☑ Encrypt passwords at rest                │
│ ☑ Clear cache on logout                    │
│                                            │
│ ⚠️  WARNING: Do not share master key!      │
└────────────────────────────────────────────┘
```

### Tab 7: Test Connection
```
┌────────────────────────────────────────────┐
│ TEST CONNECTION STATUS                     │
│                                            │
│ ANYDESK                                    │
│ ✅ Executable Found                        │
│ ✅ Version: 8.0.42                         │
│ ✅ Password Available                      │
│ ✅ READY FOR USE                           │
│                                            │
│ RUSTDESK                                   │
│ ✅ Executable Found                        │
│ ✅ Version: 1.2.3                          │
│ ✅ Server Reachable                        │
│ ✅ Relay Configured                        │
│ ✅ READY FOR USE                           │
│                                            │
│ VNC (UltraVNC)                             │
│ ✅ Viewer Found                            │
│ ✅ Version: 1.4.2                          │
│ ✅ Port Configured (5900)                  │
│ ✅ Password Available                      │
│ ✅ READY FOR USE                           │
│                                            │
│ 🎉 ALL SYSTEMS READY FOR REMOTE ACCESS    │
│                                            │
│ [Refresh Tests]  [Close]                  │
└────────────────────────────────────────────┘
```

---

## 4. DEVICE REMOTE CONFIGURATION PANEL (New)

Ditampilkan di bagian device details atau device selector:

```
┌─────────────────────────────────────────────────┐
│ DEVICE: PC-MKT-NUC                              │
├─────────────────────────────────────────────────┤
│ Hostname: PC-MKT-NUC                            │
│ IP Address: 10.20.0.49                          │
│ Agent ID: agent-uuid-123456                     │
│ Site: Head Office                               │
│ Last Online: 2026-06-17 14:23:45                │
│ Agent Version: 2.5.1                            │
├─────────────────────────────────────────────────┤
│ REMOTE ACCESS IDS (Auto-detected)               │
│                                                 │
│ AnyDesk ID:     123456789                       │
│ RustDesk ID:    rustdesk-abc-def-123           │
│ VNC Host:       10.20.0.49                      │
│ VNC Port:       5900                            │
│                                                 │
│ Preferred Tool: [RustDesk ▼]                    │
│                                                 │
│ [🔄 Update from Agent]  [✏️ Manual Edit]       │
└─────────────────────────────────────────────────┘
```

---

## 5. AUTO-LAUNCH WORKFLOW

### User Flow Diagram
```
User clicks ⚙ Settings Icon
    ↓
Remote Settings Modal opens
    ↓
User configures each tool:
  - AnyDesk executable path + password
  - RustDesk executable path + password
  - VNC viewer path + port + password
    ↓
User clicks [Test Connection] buttons
    ↓
All tests pass ✅
    ↓
User clicks [Save Settings]
    ↓
Settings encrypted & stored in database
    ↓
User selects device: PC-MKT-NUC
    ↓
User clicks [RustDesk] button
    ↓
Dashboard calls API: /api/remote/launch
    ↓
Backend retrieves:
  - Device config (RustDesk ID)
  - Decrypts password
  - Sends to Launcher Service
    ↓
Launcher Service:
  - Finds rustdesk.exe
  - Decrypts password
  - Launches: rustdesk.exe <ID> <PASSWORD>
    ↓
RustDesk opens & auto-connects
    ↓
Focus shifts to RustDesk window
    ↓
Session logged in audit log ✅
```

### Implementation Steps (for each tool)

#### ANYDESK LAUNCH
```
1. User clicks [AnyDesk] button
2. Dashboard determines: device PC-MKT-NUC → AnyDesk ID (123456789)
3. Dashboard API POST /api/remote/launch
   {
     "device_id": "device-uuid",
     "tool": "anydesk",
     "admin_id": "admin-uuid"
   }
4. Backend:
   - Fetch device config
   - Get AnyDesk ID: 123456789
   - Decrypt password: "secretpassword"
   - Get anydesk.exe path from settings
   - Call Launcher API
5. Launcher:
   - Decrypt password locally
   - Execute: 
     cmd /c "C:\Program Files (x86)\AnyDesk\AnyDesk.exe" 123456789
   - Set password in memory
   - Auto-connect with Unattended Access
6. AnyDesk opens → auto-connects
7. Session created in database
8. Audit log recorded
```

#### RUSTDESK LAUNCH
```
1. User clicks [RustDesk] button
2. Dashboard determines: device PC-MKT-NUC → RustDesk ID
3. Dashboard API POST /api/remote/launch
   {
     "device_id": "device-uuid",
     "tool": "rustdesk",
     "admin_id": "admin-uuid"
   }
4. Backend:
   - Fetch device config
   - Get RustDesk ID
   - Decrypt password
   - Get rustdesk.exe path
   - Call Launcher API
5. Launcher:
   - Decrypt password locally
   - Execute: 
     cmd /c "C:\Program Files\RustDesk\rustdesk.exe" <ID> --password <PASS>
   - Auto-connect
6. RustDesk opens → auto-connects
7. Session created & logged
```

#### VNC LAUNCH
```
1. User clicks [VNC Viewer] button
2. Dashboard determines: device PC-MKT-NUC → VNC Host:Port
3. Dashboard API POST /api/remote/launch
   {
     "device_id": "device-uuid",
     "tool": "vnc",
     "admin_id": "admin-uuid"
   }
4. Backend:
   - Fetch device config
   - Get VNC Host: 10.20.0.49
   - Get VNC Port: 5900
   - Decrypt password
   - Get vncviewer.exe path
   - Call Launcher API
5. Launcher:
   - Decrypt password
   - Create VNC connection profile
   - Execute: 
     cmd /c "C:\Program Files\UltraVNC\vncviewer.exe" 10.20.0.49:5900
   - Pass password to viewer
6. VNC Viewer opens → auto-connects
7. Session created & logged
```

---

## 6. AUTO-DETECTION FEATURE

### Launcher Auto-Detection Process
```
Launcher Service starts
    ↓
Scan Windows Registry:
  - HKLM\Software\AnyDesk → AnyDesk installed?
  - HKLM\Software\RustDesk → RustDesk installed?
    ↓
Scan Program Files:
  - C:\Program Files\AnyDesk\AnyDesk.exe
  - C:\Program Files (x86)\AnyDesk\AnyDesk.exe
  - C:\Program Files\RustDesk\rustdesk.exe
  - C:\Program Files (x86)\RustDesk\rustdesk.exe
  - C:\Program Files\UltraVNC\vncviewer.exe
  - C:\Program Files (x86)\UltraVNC\vncviewer.exe
  - C:\Program Files\TigerVNC\vncviewer.exe
  - C:\Program Files\RealVNC\VNC Viewer\vncviewer.exe
    ↓
Collect Version Info:
  - Get file version from executable
    ↓
Cache Results (1 hour TTL)
    ↓
When user opens Settings Modal:
  - API call /api/remote/detect
  - Return cached results or fresh scan
    ↓
Modal shows:
  ✅ AnyDesk 8.0.42 (C:\Program Files (x86)\...)
  ✅ RustDesk 1.2.3 (C:\Program Files\...)
  ✅ UltraVNC 1.4.2 (C:\Program Files\...)
```

### Agent Auto-Discovery Process
```
Agent starts every 5 minutes:
    ↓
Check if AnyDesk is running:
  - Get AnyDesk ID from registry/config
  - Send to server
    ↓
Check if RustDesk is running:
  - Get RustDesk ID
  - Send to server
    ↓
Check VNC status:
  - Get VNC port
  - Get VNC display number
  - Send to server
    ↓
Server updates database:
  Device.anydesk_id = "123456789"
  Device.rustdesk_id = "rustdesk-abc"
  Device.vnc_port = 5900
  Device.last_sync = NOW()
    ↓
Dashboard fetches device config:
  - Shows auto-detected IDs
  - Allows manual override
```

---

## 7. ENCRYPTION & PASSWORD HANDLING

### Password Encryption Flow
```
User enters password in Settings Modal
    ↓
Password transmitted over HTTPS
    ↓
Backend receives password
    ↓
Generate random salt (16 bytes)
    ↓
Encrypt with AES-256-GCM:
  - Master key (from launcher.key)
  - Algorithm: AES-256-GCM
  - Salt: random
  - IV: random (per encryption)
    ↓
Ciphertext = IV + salt + encrypted_password + auth_tag
    ↓
Store in database.credentials.encrypted_password
    ↓
===== TIME PASSES (user wants to connect) =====
    ↓
User clicks [RustDesk] button
    ↓
Backend retrieves encrypted_password from database
    ↓
Backend decrypts to get plaintext password
    ↓
Backend sends DECRYPTED password to Launcher Service
    ↓
Launcher processes password locally
    ↓
Launcher passes to rustdesk.exe
    ↓
Password NEVER stored plaintext in database ✅
Password NEVER transmitted in plaintext ✅
```

---

## 8. SECURITY CONSIDERATIONS

### Data Protection
```
✅ Passwords encrypted with AES-256-GCM
✅ Master key stored separately
✅ Never logged or displayed in plaintext
✅ SSL/TLS for all API communications
✅ JWT tokens for Launcher authentication
✅ HMAC verification for message integrity
```

### Access Control
```
✅ Only authenticated admins can access Settings
✅ Role-based access:
   - Admin: Full access (configure + launch)
   - Supervisor: Limited sites only
   - Helpdesk: Pre-configured devices only
   - Viewer: Read-only, no launch
```

### Audit Trail
```
✅ Log who configured settings
✅ Log who accessed each device
✅ Log tool launched + time + duration
✅ Log success/failure of connections
✅ Retention: 90 days (configurable)
```

---

## 9. BROWSER COMPATIBILITY

✅ Chrome 90+  
✅ Firefox 88+  
✅ Edge 90+  
✅ Safari 14+  

---

## 10. RESPONSIVE DESIGN

### Desktop (1920px)
```
Full modal with all tabs visible
Tab navigation horizontal
Settings modal centered
```

### Tablet (1024px)
```
Modal adjusted to fit
Tab navigation might wrap
Scrollable if needed
```

### Mobile (375px)
```
Modal full-screen
Tab navigation vertical or scrollable
Single column layout
Buttons stack vertically
```

---

## 11. COMPONENT IMPLEMENTATION CHECKLIST

### React Components
- [ ] `RemoteAccessToolsPanel.jsx`
  - Device selector
  - Tool buttons
  - Settings icon (⚙)
  - Status indicator
  
- [ ] `RemoteSettingsModal.jsx`
  - Multi-tab container
  - Tab navigation
  
- [ ] `GeneralSettingsTab.jsx`
  - Radio buttons
  - Toggles
  - Input fields
  
- [ ] `AnyDeskSettingsTab.jsx`
  - File browser
  - Auto-detect
  - Password input
  - Test button
  
- [ ] `RustDeskSettingsTab.jsx`
  - File browser
  - Server inputs
  - Encryption key
  - Test button
  
- [ ] `VNCSettingsTab.jsx`
  - Viewer selector
  - File browser
  - Port input
  - Test button
  
- [ ] `SiteRouterTab.jsx`
  - Table component
  - Add/Edit/Delete forms
  - Test route button
  
- [ ] `SecurityTab.jsx`
  - Master key status
  - Encryption info
  - Key rotation
  
- [ ] `TestConnectionTab.jsx`
  - Status display
  - Refresh button
  - Results summary

- [ ] `DeviceRemoteConfigPanel.jsx`
  - Device info display
  - Auto-detected IDs
  - Preferred tool selector
  - Update button

---

## 12. API INTEGRATION CHECKLIST

### Frontend → Backend API Calls
```
POST /api/remote/settings/save
  ↓ Save modal configuration

GET /api/remote/detect
  ↓ Get auto-detected applications

GET /api/remote/config/{device_id}
  ↓ Get device remote configuration

POST /api/remote/config/{device_id}
  ↓ Update device remote configuration

GET /api/remote/sites
  ↓ List all sites

POST /api/remote/sites
  ↓ Create new site

PUT /api/remote/sites/{site_id}
  ↓ Update site

DELETE /api/remote/sites/{site_id}
  ↓ Delete site

POST /api/remote/launch
  ↓ Launch remote access

GET /api/remote/launch/{session_id}/status
  ↓ Get session status

POST /api/remote/test/{tool}
  ↓ Test tool connection

GET /api/remote/audit
  ↓ Get audit logs
```

---

## 13. ERROR HANDLING

### Scenarios
```
❌ Launcher service offline
   → Show warning badge on Settings icon
   → Disable launch buttons
   → Suggest restart Launcher

❌ Executable not found
   → Highlight in Test tab
   → Suggest manual path selection
   → Check installation

❌ Password decryption failed
   → Show error: "Password corrupted"
   → Suggest re-enter password

❌ Connection timeout
   → Retry up to 3 times
   → Show timeout error
   → Log failure in audit log

❌ Insufficient permissions
   → Show 403 Forbidden
   → Suggest contact admin
```

---

## 14. NOTIFICATION SYSTEM

### Success Notifications
```
✅ "Settings saved successfully"
✅ "Remote session started"
✅ "Connection test passed"
```

### Warning Notifications
```
⚠️ "Launcher service not responding"
⚠️ "Some tools not installed"
⚠️ "Password will expire in 7 days"
```

### Error Notifications
```
❌ "Failed to save settings"
❌ "Connection failed - check network"
❌ "Unauthorized - insufficient permissions"
```

---

## 15. KEYBOARD SHORTCUTS

```
Alt + S    → Open Settings modal
Esc        → Close modal / Close session
Enter      → Confirm / Save
Tab        → Navigate between fields
Ctrl + T   → Test connection
```

---

## SUMMARY

✅ **Design aligns with:**
- Gambar existing Remote Access Tools panel
- intruksi1.md specifications (section 1-17)
- Enterprise RMM patterns (NinjaOne, Atera, ConnectWise)

✅ **Key Features:**
- Settings icon (⚙) in panel header
- Multi-tab settings modal
- Auto-detection of tools
- One-click remote launch
- Encrypted password storage
- Comprehensive audit logging
- Role-based access control

✅ **Next Steps:**
1. Review design specification
2. Create React components
3. Implement backend APIs
4. Deploy Launcher service
5. Test end-to-end workflow
6. Gather user feedback
7. Iterate & improve

---

**Document Status**: ✅ UI/UX DESIGN COMPLETE  
**Last Updated**: 2026-06-17  
**Ready for**: Frontend Development Sprint

