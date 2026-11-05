# OBSERVABILITY AUDIT
## OSI NOC IT AI — Logging, Metrics, Tracing, Health Check Audit
**Evidence:** ingestion_server.go, hardening/, schema.go (audit tables), docker-compose.yml  
**Status:** PARTIALLY_IMPLEMENTED — Good foundations, gaps in aggregation

---

## OBSERVABILITY COMPONENTS

| Component | Technology | Status |
|-----------|-----------|--------|
| Structured Logging | fmt.Printf (Go), logging module (Python) | PARTIALLY_IMPLEMENTED |
| Distributed Tracing | OpenTelemetry (OTel) — trace_id/span_id | PARTIALLY_IMPLEMENTED |
| Metrics | Internal counters + pprof | PARTIALLY_IMPLEMENTED |
| Health Checks | Per-service health endpoints | VERIFIED |
| Database Audit | immutable_audit_log + system_audits | VERIFIED |
| Resource Monitoring | hardening.MonitorResources() | VERIFIED |
| Agent Heartbeats | agent_heartbeats table | VERIFIED |

---

## LOGGING ANALYSIS

### Go Logging (Ingestion Server)
```go
// ingestion_server.go — uses fmt.Printf() throughout
fmt.Printf(" [INGESTOR DEBUG] Received connection from %s\n", ipAddr)
fmt.Printf(" [INGESTOR SUCCESS] %s Pipeline listening on Port %d\n", pipelineName, port)
fmt.Printf(" [INGESTOR FATAL] JetStream initialization failed: %v\n", jsErr)
```

**Logging Format:** Unstructured text with `[CATEGORY]` prefix  
**Output:** stdout (captured by Docker json-file log driver)  
**Log Rotation:** `max-size: "10m", max-file: "5"` (per docker-compose.yml)  
**Missing:** JSON structured logging, log levels (DEBUG/INFO/WARN/ERROR), correlation IDs in all log lines

### Python Logging (python_ai_core)
```python
logger = logging.getLogger("LLM_ENTERPRISE_ROUTER")
logger.info("[ORCHESTRATOR] NLU: urgency=...")
logger.error("[REST_ROUTER] Internal router error: ...", exc_info=True)
```

**Logging Format:** Standard Python logging module  
**Level Usage:** INFO, WARNING, ERROR — VERIFIED  
**Missing:** Centralized aggregation, JSON format for ELK/Loki

### GORM SQL Logging
```go
gorm.Config{Logger: logger.Default.LogMode(logger.Info)}
```
**Status:** All SQL queries logged at INFO level — VERIFIED (may be too verbose in production)

---

## DISTRIBUTED TRACING

### OpenTelemetry Integration
**File:** ingestion_server.go  
**Function:** `InjectOTelContext(&item)`

```go
// Called in processVerifyTask() before routing
InjectOTelContext(&item)

// TelemetryItem fields (verified in struct definition):
TraceID       string `json:"trace_id,omitempty"`       // OpenTelemetry Trace ID
SpanID        string `json:"span_id,omitempty"`         // OpenTelemetry Span ID
CorrelationID string `json:"correlation_id,omitempty"`  // Enterprise Correlation ID
```

**Status:** trace_id/span_id fields defined in struct — `InjectOTelContext()` exists  
**Gap:** Actual OTel SDK (go.opentelemetry.io) import NOT found in go.mod review — context may be manually propagated, not SDK-based

### trace_id Propagation in Database
```sql
-- schema.go: ALTER TABLE adds trace_id to:
incidents          ADD COLUMN trace_id TEXT
incident_events    ADD COLUMN trace_id TEXT
ai_reflection_logs ADD COLUMN trace_id TEXT, span_id TEXT, parent_span TEXT
ai_approval_logs   ADD COLUMN trace_id TEXT, span_id TEXT
```
**Status:** VERIFIED — trace context persisted in DB for cross-service correlation

---

## METRICS

### Internal Metrics (ingestion_server.go)
```go
var (
    metricsProcessedCount int64
    metricsErrorsCount    int64
    metricsDLQCount       int64
    metricsLatencySum     float64
    metricsMu             sync.Mutex
)
```

**Exposed via:** GET /metrics endpoint (HTTP)  
**Format:** Custom JSON — NOT Prometheus format  
**Missing:** Prometheus exporter, histogram buckets, percentile latency

### Resource Monitoring (hardening/)
```go
hardening.MonitorResources(sqlDB, redisClient, nil, logFn, 30*time.Second)
```
- Polls DB pool stats, Redis memory, CPU/memory
- Logs warnings at threshold crossings
- **No export to external system** (Prometheus/Datadog/Grafana)

