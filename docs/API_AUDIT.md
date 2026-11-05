# API AUDIT
## OSI NOC IT AI — REST API Forensic Audit
**Evidence:** portal/dashboard_server.go, portal/jarvis_api.go, portal/sprint_o_api.go,  
SERVER/python_ai_core/routers/api_router.py, SERVER/go_core/ingestion/ingestion_server.go  
**Status:** VERIFIED — source code analysis

---

## API SERVERS

| Server | Language | Port | Auth | Status |
|--------|----------|------|------|--------|
| Dashboard Server (portal) | Go | 9999 (internal) | JWT Bearer | VERIFIED |
| Ingestion Server (go_core) | Go | 18800/18802 | HMAC Token | VERIFIED |
| JARVIS Voice Server (jarvis) | Python FastAPI | 8089 (internal) | API Token | VERIFIED |
| Python AI Core REST | Python | 18800 proxy or standalone | Auth Guard token | PARTIALLY_IMPLEMENTED |

---

## GO DASHBOARD API (portal/) — PRIMARY API

### Authentication Endpoints

| Method | Path | Auth | Status | Notes |
|--------|------|------|--------|-------|
| POST | /api/login | NONE | VERIFIED | JWT + role check |
| POST | /api/logout | JWT | VERIFIED | Session invalidation |
| GET | /api/me | JWT | VERIFIED | Current user info |
| PUT | /api/me/settings | JWT | VERIFIED | Dashboard settings |

### Incident API Endpoints

| Method | Path | Auth | Status | Notes |
|--------|------|------|--------|-------|
| GET | /api/incidents | JWT | VERIFIED | List active incidents |
| GET | /api/incidents/:id | JWT | VERIFIED | Single incident detail |
| POST | /api/incidents | JWT | VERIFIED | Create incident manually |
| PUT | /api/incidents/:id | JWT+RBAC | VERIFIED | Update incident |
| DELETE | /api/incidents/:id | JWT+RBAC(admin) | VERIFIED | Delete incident |
| POST | /api/incidents/:id/escalate | JWT | VERIFIED | Escalate to NOC |
| POST | /api/incidents/:id/resolve | JWT | VERIFIED | Resolve incident |
| GET | /api/incidents/:id/rca | JWT | VERIFIED | Get RCA for incident |

### Fleet Management API

| Method | Path | Auth | Status |
|--------|------|------|--------|
| GET | /api/fleet/devices | JWT | VERIFIED |
| GET | /api/fleet/sites | JWT | VERIFIED |
| POST | /api/fleet/sites | JWT+RBAC(admin) | VERIFIED |
| GET | /api/fleet/printers | JWT | VERIFIED |
| GET | /api/fleet/usbs | JWT | VERIFIED |
| PUT | /api/fleet/devices/:name/approve | JWT+RBAC(admin) | VERIFIED |

### Chat API

| Method | Path | Auth | Status | Notes |
|--------|------|------|--------|-------|
| GET | /api/chat/sessions | JWT | VERIFIED | All chat sessions |
| GET | /api/chat/sessions/:id/messages | JWT | VERIFIED | Session messages |
| POST | /api/chat/sessions/:id/messages | JWT | VERIFIED | Send operator message |
| WS | /ws/chat/:clientID | None (WebSocket) | VERIFIED | Real-time chat stream |

### Telemetry / Monitoring API

| Method | Path | Auth | Status |
|--------|------|------|--------|
| GET | /api/telemetry/:device | JWT | VERIFIED |
| GET | /api/devices | JWT | VERIFIED |
| GET | /api/health | NONE | VERIFIED |
| GET | /api/audit | JWT+RBAC | VERIFIED |

### JARVIS AI API (portal/jarvis_api.go)

| Method | Path | Auth | Status | Notes |
|--------|------|------|--------|-------|
| POST | /jarvis/voice/query | JWT | VERIFIED | Proxied to JARVIS Voice Server :8089 |
| GET | /jarvis/health | NONE | VERIFIED | Health check |
| WS | /jarvis/voice/duplex | JWT (ws) | VERIFIED | Voice duplex WebSocket |
| POST | /api/ai/orchestrate | JWT | VERIFIED | AI workflow orchestration |
| POST | /api/ai/rca | JWT | VERIFIED | RCA trigger |

### Sprint O API (portal/sprint_o_api.go — 12868 bytes)

| Method | Path | Auth | Status |
|--------|------|------|--------|
| GET | /api/sop/list | JWT | VERIFIED |
| GET | /api/sop/:id | JWT | VERIFIED |
| POST | /api/sop | JWT+RBAC | VERIFIED |
| GET | /api/kb/query | JWT | VERIFIED |
| POST | /api/kb/query | JWT | VERIFIED |
| GET | /api/governance/approvals | JWT+RBAC | VERIFIED |
| POST | /api/governance/approvals/:id/approve | JWT+RBAC | VERIFIED |

### Remote Access API

| Method | Path | Auth | Status |
|--------|------|------|--------|
| POST | /api/remote/rustdesk | JWT+RBAC | VERIFIED |
| GET | /api/remote/sessions | JWT | VERIFIED |

---

## PYTHON AI CORE REST API (api_router.py)

### CRITICAL FINDING: MOCK IMPLEMENTATIONS

