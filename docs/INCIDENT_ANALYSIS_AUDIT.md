# INCIDENT ANALYSIS AUDIT
## OSI NOC IT AI — Forensic Incident Analysis Deep Audit
**Primary File:** `SERVER/go_core/ingestion/incident_service.go`  
**Supporting Files:** `SERVER/go_core/ai/ai_engine.go`, `SERVER/go_core/ingestion/ingestion_server.go`  
**Status:** FORENSIC AUDIT — Source-code verified

---

## FILE: incident_service.go

### FILE METADATA
| Field | Value |
|-------|-------|
| Path | SERVER/go_core/ingestion/incident_service.go |
| Size | 19,503 bytes / 488 lines |
| Package | ingestion |
| Language | Go |

### CLASSES / STRUCTS
```
IncidentService struct{} — line 63
  - singleton: var DefaultIncidentService = &IncidentService{} — line 65
```

### FUNCTIONS

| Function | Line | Purpose | Status |
|----------|------|---------|--------|
| `getServerIP()` | 21 | Auto-detect server IP for agent notifications | VERIFIED |
| `sendBypassCommandToAgent()` | 41 | TCP push command to Windows agent on port 10000/10001 | VERIFIED |
| `RegisterScreenshotCallback()` | 68 | Record screenshot upload path for incident workflow | VERIFIED |
| `TriggerIncidentWorkflow()` | 81 | MAIN: Full incident detection → AI analysis → notification | VERIFIED |
| `EscalateIncident()` | 269 | Escalate incident to NOC (NATS + Telegram + Chat) | VERIFIED |
| `ResolveIncident()` | 339 | Close incident, notify NOC of self-healing | VERIFIED |
| `updateIncidentCardStatus()` | 391 | Update chat message card with new status | VERIFIED |
| `TranslateCauseToIndo()` | 423 | Translate English cause to Indonesian | VERIFIED |
| `BuildUserFriendlyRemediation()` | 447 | Build step-by-step remediation guide | VERIFIED |

### DEPENDENCIES (IMPORTS)
| Package | Usage |
|---------|-------|
| `crypto/hmac`, `crypto/sha256` | HMAC token generation for agent push commands |
| `encoding/hex`, `encoding/json` | Token encoding, JSON serialization |
| `github.com/google/uuid` | ClientID UUID generation |
| `go_incident_analysis/SERVER/go_core/database` | DB operations via GORM |
| `go_incident_analysis/portal/dashboard/knowledge` | RAG knowledge engine for remediation lookup |

### INPUT SOURCES
| Source | Type | How |
|--------|------|-----|
| Telemetry alert (service_alert, process_alert, network_alert, incident_report) | From ingestion_server.go → handlePhase1Alert() | VERIFIED |
| User click "Hubungi NOC" on Chat UI | Via dashboard WebSocket → EscalateIncident() | VERIFIED |
| User click "Selesaikan Masalah" on Chat UI | Via dashboard WebSocket → ResolveIncident() | VERIFIED |

### OUTPUT TARGETS
| Target | Method | Data |
|--------|--------|------|
| PostgreSQL fleet_incidents | INSERT (line 113) | incident_id, pc_name, severity, description |
| PostgreSQL incident_events | INSERT (line 124) | CREATED event |
| PostgreSQL fleet_evidence | INSERT (line 259) | Screenshot path |
| Redis (via Chat Service) | PublishChatEvent() | Chat messages to client WebSocket |
| Windows Agent TCP :10000/:10001 | sendBypassCommandToAgent() | SHOW_NOTIFICATION, SHOW_CHAT |
| Telegram | DefaultTelegramService.SendIncidentAlert() | NOC group notification |
| NATS | natsConn.Publish("incident.site.*.escalate.request") | Python AI Core trigger |

