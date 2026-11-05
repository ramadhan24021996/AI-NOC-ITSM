# SECURITY AUDIT
## OSI NOC IT AI — Security Vulnerability Assessment
**Evidence:** .env, schema.go, ingestion_server.go, api_router.py, server_ws.go, database.go  
**Method:** Static source code analysis — no penetration testing performed  
**Status:** CRITICAL issues found

---

## SEVERITY SCALE
- **P0/CRITICAL** — Immediate exploitation risk, data breach possible
- **P1/HIGH** — Serious risk, remediation within 7 days
- **P2/MEDIUM** — Exploitable under specific conditions, remediate within 30 days
- **P3/LOW** — Defense-in-depth improvement, remediate within 90 days

---

## P0/CRITICAL VULNERABILITIES

### [SEC-001] Plaintext Secrets in .env
**Severity:** P0/CRITICAL  
**File:** `.env` (root)  
**Evidence:**
```
GEMINI_API_KEY=[REDACTED_GEMINI_KEY]
OPENAI_API_KEY=[REDACTED_OPENAI_KEY]
TELEGRAM_BOT_TOKEN=[REDACTED_TELEGRAM_TOKEN]
JWT_SECRET_KEY=[REDACTED_JWT_SECRET]
DB_PASSWORD=[REDACTED_DB_PASSWORD]
```
**Risk:** Any team member with repo access can extract all API keys, DB credentials, JWT secret, and Telegram bot token.  
**Immediate Action:** Rotate ALL keys. Move to secrets manager (Vault/AWS Secrets Manager/Doppler).

---

### [SEC-002] Default Plaintext Passwords in Database Seed
**Severity:** P0/CRITICAL  
**File:** SERVER/go_core/database/schema.go  
**Evidence:**
```sql
-- schema.go lines 931-934 (seeded on schema init)
INSERT INTO rbac_users (username, password, role_name) VALUES
  ('admin',  'admin', 'admin'),
  ('noc',    'noc',   'noc_engineering'),
  ('viewer', '...',   'viewer')
ON CONFLICT (username) DO NOTHING;
```
**Risk:** Default `admin/admin` and `noc/noc` credentials allow immediate unauthorized access if not changed after first deploy.  
**Impact:** Full admin access, NOC operator access.  
**Immediate Action:** Remove seeded passwords from schema; force password change on first login.

---

### [SEC-003] Plaintext Password Storage (No Hashing)
**Severity:** P0/CRITICAL  
**File:** SERVER/go_core/database/schema.go  
**Evidence:**
```sql
CREATE TABLE rbac_users (
    username TEXT UNIQUE NOT NULL,
    password TEXT NOT NULL,  -- PLAINTEXT
    ...
```
**Risk:** If database is breached, all passwords are immediately readable.  
**Immediate Action:** Replace with bcrypt/argon2. Add migration to re-hash existing passwords.

---

### [SEC-004] JWT Secret in Environment as Plaintext
**Severity:** P0/CRITICAL  
**File:** `.env` line 16  
**Evidence:** `JWT_SECRET_KEY=94c86bf4f85e4ea7b6abf8c0d9a690e5f2a1b9f6b4c8a7e0d3f2c5e8b1a9f0d4`  
**Risk:** JWT tokens can be forged by anyone with this secret. Full authentication bypass.  
**Immediate Action:** Rotate key, move to Vault.

---

## P1/HIGH VULNERABILITIES

### [SEC-005] WebSocket CORS Bypass
**Severity:** P1/HIGH  
**File:** portal/server_ws.go  
**Evidence:**
```go
var upgrader = websocket.Upgrader{
    CheckOrigin: func(r *http.Request) bool { return true },
}
```
**Risk:** Cross-origin WebSocket connections allowed from any domain. Enables CSRF via WS and cross-origin message injection.  
**Remediation:** Implement whitelist of allowed origins.

---

