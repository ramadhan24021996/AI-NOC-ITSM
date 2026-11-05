# AUDIT EVIDENCE INDEX
## OSI NOC IT AI — Full Evidence Registry
**Purpose:** Maps every audit finding to exact file + line + function/class for verifiability  
**Status:** VERIFIED — all evidence from source code read during audit

---

## EVIDENCE FORMAT
`[FINDING_ID] | [STATUS] | [FILE] | [LINE/RANGE] | [CLASS/FUNCTION] | [EVIDENCE]`

---

## INGESTION SERVER EVIDENCE

| Finding | Status | File | Lines | Function | Evidence |
|---------|--------|------|-------|----------|---------|
| TCP listener on port 18800 | VERIFIED | ingestion_server.go | 414 | startListenerPipeline | `startListenerPipeline(18800, "OPERATIONAL_WORKER_%d")` |
| TCP listener on port 18802 | VERIFIED | ingestion_server.go | 417 | startListenerPipeline | `startListenerPipeline(18802, "REMEDIATION_RCA_WORKER_%d")` |
| HTTP/TCP multiplexing via byte-peek | VERIFIED | ingestion_server.go | 481-501 | handleTCPConnection | `if isHTTP → httpDispatcher.conns <- bufferedConn` |
| NATS JetStream init | VERIFIED | ingestion_server.go | 318-337 | StartIngestionServer | `js, jsErr := natsConn.JetStream()` |
| Redis connection | VERIFIED | ingestion_server.go | 303-314 | StartIngestionServer | `redisClient = redis.NewClient(...)` |
| Worker pool: 4 metric workers | VERIFIED | ingestion_server.go | 362-368 | StartIngestionServer | `for i := 1; i <= 4; i++ { metricProcessorWorker(id) }` |
| verifyQueue capacity 20000 | VERIFIED | ingestion_server.go | 167 | package vars | `var verifyQueue = make(chan verifyTask, 20000)` |
| metricQueue capacity 20000 | VERIFIED | ingestion_server.go | 97 | package vars | `metricQueue = make(chan TelemetryItem, 20000)` |
| Schema validation gate | VERIFIED | ingestion_server.go | 615-622 | processVerifyTask | `if !validateTelemetrySchema(item) → DLQ` |
| HMAC token verification | VERIFIED | ingestion_server.go | 624-632 | processVerifyTask | `if !verifyToken(item.Agent, item.Timestamp, item.Token)` |
| Integrity scoring gate 0.40 threshold | VERIFIED | ingestion_server.go | 639-663 | processVerifyTask | `case integrityScore < 0.40: HARD REJECT` |
| Idempotency check | VERIFIED | ingestion_server.go | 665-670 | processVerifyTask | `if checkAndSetIdempotency(&item) → DUPLICATE_IGNORED` |
| Alert type routing | VERIFIED | ingestion_server.go | 681-694 | processVerifyTask | `alertTypes := map[string]bool{"service_alert": true, ...}` |
| OTel context injection | VERIFIED | ingestion_server.go | 581 | processVerifyTask | `InjectOTelContext(&item)` |
| Agent version check | VERIFIED | ingestion_server.go | 590-597 | processVerifyTask | `if !isVersionAllowed(item)` |

---

## INCIDENT SERVICE EVIDENCE

