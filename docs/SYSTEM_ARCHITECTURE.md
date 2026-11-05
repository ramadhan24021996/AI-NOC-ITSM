# SYSTEM ARCHITECTURE
## OSI NOC IT AI — Actual Architecture Map
**Evidence:** docker-compose.yml, ingestion_server.go, incident_service.go, noc_bridge.py, portal/  
**Status:** VERIFIED from source code analysis

---

## HIGH-LEVEL ARCHITECTURE

```mermaid
flowchart TD
    subgraph Clients
        WA[Windows Agent\nagent.exe]
        LA[Linux Agent]
        ND[Netdata\nTelemetry]
        BR[Browser Extension]
    end

    subgraph Gateway
        NG[Nginx\n:80/:9443\nReverse Proxy]
    end

    subgraph IngestionTier["Ingestion Tier (Go)"]
        IS[Ingestion Server\n:18800/:18802\ngo_core]
        SS[Scheduler Service\nDistributed Scheduler]
    end

    subgraph CoreServices["Core Services"]
        DS[Dashboard Server\nportal/\n:9999 internal]
        SR[Secure Relay\n:9998]
        TB[Telegram Bot\nListener]
    end

    subgraph AITier["AI Tier (Python)"]
        PAC[Python AI Core\npython_ai_core/]
        JVS[JARVIS Voice Server\n:8089 internal]
        ACE[AI Consensus Engine]
    end

    subgraph MessageBus["Message Bus"]
        NATS[NATS 2.9\nJetStream\n:4222]
    end

    subgraph DataTier["Data Tier"]
        PG[(PostgreSQL 15\n+ pgvector\nosi_system)]
        RD[(Redis 7\nCache + PubSub)]
    end

    subgraph Notifications
        TG[Telegram\nNOC Group]
        WS_C[WebSocket\nClient Chat]
        UI[Dashboard\nNotification UI]
    end

    %% Agent Connections
    WA -->|TCP :18800| IS
    LA -->|TCP :18802| IS
    ND -->|TCP :19999| IS

    %% Ingestion Processing
    IS -->|GORM| PG
    IS -->|JetStream publish| NATS
    IS -->|Redis PubSub| RD

    %% NATS Subscriptions
    NATS -->|incident.site.*.escalate.request| PAC
    NATS -->|incident.site.*.close.request| PAC
    NATS -->|remediation.execute| PAC

    %% Dashboard Server
    NG --> DS
    DS -->|GORM| PG
    DS -->|Redis PubSub| RD
    DS -->|Proxy /jarvis/| JVS

    %% AI Core
    PAC -->|HTTP| DS
    PAC -->|GORM/psycopg2| PG
    JVS -->|HTTP API| DS

    %% Notifications
    IS -->|TCP :10000/10001| WA
    IS -->|SendIncidentAlert| TB
    TB -->|Telegram API| TG
    DS -->|WebSocket| WS_C
    DS -->|SSE/WS| UI

    %% Telegram listening
    TB -->|updates| TG

    %% Relay
    SR -->|Forwarding| TB
```

---

## INGESTION FLOW DETAIL

```mermaid
sequenceDiagram
    participant Agent as Windows Agent
    participant IS as Ingestion Server
    participant DB as PostgreSQL
    participant NATS as NATS JetStream
    participant AIS as AI Engine (Go)
    participant TG as Telegram
    participant CS as Chat Service

    Agent->>IS: TCP JSON payload (:18800)
    IS->>IS: validateTelemetrySchema()
    IS->>IS: verifyToken() HMAC-SHA256
    IS->>IS: scoreTelemetryIntegrity()
    IS->>IS: checkAndSetIdempotency()
    IS->>DB: ensureDeviceRegistered()
    IS->>IS: handlePhase1Alert()
    IS->>DB: INSERT fleet_incidents
    IS->>DB: INSERT incident_events
    IS->>AIS: DiagnoseIncident()
    AIS->>DB: QueryRAG (knowledge_vectors)
    AIS->>DB: CheckFleetCorrelation
    AIS-->>IS: DiagnosisResult
    IS->>CS: SaveChatMessage()
    IS->>CS: PublishChatEvent() [Redis]
    IS->>TG: SendIncidentAlert()
    IS->>Agent: sendBypassCommandToAgent() SHOW_NOTIFICATION
    IS->>NATS: Publish incident.site.*.escalate.request
```

---

## INCIDENT ESCALATION FLOW

```mermaid
sequenceDiagram
    participant User as End User
    participant Chat as Chat UI (WS)
    participant DS as Dashboard Server
    participant IS as Ingestion Server
    participant NATS as NATS
    participant PAC as Python AI Core
    participant TG as Telegram

    User->>Chat: Click "Hubungi NOC"
    Chat->>DS: POST /api/incident/escalate
    DS->>IS: EscalateIncident()
    IS->>NATS: Publish incident.site.{id}.escalate.request
    IS->>TG: SendIncidentAlert (NOC Notification)
    IS->>Chat: PublishChatEvent "NOC Dihubungi"
    NATS->>PAC: Subscribe escalate.request
    PAC->>PAC: GovernanceExecutionOrchestrator
    PAC->>PAC: Policy Decision (HITL/AUTO)
```

---

## MULTI-SERVICE COMPONENT MAP

