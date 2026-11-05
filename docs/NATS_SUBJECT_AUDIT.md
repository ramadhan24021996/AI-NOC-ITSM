# NATS SUBJECT AUDIT
## OSI NOC IT AI — NATS/JetStream Event Bus Forensic Audit
**Evidence:** ingestion_server.go, incident_service.go, governance/execution_orchestrator.py,  
docker-compose.yml (nats:2.9-alpine), SERVER/python_ai_core/core/nats_cluster_manager.py  
**Status:** VERIFIED for Go side; Python side CONNECTED_BUT_NOT_VERIFIED

---

## NATS CONFIGURATION

### Docker Service
```yaml
# docker-compose.yml
nats:
  image: nats:2.9-alpine
  command: -c /etc/nats/nats-server.conf --auth ${OSI_SECURITY_KEY}
  ports:
    - "4222:4222"              # External NATS port
    - "127.0.0.1:8222:8222"   # Monitoring (localhost only)
  volumes:
    - ./docker/nats/nats-server.conf:/etc/nats/nats-server.conf:ro
    - nats_data:/data/nats
```

### NATS Authentication
- Token auth: `--auth ${OSI_SECURITY_KEY}` (same key as Redis and agent HMAC)
- Connection URL: `nats://{OSI_SECURITY_KEY}@nats:4222`

### JetStream Configuration
```go
// ingestion_server.go
natsConn, err = nats.Connect(natsURL)
js, jsErr := natsConn.JetStream()  // JetStream enabled
natsJS = js
```

---

## VERIFIED NATS SUBJECTS (Go Side)

### Publishers (Go Ingestion Server)

| Subject | Publisher | File | Function | Payload | Status |
|---------|-----------|------|----------|---------|--------|
| `incident.site.{siteID}.escalate.request` | ingestion_server | incident_service.go | EscalateIncident() L290 | `{incident_id, current_level:1, next_level:2, operator_note}` | VERIFIED |
| `incident.site.{siteID}.close.request` | ingestion_server | incident_service.go | ResolveIncident() L360 | `{incident_id, actor, resolution_summary, resolution_proof}` | VERIFIED |

**Note:** `natsConn.Publish()` used (not JetStream) for incident events — **no persistence guarantee**

### Python AI Core NATS Usage (execution_orchestrator.py)

```python
# execution_orchestrator.py line 61
await self.nc.request("remediation.execute", json.dumps(mitigation_payload).encode(), timeout=timeout)
```

| Subject | Role | File | Status |
|---------|------|------|--------|
| `remediation.execute` | Publisher (request-reply) | execution_orchestrator.py | CONNECTED_BUT_NOT_VERIFIED |

---

## NATS SUBJECT TABLE (FULL INVENTORY)

| Subject Pattern | Publisher | Subscriber | Payload Description | Persistence | Status |
|----------------|-----------|------------|---------------------|-------------|--------|
| `incident.site.{id}.escalate.request` | Go IS EscalateIncident | Python AI Core (expected) | escalation request JSON | NONE (Publish) | PUBLISHER_VERIFIED / SUBSCRIBER_NOT_VERIFIED |
| `incident.site.{id}.close.request` | Go IS ResolveIncident | Python AI Core (expected) | resolution request JSON | NONE (Publish) | PUBLISHER_VERIFIED / SUBSCRIBER_NOT_VERIFIED |
| `remediation.execute` | Python GOV Orchestrator | Go IS (expected) | remediation command | NONE (Request) | PUBLISHER_VERIFIED / SUBSCRIBER_NOT_VERIFIED |
| `scheduler.*` | Scheduler Service | Ingestion Server | Scheduled task commands | UNKNOWN | CONNECTED_BUT_NOT_VERIFIED |
| `telemetry.*` | Agents (indirect) | Ingestion Server | Telemetry events | JetStream? | PARTIALLY_VERIFIED |

---

## NATS JETSTREAM STATUS

```go
// ingestion_server.go line 327-331
js, jsErr := natsConn.JetStream()
if jsErr != nil {
    fmt.Printf(" [INGESTOR FATAL] JetStream initialization failed: %v\n", jsErr)
    os.Exit(1)
}
natsJS = js
```

**JetStream is initialized** but the actual publish calls in incident_service.go use `natsConn.Publish()` (not JetStream), meaning:
- **No message persistence** for incident events
- **No acknowledgment** guarantee
- **Messages lost** if subscriber is down at publish time

**This is a CRITICAL reliability gap.**

---

## NATS SUBSCRIPTION DISCOVERY

### Python AI Core (python_ai_core)

```python
# execution_orchestrator.py — uses nc.request() which implies NATS connection
# The NATS connection is passed in __init__(self, nc, conn)
# But where nc is initialized: NOT FOUND in verified call chain
```

**Evidence Search:**
- `execution_orchestrator.py` receives `nc` as constructor parameter (line 51)
- `run_orchestrator.py` (811 bytes) — likely initializer, not fully read
- **NATS subscription in Python NOT verified from source code**

---

## SCHEDULER NATS SUBSCRIPTIONS

```go
// ingestion_server.go
StartSchedulerSubscriptions()
```

This function is called at startup but the actual subjects it subscribes to are in `scheduler/` directory. Based on naming convention, expected subjects:
- `scheduler.heartbeat` — device heartbeat checks
- `scheduler.health.check` — fleet health polling
- `scheduler.printer.poll` — printer status polling

**Status:** CONNECTED_BUT_NOT_VERIFIED

---

## DEAD LETTER QUEUE (DLQ)

```go
// ingestion_server.go
routeToDLQ(text, "JSON_DECODE_ERROR: "+err.Error())
routeToDLQ(item, "SCHEMA_VALIDATION_FAILED: ...")
routeToDLQ(item, "UNAUTHORIZED: Invalid token signature")
routeToDLQ(item, "INTEGRITY_REJECTED: score=...")
```

**DLQ Implementation:**
- **NOT NATS-based** — writes to `dlq_hybrid` PostgreSQL table
- Retry tracked in `retry_history` table
- `dlq_service.py` in Python AI Core processes retries (PARTIALLY_IMPLEMENTED)

---

## NATS RISKS

| Risk | Severity | Evidence |
|------|----------|---------|
| Incident events use plain Publish (no JetStream persistence) | CRITICAL | incident_service.go L290, L360 |
| Python NATS subscriber not verified | HIGH | execution_orchestrator.py constructor param pattern |
| Same OSI_SECURITY_KEY for NATS, Redis, and HMAC | MEDIUM | docker-compose.yml, .env |
| No dead-letter for failed NATS messages (DLQ is DB-based, not NATS) | MEDIUM | ingestion_server.go routeToDLQ |
| NATS monitoring port 8222 bound to localhost only | LOW (good practice) | docker-compose.yml |
| JetStream streams not defined — only connection initialized | HIGH | No stream creation code found |

---

## RECOMMENDATIONS

1. **Migrate incident events to JetStream** with durable consumers and ack
2. **Verify Python NATS subscriber** — confirm where nc is initialized in run_orchestrator.py
3. **Create named JetStream streams** for `incident.>`, `remediation.>`, `scheduler.>`
4. **Rotate OSI_SECURITY_KEY** — do not reuse across NATS, Redis, HMAC
5. **Add dead-letter subject** in NATS for failed message tracking (not just DB table)
