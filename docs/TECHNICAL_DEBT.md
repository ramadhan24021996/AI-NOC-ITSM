# TECHNICAL DEBT CATALOG
## OSI NOC IT AI — Technical Debt Registry
**Evidence:** Full source code audit  
**Rating:** CRITICAL / HIGH / MEDIUM / LOW

---

## TECHNICAL DEBT OVERVIEW

| Category | Critical | High | Medium | Low |
|----------|---------|------|--------|-----|
| Security | 4 | 3 | 3 | 2 |
| Architecture | 0 | 4 | 3 | 2 |
| Code Quality | 0 | 2 | 5 | 3 |
| Testing | 0 | 2 | 3 | 1 |
| Performance | 0 | 1 | 2 | 2 |
| **Total** | **4** | **12** | **16** | **10** |

---

## CRITICAL DEBT

### [TD-C01] Mock API Handlers in Production Code
**Category:** Architecture  
**File:** SERVER/python_ai_core/routers/api_router.py  
**Evidence:**
```python
def _handle_analyze(self, body):
    return 200, {"root_cause_hypothesis": f"Elevated latency on {device_name}", "confidence": 0.94}

def _handle_execute_remediation(self, body):
    return 200, {"status": "REMEDIATION_EXECUTED", "result": "SUCCESS"}  # Always

def _handle_rag_query(self, body):
    return 200, {"results": [{"doc_id": "sop-dns-01", "snippet": "If DNS..."}]}  # Hardcoded
```
**Impact:** External systems receive false success responses. Remediation appears executed but nothing happens.  
**Effort to Fix:** MEDIUM (2-3 days) — connect to real WorkflowOrchestrator + RAGEngine  
**Risk if Not Fixed:** CRITICAL — system appears to work but silent no-ops

---

### [TD-C02] Plaintext Password Storage
**Category:** Security  
**File:** SERVER/go_core/database/schema.go  
**Evidence:** `password TEXT NOT NULL` + `INSERT ... VALUES ('admin', 'admin', ...)`  
**Impact:** Full credential exposure on DB breach  
**Effort to Fix:** MEDIUM (1-2 days) — Add bcrypt, migration script  
**Risk if Not Fixed:** CRITICAL — GDPR/compliance violation, data breach

---

### [TD-C03] All Secrets in .env Plaintext
**Category:** Security  
**File:** .env  
**Evidence:** OPENAI_KEY, GEMINI_KEY, JWT_SECRET, TELEGRAM_TOKEN, DB_PASSWORD all in .env  
**Impact:** Any repo access = full credential exposure  
**Effort to Fix:** LOW-MEDIUM (2-3 days) — Move to Vault/Doppler  
**Risk if Not Fixed:** CRITICAL

---

### [TD-C04] NATS Incident Events Without Persistence
**Category:** Reliability  
**File:** SERVER/go_core/ingestion/incident_service.go  
**Evidence:**
```go
natsConn.Publish("incident.site.{id}.escalate.request", payload)  // No JetStream ack
```
**Impact:** Escalation events silently lost if Python AI Core is restarting  
**Effort to Fix:** LOW (1 day) — Use natsJS.Publish() + configure stream  
**Risk if Not Fixed:** HIGH — Incidents escalated but Python AI never processes

---

## HIGH DEBT

### [TD-H01] Go AI Engine — Only 4 Rule-Based Predcodes
**Category:** Architecture  
**File:** SERVER/go_core/ai/ai_engine.go  
**Evidence:** 4 hardcoded cases in CorrelateIncidents()  
**Impact:** Cannot classify incidents outside 4 predefined categories  
**Effort to Fix:** HIGH (2-4 weeks) — Integrate LLM in Go or defer to Python  

---

### [TD-H02] RetrainClassifier Returns Mocked Metrics
**Category:** Code Quality  
**File:** SERVER/go_core/ai/ai_engine.go  
**Evidence:**
```go
// line 116-130
time.Sleep(100 * time.Millisecond)  // Simulated
return ClassifierMetrics{F1Score: 0.985, Accuracy: 0.991, ...}  // MOCKED
```
**Impact:** Model quality claims are false. CI/CD may pass incorrectly on metrics.  
**Effort to Fix:** HIGH — requires real training infrastructure

---

### [TD-H03] Python NATS Subscriber Not Verified
**Category:** Architecture  
**Files:** SERVER/python_ai_core/, governance/execution_orchestrator.py  
**Evidence:** nc parameter passed in constructor but initialization point not found  
**Impact:** Python AI Core may not process incident events from NATS  
**Effort to Fix:** LOW-MEDIUM (1-2 days) — trace and verify subscriber

---

### [TD-H04] State Divergence: Go fleet_incidents vs Python incident_states
**Category:** Architecture  
**Files:** incident_service.go, execution_orchestrator.py  
**Evidence:** Both maintain separate state with no sync mechanism  
**Impact:** Operator sees different state in Go dashboard vs Python AI tools  
**Effort to Fix:** MEDIUM (3-5 days) — Define single source of truth

---

### [TD-H05] No Rate Limiting on Dashboard API
**Category:** Security  
**File:** portal/dashboard_server.go  
**Evidence:** No rate limit middleware found  
**Effort to Fix:** LOW (half-day) — golang.org/x/time/rate

---

### [TD-H06] WebSocket CORS Bypass
**Category:** Security  
**File:** portal/server_ws.go  
**Evidence:** `CheckOrigin: func(r *http.Request) bool { return true }`  
**Effort to Fix:** LOW (1 hour) — Add origin whitelist

---