| Endpoint | Method | Path | Auth | Implementation Status |
|----------|--------|------|------|----------------------|
| Health | GET | /api/v1/health | NONE | VERIFIED — live DB check |
| Incidents | GET | /api/v1/incidents | Bearer Token | VERIFIED — queries DB |
| Analyze | POST | /api/v1/incidents/analyze | Bearer Token | **MOCK — hardcoded response** |
| Execute Remediation | POST | /api/v1/remediations/execute | Bearer Token | **MOCK — always returns SUCCESS** |
| RAG Query | POST | /api/v1/rag/query | Bearer Token | **MOCK — hardcoded DNS snippet** |
| Models | GET | /api/v1/models | Bearer Token | **MOCK — static list** |
| Orchestrate | POST | /api/v1/orchestrate | Bearer Token | VERIFIED — calls WorkflowOrchestrator |

#### Evidence: MOCK Implementation in _handle_analyze()
```python
# api_router.py lines 196-204
def _handle_analyze(self, body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    device_name = body.get("device_name", "UNKNOWN")
    return 200, {
        "status": "ANALYSIS_SCHEDULED",
        "device_name": device_name,
        "root_cause_hypothesis": f"Elevated latency detected on {device_name}",  # HARDCODED
        "confidence": 0.94,                                                         # HARDCODED
        "recommended_action": "RESTART_SERVICE"                                     # HARDCODED
    }
```

#### Evidence: MOCK Implementation in _handle_execute_remediation()
```python
# api_router.py lines 206-215
def _handle_execute_remediation(self, body: Dict[str, Any]) -> Tuple[int, Dict[str, Any]]:
    incident_id = body.get("incident_id")
    action = body.get("action", "RESTART_SERVICE")
    return 200, {
        "status": "REMEDIATION_EXECUTED",          # ALWAYS SUCCESS
        "result": "SUCCESS",                         # ALWAYS SUCCESS
        "rollback_snapshot_id": "snap-9901-pre-exec"  # HARDCODED
    }
```

---

## INGESTION SERVER HTTP API (ingestion_server.go)

The ingestion server multiplexes TCP and HTTP on the same port 18800 using byte-peek protocol detection.

| Method | Path | Auth | Status | Notes |
|--------|------|------|--------|-------|
| GET | /health | HMAC/None | VERIFIED | Basic health response |
| POST | /telemetry | HMAC Token | VERIFIED | Main telemetry ingestion |
| POST | /screenshot/upload | HMAC | VERIFIED | Screenshot evidence upload |
| POST | /agent/register | HMAC | VERIFIED | Agent registration |
| GET | /kb | None | VERIFIED | Knowledge base sync |
| GET | /config | HMAC | VERIFIED | Config distribution to agents |
| GET | /metrics | None | VERIFIED | Internal metrics |

---

## AUTHENTICATION IMPLEMENTATION

### JWT (Dashboard Server)
```
POST /api/login
  → Check rbac_users table: username + password (PLAINTEXT COMPARISON)
  → On match: generate JWT (HS256, secret: JWT_SECRET_KEY env)
  → Response: { token: "jwt...", role: "admin", expires_at: ... }

Protected endpoints:
  → Extract Authorization: Bearer {token}
  → Parse JWT, validate signature + expiry
  → Check RBAC permissions from rbac_policies table
  → Log to rbac_audit_logs
```

### HMAC Token (Ingestion Server)
```
Agent sends: { agent: "PC_NAME", timestamp: "ISO8601", token: "HMAC_HEX", ... }
Server verifies: HMAC-SHA256(agent_name + ":" + timestamp, security_key)
Tolerance: ±5 minutes timestamp drift
```

---

## RATE LIMITING

| Server | Rate Limit | Implementation | Status |
|--------|-----------|----------------|--------|
| Ingestion Server | Per-IP sliding window | checkRateLimit() — in-memory | VERIFIED |
| Dashboard Server | Not implemented | None found | NOT_FOUND |
| Python AI REST | Not implemented | None found | NOT_FOUND |

---

## VALIDATION SUMMARY

| API Component | Input Validation | Auth | Rate Limit | Error Response | Status |
|---------------|-----------------|------|------------|----------------|--------|
| Dashboard REST | Partial (some endpoints) | JWT | NO | JSON error | PARTIAL |
| Ingestion TCP | Full schema + HMAC + integrity | HMAC | YES | JSON error | VERIFIED |
| Python AI REST | Basic JSON parse only | Bearer Token | NO | JSON error | PARTIAL |
| JARVIS API | Request validation | JWT | NO | JSON error | PARTIAL |

---

## API SECURITY RISKS

| Risk | Severity | Endpoint | Evidence |
|------|----------|---------|---------|
| Dashboard API has no rate limiting | HIGH | All /api/ | No rate limit code in dashboard_server.go |
| Python REST mock handlers return SUCCESS regardless of input | HIGH | /api/v1/remediations/execute | api_router.py line 210 |
| JWT secret in .env as plaintext | CRITICAL | All auth | .env line 16 |
| No CSRF protection on state-changing endpoints | MEDIUM | POST/PUT/DELETE | No CSRF middleware found |
| No request size limit on ingestion | MEDIUM | :18800 | buf := make([]byte, 8192) — per read, but no total limit |
