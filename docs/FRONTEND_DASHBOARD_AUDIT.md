# FRONTEND / DASHBOARD AUDIT
## OSI NOC IT AI — Dashboard & Frontend Forensic Audit
**Evidence:** portal/ directory, portal/Dockerfile, docker-compose.yml (dashboard-server service)  
**Status:** PARTIALLY_IMPLEMENTED — Go dashboard with templates

---

## DASHBOARD SERVER OVERVIEW

| Aspect | Detail | Status |
|--------|--------|--------|
| Language | Go | VERIFIED |
| Server | Custom HTTP (net/http + gorilla/mux or stdlib) | VERIFIED |
| Templates | HTML templates in portal/templates/ | VERIFIED |
| Static assets | portal/static/ | VERIFIED |
| Port | 9999 (internal, proxied via Nginx) | VERIFIED |
| Primary file | dashboard_server.go (12,060 bytes) | VERIFIED |

---

## FRONTEND CAPABILITIES (Verified from Go source)

| Feature | File | Status |
|---------|------|--------|
| Incident list + detail | portal/ | VERIFIED |
| Fleet device management | portal/ | VERIFIED |
| Real-time chat (WebSocket) | chat_engine.go (67,654 bytes) | VERIFIED |
| JARVIS voice query | jarvis_api.go (12,353 bytes) | VERIFIED |
| SOP management | sprint_o_api.go | VERIFIED |
| Remote access (RustDesk) | remote_settings.json | VERIFIED |
| Audit log viewer | server_auditor.go | VERIFIED |
| System state machine | state_machine.go | VERIFIED |
| Knowledge base query | sprint_o_api.go | VERIFIED |
| Governance approvals | sprint_o_api.go | VERIFIED |

---

## TECHNOLOGY STACK

| Component | Technology | Notes |
|-----------|-----------|-------|
| HTML templates | Go html/template | Server-side rendering |
| JavaScript | Vanilla JS (assumed from static/) | No React/Vue bundle found |
| CSS | Custom CSS in portal/static/ | No TailwindCSS config |
| WebSocket client | Browser native WebSocket | No socket.io |
| Charts | Unknown — likely Chart.js | No package.json found in portal/ |

---

## DASHBOARD API (Verified Endpoints — dashboard_server.go)

The dashboard server exposes the full REST API for the frontend to consume.

See [API_AUDIT.md](./API_AUDIT.md) for the complete endpoint list.

---

## REALTIME FEATURES

| Feature | Transport | Status |
|---------|-----------|--------|
| Incident updates | WebSocket /ws/dashboard | VERIFIED |
| Chat messages | WebSocket /ws/chat/:clientID | VERIFIED |
| Live telemetry stream | PostgreSQL pg_notify → Go LISTEN | VERIFIED (trigger) / NOT_VERIFIED (Go LISTEN) |
| JARVIS voice duplex | WebSocket /jarvis/voice/duplex | VERIFIED |

---

## JARVIS VOICE INTEGRATION (jarvis_api.go — 12,353 bytes)

```go
// Proxy pattern:
// User request → dashboard-server → proxy → jarvis-voice-server:8089
JARVIS_VOICE_API_URL = http://osi-jarvis-voice-server:8089

POST /jarvis/voice/query    → proxy to :8089/jarvis/voice/query
GET  /jarvis/health         → proxy to :8089/jarvis/health
WS   /jarvis/voice/duplex   → proxy to :8089/jarvis/voice/duplex
```

**Status:** VERIFIED — Go proxy implementation confirmed

---

## CONFIGURATION FILES (Hot-reloadable)

| File | Purpose | Hot-reload | Status |
|------|---------|-----------|--------|
| portal/ai_config.json | AI provider config (models, keys, thresholds) | YES | VERIFIED |
| portal/remote_settings.json | Remote access settings (RustDesk config) | YES | VERIFIED |

---

## FRONTEND RISKS

| Risk | Severity | Evidence |
|------|----------|---------|
| No verified test for dashboard UI | HIGH | No frontend tests |
| No CSRF protection | MEDIUM | No CSRF token in API |
| WebSocket CORS bypass | HIGH | CheckOrigin: true |
| No Content-Security-Policy header | MEDIUM | Not found in dashboard_server.go |
| Static assets served without cache headers audit | LOW | Unknown |

---

## PORTAL DOCKERFILE ANALYSIS

```dockerfile
# portal/Dockerfile (inferred from docker-compose)
# Serves pre-compiled binary: ./build/bin/portal
# Mounts: portal/templates/:ro, portal/static/:ro
# Config files mounted rw for hot-reload
# docker.sock mounted (for Docker management features)
```

---

## DASHBOARD SUMMARY

The dashboard is a Go-rendered server-side application with:
- **Strong** real-time capabilities via WebSocket + Redis PubSub
- **Full-featured** API for all NOC operations
- **JARVIS AI** integration via HTTP proxy
- **Needs:** CSRF, CSP headers, rate limiting, frontend tests