### [SEC-006] Hardcoded HMAC Secret in Code
**Severity:** P1/HIGH  
**File:** SERVER/go_core/ingestion/incident_service.go  
**Evidence:**
```go
// incident_service.go (sendBypassCommandToAgent)
fallbackKey := []byte("SIAP_DISTRIBUSI_SECRET_KEY")  // HARDCODED FALLBACK
```
**Also found in:** ingestion_server.go  
**Risk:** If primary key is unavailable, hardcoded fallback key is used. HMAC tokens can be forged.

---

### [SEC-007] Python Mock Handlers Always Return SUCCESS
**Severity:** P1/HIGH  
**File:** SERVER/python_ai_core/routers/api_router.py  
**Evidence:**
```python
def _handle_execute_remediation(self, body):
    return 200, {"status": "REMEDIATION_EXECUTED", "result": "SUCCESS"}  # ALWAYS
```
**Risk:** External systems calling `/api/v1/remediations/execute` receive SUCCESS without any action executed. Silent no-op security bypass.

---

### [SEC-008] No Rate Limiting on Dashboard API
**Severity:** P1/HIGH  
**File:** portal/dashboard_server.go  
**Evidence:** No rate limiting middleware found in any portal route handler.  
**Risk:** Login endpoint vulnerable to brute-force. API DoS possible.  
**Remediation:** Implement per-IP rate limiting (golang.org/x/time/rate).

---

### [SEC-009] Database TLS Disabled (sslmode=disable)
**Severity:** P1/HIGH  
**File:** SERVER/go_core/database/database.go line 258  
**Evidence:** `sslmode=disable` in DSN string  
**Risk:** DB traffic between services is unencrypted. Man-in-the-middle within Docker network possible.  
**Remediation:** Enable sslmode=require with proper cert setup.

---

### [SEC-010] Same Key Used for Multiple Purposes
**Severity:** P1/HIGH  
**File:** docker-compose.yml, .env  
**Evidence:** `OSI_SECURITY_KEY` is used for:
- Redis password
- NATS auth token
- Fernet encryption key (Python AI)
- HMAC token auth (agents)  
**Risk:** Compromising one service exposes all. Key rotation requires all services to update simultaneously.

---

## P2/MEDIUM VULNERABILITIES

### [SEC-011] No CSRF Protection
**Severity:** P2/MEDIUM  
**File:** portal/dashboard_server.go  
**Evidence:** No CSRF middleware/token in route handlers.  
**Risk:** State-changing operations (approve incidents, create users) could be triggered via CSRF.

### [SEC-012] LDAP Credentials in .env (Plaintext)
**Severity:** P2/MEDIUM  
**File:** `.env` lines 51-55  
**Evidence:**
```
ENTERPRISE_LDAP_BIND_DN=CN=svc-osi,...
ENTERPRISE_LDAP_BIND_PASSWORD=changeme_ldap_password_2026
```
**Risk:** Default LDAP credentials and domain info exposed.

### [SEC-013] api_token Stored Plaintext in DB
**Severity:** P2/MEDIUM  
**File:** SERVER/jarvis/noc/noc_bridge.py lines 104-107  
**Evidence:** Query: `SELECT api_token FROM rbac_users WHERE role_name='superadmin'`  
API tokens stored as plaintext in user table.

### [SEC-014] LDAP Auth Stub (ldap_auth.go = 600 bytes)
**Severity:** P2/MEDIUM  
**File:** portal/ldap_auth.go  
**Evidence:** File is 600 bytes — likely placeholder stub.  
**Risk:** LDAP authentication may be incomplete; users may bypass authentication if LDAP path is reachable.

### [SEC-015] screenshot Upload Without Content Validation
**Severity:** P2/MEDIUM  
**File:** ingestion_server.go screenshot upload handler  
**Evidence:** Screenshot uploaded via POST, stored to local path — no MIME type or size validation found.  
**Risk:** Arbitrary file upload potential.

---

## P3/LOW VULNERABILITIES

### [SEC-016] Debug Mode Active (DEV_MODE=true)
**Severity:** P3/LOW**  
**File:** `.env` line 31  
**Evidence:** `DEV_MODE=true`  
**Risk:** Debug endpoints may be enabled, error messages may be verbose.

