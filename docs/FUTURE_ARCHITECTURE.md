# FUTURE ARCHITECTURE
## OSI NOC IT AI — Recommended Future Architecture
**Based on:** Current audit findings and gaps  
**Status:** RECOMMENDATION — not implemented

---

## RECOMMENDED TARGET ARCHITECTURE

```mermaid
graph TD
    subgraph Clients
        WA[Windows Agent v5]
        LA[Linux Agent]
        ND[Netdata]
        WEB[Browser Dashboard]
    end

    subgraph Security["Security Layer"]
        VAULT[HashiCorp Vault\nSecrets Manager]
        OPA[Open Policy Agent\nPolicies]
    end

    subgraph Gateway["Gateway Layer"]
        NG[Nginx\nHTTPS + Rate Limit]
        WAF[WAF Rules]
    end

    subgraph IngestionTier["Ingestion Tier (Scalable)"]
        IS1[Ingestion Server 1]
        IS2[Ingestion Server 2]
        IS3[Ingestion Server 3]
    end

    subgraph MessageBus["Message Bus (JetStream)"]
        NATS[NATS JetStream\nNamed Streams\nPersisted + Acked]
        TELEMETRY_STREAM[Stream: TELEMETRY]
        INCIDENT_STREAM[Stream: INCIDENTS]
        REMEDIATION_STREAM[Stream: REMEDIATION]
    end

    subgraph CoreServices["Core Services"]
        DS[Dashboard Server\nw/ Rate Limit + CSRF]
        JVS[JARVIS Voice\nProduction-hardened]
    end

    subgraph AITier["AI Tier"]
        GO_AI[Go Rule-Based AI\nFast Path]
        PY_AI[Python LLM AI\nDeep Analysis]
        RAG[RAG Engine\npgvector semantic]
        GOV[Governance\nReal policy execution]
    end

    subgraph DataTier["Data Tier (HA)"]
        PG_W[(PostgreSQL Primary\nTLS enabled)]
        PG_R[(PostgreSQL Read Replica)]
        REDIS_C[(Redis Cluster)]
        S3[S3/MinIO\nEvidence storage]
    end

    subgraph Observability["Observability Stack"]
        PROM[Prometheus]
        GRAF[Grafana]
        LOKI[Loki\nLog aggregation]
        JAEGER[Jaeger\nDistributed traces]
        ALERT[Alertmanager\nPagerDuty/Slack]
    end

    WA -->|mTLS TCP| IS1
    LA -->|mTLS TCP| IS2
    NG --> DS
    IS1 --> NATS
    IS2 --> NATS
    NATS --> GO_AI
    NATS --> PY_AI
    GO_AI --> PG_W
    PY_AI --> PG_W
    PY_AI --> RAG
    RAG --> PG_R
    GOV --> OPA
    DS --> PG_R
    DS --> REDIS_C
    VAULT --> IS1
    VAULT --> DS
    VAULT --> PY_AI
    IS1 --> PROM
    DS --> PROM
    PY_AI --> PROM
    PROM --> GRAF
    PROM --> ALERT
```

---

## KEY ARCHITECTURAL IMPROVEMENTS

### 1. Secrets Management
- HashiCorp Vault for all API keys, JWT secrets, DB passwords
- Dynamic short-lived credentials for DB (Vault database secrets engine)
- Secret rotation automation

### 2. Message Bus (JetStream)
- Named streams: TELEMETRY, INCIDENTS, REMEDIATION
- Durable consumers with explicit ack
- Consumer groups for load-balanced processing
- Subject hierarchy: `{domain}.{site}.{event_type}`

### 3. AI Two-Tier Decision
- **Tier 1 (< 200ms):** Go rule-based for immediate response
- **Tier 2 (< 2s):** Python LLM for deep analysis
- **Feedback loop:** Resolved incidents → knowledge base update
- **Quality gate:** Critic engine validates all AI decisions

### 4. State Management
- Single source of truth: `incident_states` table
- Event sourcing via `incident_events` with causal_chain
- Go and Python both read/write same `incident_states` row (with optimistic locking)

### 5. Observability
- Structured JSON logging with slog/zap (Go) + structlog (Python)
- Prometheus metrics + Grafana dashboards
- Loki log aggregation
- Jaeger distributed traces (OTel SDK)
- Alertmanager → PagerDuty + Telegram

### 6. Security
- Separate keys per service (no OSI_SECURITY_KEY reuse)
- bcrypt password hashing with 12 rounds
- CSRF tokens on all state-change endpoints
- WebSocket origin whitelist
- TLS everywhere (internal + external)
- mTLS for agent → ingestion server communication

### 7. Testing
- Unit tests: >80% coverage
- Integration tests: Full incident lifecycle
- Chaos tests: Kill individual services
- Performance tests: 10,000 events/second

### 8. Scaling
- Horizontal scaling of ingestion-server (3+ replicas)
- PostgreSQL read replica for analytics queries
- Redis Cluster for HA
- NATS cluster (3 nodes) for HA