| Finding | Status | File | Lines | Function | Evidence |
|---------|--------|------|-------|----------|---------|
| Incident creation INSERT | VERIFIED | incident_service.go | 113 | TriggerIncidentWorkflow | `database.DB.Exec("INSERT INTO fleet_incidents ...")` |
| event_sourced INSERT | VERIFIED | incident_service.go | 124 | TriggerIncidentWorkflow | `database.DB.Exec("INSERT INTO incident_events ...")` |
| Initial chat message | VERIFIED | incident_service.go | 129 | TriggerIncidentWorkflow | `DefaultChatService.SaveChatMessage(...)` |
| AI analysis call | VERIFIED | incident_service.go | 138 | TriggerIncidentWorkflow | `DefaultAIAnalysisService.Analyze(description, "")` |
| Knowledge base match | VERIFIED | incident_service.go | 153 | TriggerIncidentWorkflow | `knowledge.GlobalEngine.Match(queryText)` |
| Agent push SHOW_NOTIFICATION | VERIFIED | incident_service.go | 214 | TriggerIncidentWorkflow goroutine | `sendBypassCommandToAgent(..., SHOW_NOTIFICATION...)` |
| Agent push SHOW_CHAT | VERIFIED | incident_service.go | 228 | TriggerIncidentWorkflow goroutine | `sendBypassCommandToAgent(..., SHOW_CHAT...)` |
| Screenshot request | VERIFIED | incident_service.go | 239 | TriggerIncidentWorkflow goroutine | `SendWSCommand(clientID, "capture_screenshot", ...)` |
| Screenshot 4s timeout | VERIFIED | incident_service.go | 249 | TriggerIncidentWorkflow goroutine | `time.After(4 * time.Second)` |
| NATS escalation publish | VERIFIED | incident_service.go | 290 | EscalateIncident | `natsConn.Publish("incident.site.{id}.escalate.request", ...)` |
| Telegram escalation alert | VERIFIED | incident_service.go | 319 | EscalateIncident | `DefaultTelegramService.SendIncidentAlert(...)` |
| NATS close publish | VERIFIED | incident_service.go | 360 | ResolveIncident | `natsConn.Publish("incident.site.{id}.close.request", ...)` |
| Self-healing Telegram | VERIFIED | incident_service.go | 375 | ResolveIncident | `DefaultTelegramService.SendIncidentAlert("Self-Healing SUCCESS")` |
| Hardcoded HMAC fallback key | VERIFIED | incident_service.go | ~200-204 | sendBypassCommandToAgent | `fallbackKey := []byte("SIAP_DISTRIBUSI_SECRET_KEY")` |
| Cooldown check (2 min) | VERIFIED | incident_service.go | 84-90 | TriggerIncidentWorkflow | `fleet_incidents WHERE created_at > NOW() - INTERVAL '2 minutes'` |

---

## AI ENGINE EVIDENCE

| Finding | Status | File | Lines | Function | Evidence |
|---------|--------|------|-------|----------|---------|
| Go AI uses NO LLM | VERIFIED | ai_engine.go | 79 (comment) | DiagnoseIncident | Comment: "True Semantic Vector Search is handled by Python AI Core" |
| CorrelateIncidents keyword matching | VERIFIED | ai_engine.go | 38-72 | CorrelateIncidents | Keyword scan for gateway/router/database/agent |
| QueryRAG uses LIKE not vector | VERIFIED | ai_engine.go | ~140-160 | QueryRAG | `db.Where("symptoms LIKE ? OR title LIKE ?", ...)` |
| RetrainClassifier MOCK | VERIFIED | ai_engine.go | 116-130 | RetrainClassifier | `time.Sleep(100ms)` + hardcoded `F1Score: 0.985` |
| Confidence math formula | VERIFIED | ai_engine.go | ~400-500 | DiagnoseIncident | telemetry(30)+historical(30)+dependency(20)+temporal(20) |
| Fleet correlation 24h window | VERIFIED | ai_engine.go | ~500-560 | CheckFleetCorrelation | `fleet_incidents WHERE created_at > NOW() - INTERVAL '24 hours'` |
| 4 predcodes only | VERIFIED | ai_engine.go | ~38-72 | CorrelateIncidents | NETWORK_GATEWAY_DOWN, DATABASE_POOL_EXHAUSTED, CLIENT_SERVICE_STOPPED, UNKNOWN_ANOMALY |

---

## DATABASE EVIDENCE