### DATABASE OPERATIONS
| Table | Operation | Function | Line |
|-------|-----------|----------|------|
| fleet_incidents | COUNT (cooldown check) | TriggerIncidentWorkflow | 84 |
| chat_sessions | SELECT (get/create) | TriggerIncidentWorkflow | 96 |
| chat_sessions | INSERT | TriggerIncidentWorkflow | 106 |
| fleet_incidents | INSERT (raw SQL) | TriggerIncidentWorkflow | 113 |
| fleet_incidents | SELECT LASTVAL() | TriggerIncidentWorkflow | 118 |
| incident_events | INSERT | TriggerIncidentWorkflow | 124 |
| devices | SELECT ip | TriggerIncidentWorkflow goroutine | 191 |
| fleet_evidence | INSERT | TriggerIncidentWorkflow goroutine | 259 |
| fleet_incidents | SELECT site_id | EscalateIncident | 278 |
| chat_sessions | UPDATE status | EscalateIncident | 294 |
| fleet_incidents | SELECT pc_name, severity, description | EscalateIncident | 302 |
| fleet_evidence | SELECT screenshot | EscalateIncident | 309 |
| chat_sessions | UPDATE status=CLOSED | ResolveIncident | 364 |
| chat_sessions | SELECT pc_name | ResolveIncident | 368 |
| chat_messages | SELECT/UPDATE (card status) | updateIncidentCardStatus | 394, 411 |

### AI INTEGRATION
| Component | Call | Line | Status |
|-----------|------|------|--------|
| DefaultAIAnalysisService.Analyze() | Called in TriggerIncidentWorkflow | 138 | VERIFIED |
| DefaultAIAnalysisService.Analyze() | Called in EscalateIncident | 312 | VERIFIED |
| knowledge.GlobalEngine.Match() | RAG knowledge base lookup | 153 | VERIFIED |

**AI Analysis path:**
```
TriggerIncidentWorkflow()
  → DefaultAIAnalysisService.Analyze(description, "")
    → ai_analysis_service.go → wraps AISupervisor
      → ai_engine.go DiagnoseIncident()
        → CorrelateIncidents() [rule-based pattern matching]
        → QueryRAG() [PostgreSQL text search on knowledge_vectors]
        → CheckFleetCorrelation() [fleet_incidents cross-device query]
      → returns DiagnosisResult{PrimaryCause, Action, Reason, ConfidenceScore}
```

### NOTIFICATION PATH
```
TriggerIncidentWorkflow()
  1. SaveChatMessage("Saya mendeteksi gangguan...") [immediate feedback]
  2. PublishChatEvent() → Redis PubSub → WebSocket → Client UI
  3. AI Analysis runs
  4. SaveChatMessage(AI report) → PublishChatEvent()
  5. SaveChatMessage(remediation guide) → PublishChatEvent()
  6. goroutine: sendBypassCommandToAgent() SHOW_NOTIFICATION
  7. goroutine: sendBypassCommandToAgent() SHOW_CHAT
  8. goroutine: capture_screenshot via WebSocket
EscalateIncident()
  9. natsConn.Publish("incident.site.{id}.escalate.request")
  10. DefaultTelegramService.SendIncidentAlert() → Telegram
  11. SaveChatMessage("NOC Dihubungi") → PublishChatEvent()
```

### ERROR HANDLING
| Scenario | Handling | Line | Quality |
|----------|----------|------|---------|
| Cooldown/dedup | Skip if similar incident in last 2 minutes | 84-90 | GOOD |
| Session not found | Create new session | 97-107 | GOOD |
| LASTVAL fails | Fallback query by pc_name + DESC LIMIT 1 | 119-122 | ACCEPTABLE |
| Screenshot timeout | 4 second timeout, silently continues | 249-264 | ACCEPTABLE |
| Agent IP not found | Printf warning, skip push | 192-195 | ACCEPTABLE |
| NATS nil check | `if natsConn != nil` guard | 276, 346 | GOOD |
| Telegram error | Returned error propagated | 323 | GOOD |
| Status card not found | Printf warning, return | 395-398 | ACCEPTABLE |

### SECURITY ASSESSMENT
| Issue | Severity | Evidence |
|-------|----------|---------|
| Hardcoded HMAC secret key "SIAP_DISTRIBUSI_SECRET_KEY" | HIGH | Line 204, 218 |
| Raw SQL INSERT with string formatting (potential SQLi in description) | MEDIUM | Line 113-114 |
| No rate limit per PC for incident creation (2 min cooldown only) | LOW | Line 83 |

### RISKS
1. **HMAC secret hardcoded** in production code — should be env variable
2. **Raw SQL INSERT** with `fmt.Sprintf()` for description field — SQL injection risk
3. **No input sanitization** on description/severity before DB insert
4. **LASTVAL() race condition** in multi-tenant environment

### STATUS SUMMARY
| Feature | Status |
|---------|--------|
| Incident creation from alert | VERIFIED |
| AI analysis integration | VERIFIED |
| Chat notification | VERIFIED |
| Agent push notification | VERIFIED |
| Screenshot capture | VERIFIED |
| Escalation to NOC | VERIFIED |
| Telegram notification | VERIFIED |
| NATS event publish | VERIFIED |
| Self-healing resolution | VERIFIED |
| Knowledge base lookup | VERIFIED |