```mermaid
graph LR
    subgraph GoCore["Go Core (Ingestion)"]
        IS_SV[ingestion_server.go]
        INC_SV[incident_service.go]
        AI_SV[ai_analysis_service.go]
        CHAT_SV[chat_service.go]
        TG_SV[telegram_service.go]
        AI_ENG[ai_engine.go]
        DB_SV[database.go]
        SCHEMA[schema.go]
    end

    subgraph Portal["Portal (Dashboard)"]
        DASH[dashboard_server.go]
        CHAT_ENG[chat_engine.go]
        JARVIS_API[jarvis_api.go]
        WS[server_ws.go]
        AUD[server_auditor.go]
    end

    subgraph PythonAI["Python AI Core"]
        LLM[llm_router.py]
        WO[workflow_orchestrator.py]
        API_R[api_router.py]
        RCA[rag_engine.py]
        HYPO[hypothesis_engine.py]
        GOV[execution_orchestrator.py]
        HITL[hitl_authorization_gate.py]
    end

    subgraph JarvisNOC["JARVIS Voice + NOC"]
        NOC_B[noc_bridge.py]
        JPA[jarvis_proactive_announcer.py]
        NVI[noc_voice_intelligence.py]
    end

    IS_SV --> INC_SV
    IS_SV --> AI_SV
    AI_SV --> AI_ENG
    INC_SV --> CHAT_SV
    INC_SV --> TG_SV
    IS_SV --> DB_SV
    DB_SV --> SCHEMA

    DASH --> CHAT_ENG
    DASH --> JARVIS_API
    DASH --> WS
    JARVIS_API --> NOC_B

    NOC_B --> DASH
    JPA --> NOC_B
    NVI --> NOC_B

    API_R --> WO
    WO --> LLM
    WO --> RCA
    GOV --> HITL
```

---

## PORT MAP (VERIFIED)

| Port | Protocol | Service | Exposed To |
|------|----------|---------|-----------|
| 18800 | TCP (custom JSON) | Ingestion Server (primary telemetry) | Windows/Linux Agents |
| 18802 | TCP (custom JSON) | Ingestion Server (RCA/Remediation) | Agents |
| 19999 | TCP/HTTP | Netdata telemetry ingestion | Netdata agents |
| 4222 | TCP (NATS) | NATS JetStream | All internal services |
| 8222 | HTTP (NATS monitor) | NATS Monitoring | localhost only |
| 9999 | HTTP | Dashboard Server | Internal (via Nginx) |
| 8089 | HTTP | JARVIS Voice Server | Dashboard Server proxy |
| 9998 | HTTP | Secure Relay | Agents |
| 5432 | PostgreSQL | PostgreSQL (internal) | All services (internal) |
| 5433 | PostgreSQL | PostgreSQL (host-mapped) | localhost only |
| 6379 | Redis | Redis | All services (internal) |
| 80 | HTTP | Nginx | External |
| 9443 | HTTPS | Nginx | External |
| 10000/10001 | TCP | Windows Agent command receiver | Server → Agent |

---

## DATA FLOW MATRIX

| Source | Destination | Protocol | Data Type | Verified |
|--------|-------------|----------|-----------|----------|
| Windows Agent | Ingestion Server :18800 | TCP JSON | Telemetry, alerts, incidents | YES |
| Ingestion Server | PostgreSQL | GORM/SQL | All incident/telemetry data | YES |
| Ingestion Server | NATS | JetStream Publish | Incident events | YES |
| Ingestion Server | Redis | PubSub | Chat events | YES |
| Ingestion Server | Windows Agent :10000 | TCP JSON | SHOW_NOTIFICATION, SHOW_CHAT | YES |
| Ingestion Server | Telegram API | HTTPS | Incident alerts | YES |
| NATS | Python AI Core | JetStream Subscribe | Incident events | CONNECTED_BUT_NOT_VERIFIED |
| Python AI Core | PostgreSQL | psycopg2 | Read incidents, write analysis | VERIFIED |
| Python AI Core | Dashboard Server | HTTP | NOC Bridge calls | VERIFIED |
| Dashboard Server | JARVIS Voice | HTTP Proxy | Voice queries | VERIFIED |
| Dashboard Server | Redis | PubSub | Chat event subscribe | VERIFIED |
| Dashboard Server | Nginx | HTTP | All web traffic | VERIFIED |

---

## AUTHENTICATION ARCHITECTURE

```mermaid
flowchart TD
    A[User Request] --> B{Nginx}
    B --> C[Dashboard Server]
    C --> D{JWT Validation}
    D -->|Invalid| E[401 Unauthorized]
    D -->|Valid| F{RBAC Check}
    F -->|Permission Denied| G[403 Forbidden]
    F -->|Allowed| H[Handler Execution]
    H --> I[Action + Audit Log]

    J[Agent Request :18800] --> K{HMAC-SHA256 Token}
    K -->|Invalid| L[UNAUTHORIZED DLQ]
    K -->|Valid| M{Schema Validation}
    M -->|Fail| N[BAD_REQUEST DLQ]
    M -->|Pass| O{Integrity Score}
    O -->|< 0.40| P[HARD REJECT DLQ]
    O -->|0.40-0.60| Q[Soft Flag: requires_hitl]
    O -->|>= 0.60| R[Process Telemetry]
```