| Finding | Status | File | Lines | Class/Table | Evidence |
|---------|--------|------|-------|-------------|---------|
| Password TEXT NOT NULL | VERIFIED | schema.go | ~928 | rbac_users DDL | `password TEXT NOT NULL` |
| Default admin/admin seed | VERIFIED | schema.go | 931-934 | rbac_users seed | `INSERT INTO rbac_users VALUES ('admin', 'admin', ...)` |
| sslmode=disable | VERIFIED | database.go | 258 | InitDatabase | `sslmode=disable TimeZone=UTC` |
| MaxOpenConns 50 | VERIFIED | database.go | 317 | InitDatabase | `sqlDB.SetMaxOpenConns(50)` |
| pgvector extension | VERIFIED | docker-compose.yml | 28 | postgres service | `image: pgvector/pgvector:pg15` |
| knowledge_vectors embedding vector(768) | VERIFIED | schema.go | ~820-850 | CREATE TABLE | `embedding vector(768)` |
| HNSW index on embeddings | VERIFIED | schema.go | ~850-855 | CREATE INDEX | `USING hnsw (embedding vector_cosine_ops)` |
| advisory lock migration | VERIFIED | schema.go | 26 | InitializeSchema | `SELECT pg_advisory_xact_lock(74283921)` |
| 84 telemetry partitions | VERIFIED | schema.go | ~300-600 | CREATE TABLE | telemetry_logs PARTITION BY RANGE (timestamp) |
| immutable audit hash chain | VERIFIED | schema.go | ~1100-1150 | immutable_audit_log | `prev_hash TEXT NOT NULL, hash_signature TEXT NOT NULL` |
| MIGRATE_DB guard | VERIFIED | database.go | 279 | InitDatabase | `if getEnv("MIGRATE_DB", "false") == "true"` |

---

## PYTHON AI CORE EVIDENCE

| Finding | Status | File | Lines | Class/Function | Evidence |
|---------|--------|------|-------|----------------|---------|
| _handle_analyze MOCK | VERIFIED | api_router.py | 196-204 | ApiRouter._handle_analyze | Hardcoded response + 0.94 confidence |
| _handle_execute_remediation MOCK | VERIFIED | api_router.py | 206-215 | ApiRouter._handle_execute_remediation | Always returns SUCCESS |
| _handle_rag_query MOCK | VERIFIED | api_router.py | 217-228 | ApiRouter._handle_rag_query | Static DNS snippet hardcoded |
| WorkflowOrchestrator NATS none | VERIFIED | workflow_orchestrator.py | 18-55 | WorkflowOrchestrator.__init__ | No NATS connection in constructor |
| 9 LLM providers | VERIFIED | llm_router.py | 25-35 | OPENAI_COMPATIBLE_PROVIDERS | 9-entry dict |
| Fernet decrypt for API keys | VERIFIED | llm_router.py | 37-51 | decrypt_key | `f = Fernet(sec_key.encode())` |
| Multi-key rotation pool | VERIFIED | llm_router.py | 53-72 | parse_keys | comma-split parsing |
| Token circuit breaker 50k | VERIFIED | llm_router.py | 20 | module vars | `MAX_TOKENS_PER_INCIDENT = 50000` |
| AuthGuard token validation | VERIFIED | api_router.py | 90-102 | ApiRouter.dispatch | `auth_res = self._auth_guard.authenticate_request(...)` |
| PlannerCriticConsensus optional load | VERIFIED | workflow_orchestrator.py | 36-42 | WorkflowOrchestrator.__init__ | try/except import pattern |
| GovernanceExecutionOrchestrator circuit breaker | VERIFIED | execution_orchestrator.py | 17 | module vars | `CircuitBreaker(failure_threshold=3, recovery_timeout_sec=30)` |
| Policy matrix | VERIFIED | execution_orchestrator.py | 31-38 | POLICY_MATRIX | Full dict: NOTIFY/TICKET/RESTART/DB_MIGRATION/FIREWALL |