### AI Metrics Table
```sql
CREATE TABLE ai_metrics (
    metric_id SERIAL PRIMARY KEY,
    model_used TEXT,
    latency_ms INTEGER,
    prompt_tokens INTEGER,
    completion_tokens INTEGER,
    cost_estimate REAL,
    hallucination_score REAL,
    ...
)
```
**Status:** Schema VERIFIED — write path from Python AI not fully verified

---

## HEALTH CHECKS

| Service | Endpoint | Checks | Status |
|---------|---------|--------|--------|
| Dashboard Server | GET /api/health | Basic response | VERIFIED |
| Python AI Core | GET /api/v1/health | DB connectivity + subcomponents | VERIFIED |
| JARVIS Voice | GET /jarvis/health | Basic | VERIFIED |
| PostgreSQL | Docker healthcheck: pg_isready | DB ready | VERIFIED |
| Redis | Docker healthcheck: redis-cli ping | Redis ready | VERIFIED |
| NATS | No healthcheck configured | None | NOT_CONFIGURED |
| Ingestion Server | GET /health on :18800 | Basic | VERIFIED |

### Python AI Health Detail (api_router.py _handle_health())
```python
# Returns static subcomponent status (NOT live checks):
{
    "ai_supervisor": "ONLINE",    # Static string
    "rag_engine": "ONLINE",       # Static string
    "auth_guard": "ACTIVE",       # Static string
    "causal_dag": "ACTIVE",       # Static string
    "database": db_status,        # LIVE DB check
    "nlu_engine": "ACTIVE",       # Static string
}
```
**Finding:** Only `database` status is live-checked; all other components report static "ONLINE" regardless of actual state.

---

## AGENT HEARTBEATS

### Heartbeat Table
```sql
CREATE TABLE agent_heartbeats (
    agent TEXT PRIMARY KEY,
    status TEXT DEFAULT 'ALIVE',  -- ALIVE, DEGRADED, DEAD
    uptime INTEGER,
    queue_depth INTEGER,
    cpu REAL,
    last_seen TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```

### Dead Man Switch (startDeadManSwitch in ingestion_server.go)
```go
// Periodic check: if agent_heartbeats.last_seen > threshold → mark DEAD
// Triggers: incident creation for "agent offline" scenario
```
**Status:** VERIFIED

---

## AUDIT TRAIL

### Immutable Audit Log
```sql
CREATE TABLE immutable_audit_log (
    log_id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    action_type TEXT NOT NULL,
    actor TEXT NOT NULL,
    target TEXT,
    payload JSONB,
    prev_hash TEXT NOT NULL,       -- chain previous
    hash_signature TEXT NOT NULL,  -- SHA256 hash of this record
    session_id TEXT,
    classification TEXT DEFAULT 'INTERNAL'
)
```
**Status:** VERIFIED — cryptographic hash chain for tamper detection

### System Audits
```sql
CREATE TABLE system_audits (
    id SERIAL PRIMARY KEY,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    health_score REAL,
    status TEXT,
    failed_components TEXT[],
    root_cause TEXT,
    audit_hash TEXT,
    previous_audit_hash TEXT,
    audit_category TEXT
)
```
**Status:** VERIFIED — periodic system health snapshots

### RBAC Audit Logs
```sql
CREATE TABLE rbac_audit_logs (
    log_id SERIAL PRIMARY KEY,
    username TEXT,
    action TEXT,
    target TEXT,
    details JSONB,
    ip_address TEXT,
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP
)
```
**Status:** VERIFIED — all auth operations logged

---

## OBSERVABILITY GAPS

| Gap | Impact | Priority |
|-----|--------|----------|
| No Prometheus/OpenMetrics exporter | Cannot integrate with Grafana/Alertmanager | P1 HIGH |
| No log aggregation (ELK/Loki) | Log search requires per-container access | P1 HIGH |
| Go logging uses fmt.Printf (not structured) | Cannot filter/query logs efficiently | P2 MEDIUM |
| OTel trace export not configured | Traces not sent to Jaeger/Zipkin | P2 MEDIUM |
| Python health check returns static status | Health checks not reliable | P2 MEDIUM |
| No SLA breach alerting verified | SLA breaches may be silent | P1 HIGH |
| No alerting rules (Alertmanager/PagerDuty) | No automated escalation on system failures | P1 HIGH |
| pprof server exposed (hardening.StartPprofServer) | Performance data exposure if network misconfigured | P3 LOW |

---

## OBSERVABILITY STRENGTHS

| Strength | Evidence |
|----------|---------|
| Hash-chained immutable audit log | immutable_audit_log table |
| Comprehensive RBAC audit | rbac_audit_logs table |
| AI decision audit trail | ai_audit_trail table |
| trace_id propagation in DB | ALTER TABLE scripts |
| Agent heartbeat monitoring | agent_heartbeats + Dead Man Switch |
| Resource monitoring | hardening.MonitorResources() |
| DLQ tracking | dlq_hybrid + retry_history |
| pprof profiling endpoint | hardening.StartPprofServer() |