### [SEC-017] Docker Compose Mounts workspace as rw
**Severity:** P3/LOW  
**File:** docker-compose.yml line 172  
**Evidence:** `- ./:/app/workspace:rw` (entire workspace mounted read-write)  
**Risk:** Container escape could write to workspace. Prefer read-only or minimal mounts.

### [SEC-018] docker.sock Mounted in Dashboard Server
**Severity:** P3/LOW  
**File:** docker-compose.yml line 171  
**Evidence:** `- /var/run/docker.sock:/var/run/docker.sock`  
**Risk:** Container escape via Docker socket gives full host control.

---

## SECURITY SUMMARY TABLE

| ID | Issue | Severity | Files | Action |
|----|-------|----------|-------|--------|
| SEC-001 | Plaintext secrets in .env | P0/CRITICAL | .env | Rotate + use secrets manager |
| SEC-002 | Default seed passwords admin/admin | P0/CRITICAL | schema.go | Remove seed, force change |
| SEC-003 | Plaintext password storage | P0/CRITICAL | schema.go | Use bcrypt |
| SEC-004 | JWT secret in env plaintext | P0/CRITICAL | .env | Rotate + Vault |
| SEC-005 | WebSocket CORS bypass | P1/HIGH | server_ws.go | Add origin whitelist |
| SEC-006 | Hardcoded HMAC key fallback | P1/HIGH | incident_service.go | Remove fallback, env only |
| SEC-007 | Mock handlers return SUCCESS | P1/HIGH | api_router.py | Implement real handlers |
| SEC-008 | No rate limiting dashboard | P1/HIGH | dashboard_server.go | Add rate limiting |
| SEC-009 | DB sslmode=disable | P1/HIGH | database.go | Enable TLS |
| SEC-010 | Key reuse across services | P1/HIGH | docker-compose.yml | Separate keys |
| SEC-011 | No CSRF protection | P2/MEDIUM | dashboard_server.go | Add CSRF middleware |
| SEC-012 | LDAP credentials in env | P2/MEDIUM | .env | Move to Vault |
| SEC-013 | api_token plaintext in DB | P2/MEDIUM | rbac_users table | Hash tokens |
| SEC-014 | LDAP auth stub | P2/MEDIUM | ldap_auth.go | Complete or disable |
| SEC-015 | Upload without validation | P2/MEDIUM | ingestion_server.go | Add MIME + size check |
| SEC-016 | DEV_MODE=true | P3/LOW | .env | Set to false in production |
| SEC-017 | workspace:rw mount | P3/LOW | docker-compose.yml | Use :ro where possible |
| SEC-018 | docker.sock mounted | P3/LOW | docker-compose.yml | Restrict access |

---

## POSITIVE SECURITY CONTROLS FOUND

| Control | Implementation | Status |
|---------|---------------|--------|
| HMAC-SHA256 token auth for agents | ingestion_server.go verifyToken() | VERIFIED |
| JWT auth for dashboard API | portal/dashboard_server.go | VERIFIED |
| RBAC permission system | rbac_users + rbac_policies tables | VERIFIED |
| RBAC audit logs | rbac_audit_logs table | VERIFIED |
| Telemetry integrity scoring | ingestion_server.go scoreTelemetryIntegrity() | VERIFIED |
| Idempotency check | ingestion_server.go checkAndSetIdempotency() | VERIFIED |
| Agent trust scores | agent_trust_scores table | VERIFIED |
| Dead Letter Queue | dlq_hybrid table | VERIFIED |
| Agent version enforcement | ingestion_server.go isVersionAllowed() | VERIFIED |
| Immutable audit log with hash chain | immutable_audit_log table | VERIFIED |
| Fernet encryption for LLM API keys | llm_router.py decrypt_key() | VERIFIED |
| HITL gate for high-risk actions | hitl_authorization_gate.py | VERIFIED |
| Circuit breaker for AI execution | execution_orchestrator.py | VERIFIED |
| Policy matrix for action governance | execution_orchestrator.py POLICY_MATRIX | VERIFIED |