---

## SECURITY EVIDENCE

| Finding | Status | File | Lines | Evidence |
|---------|--------|------|-------|---------|
| OPENAI_API_KEY plaintext | VERIFIED | .env | 19 | `OPENAI_API_KEY=sk-proj-UTb5B32_...` |
| GEMINI_API_KEY plaintext | VERIFIED | .env | 18 | `GEMINI_API_KEY=AQ.Ab8RN6KQeV...` |
| TELEGRAM_BOT_TOKEN plaintext | VERIFIED | .env | 26 | `TELEGRAM_BOT_TOKEN=8685494518:AAH...` |
| JWT_SECRET_KEY plaintext | VERIFIED | .env | 16 | `JWT_SECRET_KEY=94c86bf4f85e4ea7...` |
| DB_PASSWORD plaintext | VERIFIED | .env | 5 | `DB_PASSWORD=SecurePassword_123!` |
| WebSocket CheckOrigin bypass | VERIFIED | server_ws.go | ~15-20 | `CheckOrigin: func(r *http.Request) bool { return true }` |
| docker.sock mounted | VERIFIED | docker-compose.yml | 171 | `- /var/run/docker.sock:/var/run/docker.sock` |
| workspace:rw mount | VERIFIED | docker-compose.yml | 172 | `- ./:/app/workspace:rw` |
| DEV_MODE=true | VERIFIED | .env | 31 | `DEV_MODE=true` |
| OSI_SECURITY_KEY reuse | VERIFIED | docker-compose.yml | 57,78 | Redis cmd + NATS cmd both use same key |

---

## NATS EVIDENCE

| Finding | Status | File | Lines | Evidence |
|---------|--------|------|-------|---------|
| JetStream initialized | VERIFIED | ingestion_server.go | 327-332 | `js, jsErr := natsConn.JetStream()` |
| escalate.request publish (non-JetStream) | VERIFIED | incident_service.go | 290 | `natsConn.Publish(...)` not `natsJS.Publish(...)` |
| close.request publish (non-JetStream) | VERIFIED | incident_service.go | 360 | `natsConn.Publish(...)` |
| remediation.execute request-reply | VERIFIED | execution_orchestrator.py | 61 | `await self.nc.request("remediation.execute", ...)` |
| NATS token auth | VERIFIED | docker-compose.yml | 78 | `--auth ${OSI_SECURITY_KEY}` |
| NATS monitoring localhost only | VERIFIED | docker-compose.yml | 84 | `127.0.0.1:8222:8222` |

---

## INFRASTRUCTURE EVIDENCE

| Finding | Status | File | Lines | Evidence |
|---------|--------|------|-------|---------|
| 15+ Docker services | VERIFIED | docker-compose.yml | All | 15 named services |
| nginx:1.25-alpine reverse proxy | VERIFIED | docker-compose.yml | 4 | `image: nginx:1.25-alpine` |
| Postgres healthcheck | VERIFIED | docker-compose.yml | 47-51 | `test: pg_isready -U postgres -d osi_system` |
| Redis healthcheck | VERIFIED | docker-compose.yml | 68-72 | `test: redis-cli ping` |
| JARVIS healthcheck | VERIFIED | docker-compose.yml | 334-338 | Python urllib.request check |
| restart: always on all services | VERIFIED | docker-compose.yml | Multiple | restart: always |
| Log rotation configured | VERIFIED | docker-compose.yml | Multiple | `max-size: "10m", max-file: "5"` |
| JARVIS Voice server port 8089 internal | VERIFIED | docker-compose.yml | 309 | `JARVIS_VOICE_API_PORT=8089` |
| NOC Bridge auto-discover DB token | VERIFIED | noc_bridge.py | 96-117 | psycopg2 query to rbac_users |
| Secure relay port 9998 | VERIFIED | docker-compose.yml | 216 | `- "9998:9998"` |