---

## FILE: ai_engine.go (AI Analysis Core)

### FILE METADATA
| Field | Value |
|-------|-------|
| Path | SERVER/go_core/ai/ai_engine.go |
| Size | 32,812 bytes / 849 lines |
| Package | ai |
| Language | Go |

### AI ANALYSIS METHOD: DiagnoseIncident()

**Status: VERIFIED — Rule-based, NOT LLM-based**

The Go AI engine (`ai_engine.go`) does NOT call any external LLM API. It uses:

1. **CorrelateIncidents()** — keyword-based pattern matching on alert strings
   - Checks for keywords: "gateway", "router", "agent", "database", "postgres"
   - Returns one of 4 predcodes: NETWORK_GATEWAY_DOWN, DATABASE_POOL_EXHAUSTED, CLIENT_SERVICE_STOPPED, UNKNOWN_ANOMALY

2. **QueryRAG()** — PostgreSQL text search (NOT semantic vector search)
   ```go
   db.Where("symptoms LIKE ? OR title LIKE ?", "%"+symptoms+"%", "%"+symptoms+"%").Limit(limit)
   ```
   > Note (line 79): "True Semantic Vector Search is handled by Python AI Core via Gemini API. This Go implementation uses basic text matching as a fallback/lightweight query."

3. **CheckFleetCorrelation()** — Queries fleet_incidents in last 24h for systemic patterns

4. **Confidence scoring** — mathematical formula based on:
   - Telemetry match (30%)
   - Historical match (30%)
   - Dependency validation (20%)
   - Temporal consistency (20%)
   - Penalties for VECTOR_ENGINE_UNAVAILABLE (-25%), DEPENDENCY_GRAPH_INCOMPLETE (-15%)

5. **RetrainClassifier()** — Returns MOCKED metrics (hardcoded 0.985 F1 score, simulated 100ms delay)

### CRITICAL FINDING: GO AI ENGINE IS RULE-BASED

```
Finding: Go AI engine (ai_engine.go) does NOT call LLM APIs.
Evidence: 
  File: SERVER/go_core/ai/ai_engine.go
  Function: DiagnoseIncident() — lines 335-848
  Comment at line 79: "True Semantic Vector Search is handled by Python AI Core"
  No HTTP calls, no API keys, no LLM imports.
Status: VERIFIED — Rule-based pattern matching, not LLM-based
Risk: Users/operators may believe AI analysis uses LLM when it uses heuristics
```

---

## FILE: ingestion_server.go (Telemetry Processing)

### KEY FUNCTIONS FOR INCIDENT DETECTION

| Function | Line | Purpose | Calls Incident? |
|----------|------|---------|----------------|
| `handlePhase1Alert()` | ~700+ | Alert routing | YES → TriggerIncidentWorkflow |
| `processVerifyTask()` | 558 | Main telemetry processor | YES (via handlePhase1Alert) |
| `checkAndSetIdempotency()` | ~620+ | Deduplication | BEFORE incident creation |
| `scoreTelemetryIntegrity()` | ~635+ | Integrity scoring (0.0-1.0) | GATE before processing |
| `validateTelemetrySchema()` | ~615 | Schema enforcement | GATE before processing |
| `verifyToken()` | ~625 | HMAC authentication | GATE before processing |

### ALERT TYPES THAT TRIGGER INCIDENTS
```go
alertTypes := map[string]bool{
    "service_alert":   true,   // Windows service stopped/started
    "process_alert":   true,   // Process anomaly
    "network_alert":   true,   // Network connectivity issue
    "incident_report": true,   // Direct incident report
    "evidence_upload": true,   // Screenshot/file evidence
}
```

### QUEUE ARCHITECTURE
```
metricQueue  chan TelemetryItem (capacity: 20,000)
logQueue     chan TelemetryItem (capacity: 10,000)
eventQueue   chan TelemetryItem (capacity: 10,000)
verifyQueue  chan verifyTask    (capacity: 20,000)

Site-sharded queues per site_id:
  - 2 metric workers per site
  - 1 log worker per site
  - 1 event worker per site

Global workers:
  - 4 metricProcessorWorker goroutines
  - 2 logProcessorWorker goroutines
  - 2 eventProcessorWorker goroutines
  - NumCPU*2 verifyWorker goroutines
```