### [TD-H07] No Post-Mortem Auto-Generation
**Category:** Feature Gap  
**Files:** incident_service.go ResolveIncident(), governance/post_mortem_generator.py  
**Evidence:** post_mortem_generator.py exists but not called from ResolveIncident()  
**Effort to Fix:** MEDIUM (2-3 days) — Wire Python PostMortemGenerator to ResolveIncident

---

### [TD-H08] No Knowledge Base Learning from Resolved Incidents
**Category:** Feature Gap  
**Files:** incident_service.go, knowledge/knowledge_auto_builder.py  
**Evidence:** knowledge_auto_builder.py exists but no call from resolution path  
**Effort to Fix:** MEDIUM (3-5 days) — Wire feedback loop

---

### [TD-H09] Missing Test Coverage
**Category:** Testing  
**Files:** All — no test files found in ingestion/, ai/, python_ai_core/core/  
**Evidence:** No *_test.go or test_*.py files in key directories  
**Effort to Fix:** HIGH (2-4 weeks) — Write unit + integration tests

---

### [TD-H10] Go Logging Using fmt.Printf (Unstructured)
**Category:** Observability  
**Files:** ingestion_server.go, incident_service.go, ai_engine.go  
**Evidence:** All logs via fmt.Printf() — not filterable, not JSON  
**Effort to Fix:** MEDIUM (3-5 days) — Replace with slog/zap

---

### [TD-H11] Same OSI_SECURITY_KEY for 4 Different Purposes
**Category:** Security  
**File:** docker-compose.yml  
**Evidence:** Redis password, NATS auth, Fernet encryption, HMAC fallback all use OSI_SECURITY_KEY  
**Effort to Fix:** MEDIUM (2-3 days) — Separate keys, rotate

---

### [TD-H12] No Prometheus Metrics Export
**Category:** Observability  
**File:** ingestion_server.go /metrics endpoint  
**Evidence:** Custom JSON format, not Prometheus  
**Effort to Fix:** LOW-MEDIUM (1-2 days) — Use prometheus/client_golang

---

## MEDIUM DEBT (Summary)

| ID | Issue | File | Effort |
|----|-------|------|--------|
| TD-M01 | LDAP auth stub incomplete | portal/ldap_auth.go (600 bytes) | HIGH |
| TD-M02 | DB read replica code present but disabled | database.go L269-274 | LOW |
| TD-M03 | fleet_evidence.s3_path misleading name | schema.go | LOW |
| TD-M04 | GORM SQL logger at INFO level always | database.go | LOW |
| TD-M05 | Python health check static status | api_router.py | LOW |
| TD-M06 | No CSRF protection | dashboard_server.go | MEDIUM |
| TD-M07 | Agent push no retry if device offline | incident_service.go | MEDIUM |
| TD-M08 | Screenshot timeout 4s too short | incident_service.go L249 | LOW |
| TD-M09 | Telegram failure hard-errors escalation | incident_service.go L319-323 | LOW |
| TD-M10 | n8n integration not connected to incident lifecycle | n8n_dispatcher.py | MEDIUM |
| TD-M11 | DB connection limit 50 — may exhaust under load | database.go L317 | MEDIUM |
| TD-M12 | LoRA training pipeline is placeholder | lora_training_pipeline_orchestrator.py | VERY HIGH |
| TD-M13 | incident_events.incident_id is TEXT not FK | schema.go | MEDIUM |
| TD-M14 | NATS monitoring port 8222 not secured (localhost only - good) | docker-compose.yml | LOW |
| TD-M15 | No backup/restore procedure | Not found anywhere | HIGH |

---

## LOW DEBT (Summary)

| ID | Issue | File | Effort |
|----|-------|------|--------|
| TD-L01 | pprof always running in production | hardening.StartPprofServer() | LOW |
| TD-L02 | docker.sock mounted in dashboard-server | docker-compose.yml | MEDIUM |
| TD-L03 | workspace:rw mount | docker-compose.yml | LOW |
| TD-L04 | DEV_MODE=true in .env | .env | TRIVIAL |
| TD-L05 | MaxOpenConns(50) may exhaust at scale | database.go | MEDIUM |
| TD-L06 | No automated DB vacuum tuning | Not configured | LOW |
| TD-L07 | Missing NATS healthcheck in docker-compose | docker-compose.yml | TRIVIAL |
| TD-L08 | Cognitive memory SQLite at root level | cognitive_memory.db | LOW |
| TD-L09 | WS ReadBufferSize=1024 may be too small | server_ws.go | LOW |
| TD-L10 | No Kubernetes manifests verified | manifests/ | MEDIUM |

---

## DEBT PAYDOWN ROADMAP

### Sprint 1 (Week 1-2) — Critical Security
- [x] Plan only — must be executed
- [ ] Fix password hashing (bcrypt)
- [ ] Remove .env secrets → Vault/Doppler
- [ ] Remove default seed passwords
- [ ] Add rate limiting to dashboard API
- [ ] Fix WebSocket CORS

### Sprint 2 (Week 3-4) — Core Features
- [ ] Fix Python mock API handlers
- [ ] Verify NATS subscriber in Python AI
- [ ] Migrate incident events to JetStream
- [ ] Wire post-mortem auto-generation

### Sprint 3 (Week 5-6) — Quality
- [ ] Structured logging (slog/zap)
- [ ] Prometheus metrics exporter
- [ ] Unit test coverage >70%
- [ ] CSRF protection

### Sprint 4 (Week 7-8) — AI Enhancement
- [ ] Knowledge feedback loop from resolved incidents
- [ ] Go AI LLM augmentation (via Python)
- [ ] State sync between Go and Python
- [ ] SLA breach alerting
