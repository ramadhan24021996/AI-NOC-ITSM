# DOKUMEN ARSITEKTUR ENTERPRISE & VISUALISASI TOPOLOGI SISTEM INCIDENT ANALYSIS

> **Spesifikasi Diagram Arsitektur Tingkat Enterprise (Enterprise Solution & Software Architecture)**
> **Tanggal Rilis & Audit:** 23 Juli 2026
> **Status System:** PASSED_PRODUCTION_READY
> **Arsitek:** Enterprise Solution Architect, Principal Software Architect & System Visualization Expert

---

## 1. Enterprise System Topology Diagram

Diagram topologi menyeluruh yang menghubungkan pengguna, antarmuka web, backend Go, AI core Python, NATS JetStream, microservices Docker, agen endpoint, dan infrastruktur enterprise eksternal.

```mermaid
graph TD
    classDef client fill:#3b82f6,stroke:#1d4ed8,color:#fff,stroke-width:2px;
    classDef web fill:#0284c7,stroke:#0369a1,color:#fff,stroke-width:2px;
    classDef backend fill:#0d9488,stroke:#0f766e,color:#fff,stroke-width:2px;
    classDef ai fill:#7c3aed,stroke:#6d28d9,color:#fff,stroke-width:2px;
    classDef db fill:#d97706,stroke:#b45309,color:#fff,stroke-width:2px;
    classDef broker fill:#ea580c,stroke:#c2410c,color:#fff,stroke-width:2px;
    classDef infra fill:#475569,stroke:#334155,color:#fff,stroke-width:2px;
    classDef ext fill:#dc2626,stroke:#b91c1c,color:#fff,stroke-width:2px;

    subgraph ClientLayer [Client and User Layer]
        U["System Administrator"]:::client
        CE["Chrome Extension OSI Assistant"]:::client
    end

    subgraph PresentationLayer [Web Portal Presentation Layer]
        WP["System Portal Web UI"]:::web
        DB_M["Dashboard Utama"]:::web
        INC_M["Incident Management"]:::web
        TEL_M["Telemetry Monitoring"]:::web
        AI_M["AI Ops Cognition"]:::web
        KB_M["Knowledge Base RAG"]:::web
        AUD_M["System Audit Verification"]:::web
        SET_M["Settings Governance"]:::web
    end

    subgraph APIGateway [API Gateway Controller]
        REST["HTTP REST API Gateway"]:::backend
        WS["WebSocket Stream Server"]:::backend
    end

    subgraph CoreBackend [Go Backend Services]
        GB["Go Dashboard Server Core"]:::backend
        LS["Launcher Service Manager"]:::backend
        SR["Secure Encrypted Relay Service"]:::backend
    end

    subgraph AICore [Python AI Core Engine]
        PAI["Python AI Supervisor Cognition"]:::ai
        LLMR["LLM Router GPT4 Ollama"]:::ai
        RAG["RAG Vector Search Reranker"]:::ai
        DAG["Causal DAG Engine RCA"]:::ai
        GOV["Policy Engine HITL Safeguard"]:::ai
        OBS["Active Observer Daemon 247"]:::ai
        CHS["Autonomous Chaos Worker"]:::ai
    end

    subgraph Persistence [Persistence Broker Layer]
        NATS["NATS JetStream Event Broker"]:::broker
        SQL_INC["incident_analysis DB SQLite"]:::db
        SQL_SO["sprint_o DB State Machine"]:::db
        SQL_RAG["sprint_q_rag DB Vector Store"]:::db
        SQL_COG["cognitive_memory DB Memory DB"]:::db
        FTP["FTP Share OTA Storage"]:::db
    end

    subgraph AutomationInfra [Automation Container Infra]
        DK["Docker Microservices Engine"]:::infra
        N8N["n8n Workflow Automation Engine"]:::infra
        CASA["CasaOS System Management"]:::infra
    end

    subgraph EndpointAgents [Monitoring Agents]
        AL["Linux Agent Service"]:::client
        AW["Windows Agent Service"]:::client
    end

    subgraph ExternalServices [External Enterprise Integration]
        LDAP["LDAP Active Directory"]:::ext
        KAFKA["Apache Kafka Cluster"]:::ext
        DNS["Enterprise DNS DHCP"]:::ext
        K8S["Kubernetes Cluster"]:::ext
    end

    U --> WP
    CE --> REST
    WP --> DB_M & INC_M & TEL_M & AI_M & KB_M & AUD_M & SET_M
    DB_M & INC_M & TEL_M & AI_M & KB_M & AUD_M & SET_M --> REST & WS
    REST & WS --> GB
    GB --> LS & SR & NATS
    GB --> PAI
    PAI --> LLMR & RAG & DAG & GOV & OBS & CHS
    GB --> SQL_INC & SQL_SO
    PAI --> SQL_RAG & SQL_COG
    NATS --> AL & AW
    AL & AW --> NATS
    GB --> LDAP & KAFKA & DNS & K8S
    DK --> NATS & N8N & CASA
```

---

## 2. Package Dependency Graph

Visualisasi ketergantungan antar 10 Package Utama dalam arsitektur Incident Analysis.

```mermaid
graph TD
    classDef pkg fill:#1e40af,stroke:#1e3a8a,color:#fff,stroke-width:2px;

    P_SERVER["SERVER Root Backend Package"]:::pkg
    P_PORTAL["portal Web Portal Package"]:::pkg
    P_DIST["CLIENT_DISTRIBUSI_GO Agent Build"]:::pkg
    P_LAUNCH["LAUNCHER_SERVICE_GO Process Manager"]:::pkg
    P_DOCKER["docker Container Infrastructure"]:::pkg
    P_N8N["n8n_docker Workflow Engine"]:::pkg
    P_EXT["chrome_extension Browser Plugin"]:::pkg
    P_SCRIPTS["scripts Master Audit Admin"]:::pkg
    P_TESTS["tests Test Automation Suite"]:::pkg
    P_DOCS["DOCUMENTATION Enterprise Specs"]:::pkg

    P_LAUNCH --> P_PORTAL
    P_LAUNCH --> P_SERVER
    P_PORTAL --> P_SERVER
    P_SCRIPTS --> P_SERVER
    P_SCRIPTS --> P_PORTAL
    P_TESTS --> P_SERVER
    P_TESTS --> P_PORTAL
    P_EXT --> P_PORTAL
    P_DOCKER --> P_N8N
    P_DOCKER --> P_SERVER
    P_DIST --> P_LAUNCH
    P_DOCS -.-> P_SERVER
```

---

## 3. Subpackage Dependency Graph

Visualisasi ketergantungan antar subpackage kognitif, tata kelola, memori, dan runtime.

```mermaid
graph LR
    classDef subpkg fill:#4c1d95,stroke:#3b0764,color:#fff,stroke-width:2px;

    SP_TEL["telemetry"]:::subpkg
    SP_COG["cognition"]:::subpkg
    SP_GOV["governance"]:::subpkg
    SP_MEM["cognitive_memory"]:::subpkg
    SP_AGENT["multi_agent"]:::subpkg
    SP_PLAN["planning"]:::subpkg
    SP_KNOW["knowledge"]:::subpkg
    SP_LEARN["learning"]:::subpkg
    SP_EVO["evolution"]:::subpkg
    SP_ESCAL["escalation"]:::subpkg
    SP_EVAL["evaluation"]:::subpkg
    SP_WORLD["world_model"]:::subpkg
    SP_VERIF["verification"]:::subpkg
    SP_API["api"]:::subpkg
    SP_RUN["runtime"]:::subpkg
    SP_GO_DASH["portal dashboard"]:::subpkg

    SP_TEL --> SP_MEM & SP_GOV
    SP_COG --> SP_KNOW & SP_PLAN & SP_AGENT
    SP_GOV --> SP_COG & SP_VERIF
    SP_MEM --> SP_LEARN & SP_WORLD
    SP_AGENT --> SP_GOV & SP_COG
    SP_PLAN --> SP_WORLD
    SP_LEARN --> SP_EVO & SP_EVAL
    SP_API --> SP_COG & SP_TEL & SP_GOV
    SP_GO_DASH --> SP_API & SP_RUN
```

---

## 4. Module Dependency Graph

Ketergantungan modul dengan class, function, service, database, API, daemon, dan worker.

```mermaid
graph TD
    classDef mod fill:#0f766e,stroke:#115e59,color:#fff,stroke-width:2px;
    classDef cls fill:#7e22ce,stroke:#6b21a8,color:#fff,stroke-width:2px;
    classDef srv fill:#c2410c,stroke:#9a3412,color:#fff,stroke-width:2px;
    classDef db fill:#b45309,stroke:#854d0e,color:#fff,stroke-width:2px;

    M_AUDIT["master_production_readiness_audit.py"]:::mod
    M_OBS["active_observer_daemon.py"]:::mod
    M_CHAOS["chaos_injection_worker.py"]:::mod
    M_INGEST["telemetry_ingest_service.py"]:::mod
    M_RAG["rag_engine.py"]:::mod
    M_DASH["dashboard_server.go"]:::mod

    C_OBS["Class ActiveObserverDaemon"]:::cls
    C_CHAOS["Class AutonomousChaosWorker"]:::cls
    C_INGEST["Class TelemetryIngestService"]:::cls
    C_RAG["Class RAGEngine"]:::cls

    S_OBS["Service 247 Cognitive Observer"]:::srv
    S_INGEST["Service Telemetry Ingest Worker"]:::srv
    S_DASH["Service Go REST Server"]:::srv

    DB_MAIN["DB incident_analysis.db"]:::db
    DB_RAG["DB sprint_q_rag.db"]:::db

    M_AUDIT --> C_OBS & C_CHAOS & C_INGEST & C_RAG
    M_OBS --> C_OBS --> S_OBS
    M_CHAOS --> C_CHAOS
    M_INGEST --> C_INGEST --> S_INGEST --> DB_MAIN
    M_RAG --> C_RAG --> DB_RAG
    M_DASH --> S_DASH --> DB_MAIN
```

---

## 5. Runtime Execution Flow Diagram

Alur eksekusi dari startup hingga respon dan pencatatan audit.

```mermaid
sequenceDiagram
    autonumber
    actor User as User or Portal
    participant LS as Launcher Service
    participant GS as Go Server
    participant API as REST API Gateway
    participant AI as Python AI Core
    participant TC as Telemetry Collector
    participant INF as Inference Engine
    participant CON as Consensus Engine
    participant DEC as Decision Orchestrator
    participant POL as Policy Engine HITL
    participant TRU as Trust Engine
    participant REM as Remediation Engine
    participant LOG as Audit Logger
    participant DB as SQLite DB

    User->>LS: System Startup Trigger
    LS->>GS: Spawn Go Dashboard Server
    GS->>API: Initialize REST & WS Handlers
    User->>API: HTTP Request / Incident Event
    API->>AI: Dispatch to Python AI Core
    AI->>TC: Fetch System Telemetry
    TC-->>AI: Raw Telemetry Stream
    AI->>INF: Execute LLM / RAG Inference
    INF->>CON: Evaluate Multi-Agent Consensus
    CON->>DEC: Orchestrate Remediation Plan
    DEC->>POL: Check Risk & Enforcement Policy
    POL->>TRU: Calculate Agent Trust Score
    TRU-->>POL: Trust Score Validated
    POL->>REM: Dispatch Action Execution
    REM->>LOG: Log Execution Step
    LOG->>DB: Persist Audit Record & State
    DB-->>GS: Acknowledge Persistence
    GS-->>User: Return HTTP JSON Response
```

---

## 6. Incident Pipeline Architecture

Pipeline pemrosesan insiden end-to-end dari event hardware hingga pembaharuan RAG dashboard.

```mermaid
flowchart TD
    HW["Hardware Event Signal"] --> TEL["Telemetry Collector"]
    TEL --> NATS["NATS JetStream Event Stream"]
    NATS --> TAPI["Telemetry Ingest API"]
    TAPI --> CORR["Correlation Engine"]
    CORR --> DAG["Causal DAG Engine RCA"]
    DAG --> RC["Root Cause Diagnosis"]
    RC --> CON["Consensus Engine"]
    CON --> DEC["Decision Orchestrator"]
    DEC --> POL["Policy Engine Validation"]
    POL --> HITL{"Human Approval Required"}
    HITL -- Yes --> APP["Human Approval HITL"]
    HITL -- No --> REM["Autonomous Remediation"]
    APP --> REM
    REM --> VER["Verification Health Check"]
    VER --> KNOW["Knowledge Update"]
    KNOW --> RAG["RAG Vector Indexing"]
    RAG --> DASH["Live Dashboard Refresh"]
```

---

## 7. RAG Knowledge Pipeline Diagram

Pipeline penelusuran dan ekstraksi pengetahuan dokumen insiden dan ADR.

```mermaid
flowchart LR
    DOC["Incident Doc or ADR"] --> EMB["Sentence Transformer Embedding"]
    EMB --> VEC["Vector Store sprint_q_rag DB"]
    QUERY["User Question Query"] --> RET["Vector Retriever"]
    VEC --> RET
    RET --> RERANK["bge-reranker-large Cross-Encoder"]
    RERANK --> ROUTER["LLM Router"]
    ROUTER --> LLM["GPT-4 or Ollama Llama3"]
    LLM --> ANS["Synthesized Technical Answer"]
    ANS --> UPD["Knowledge Store Update"]
```

---

## 8. AI Cognition Pipeline Diagram

Alur penalaran kognitif 24/7 dari telemetri hingga pencatatan audit.

```mermaid
flowchart TD
    T["Telemetry Stream"] --> M["Cognitive Memory"]
    M --> O["Active Observer Daemon"]
    O --> Q["Question Engine"]
    Q --> C["Critic Engine"]
    C --> CON["Consensus Engine"]
    CON --> P["Planner"]
    P --> D["Decision Orchestrator"]
    D --> A["Action Execution"]
    A --> AUD["Audit Logger Persistence"]
```

---

## 9. Learning Pipeline Architecture

Alur ekstraksi fitur, temporal learning, penentuan versi, dan registry model.

```mermaid
flowchart LR
    TEL["Telemetry"] --> FE["Feature Extraction"]
    FE --> FS["Feature Store"]
    FS --> TL["Temporal Learning"]
    TL --> IL["Infrastructure Learning"]
    IL --> RL["Remediation Learning"]
    RL --> KS["Knowledge Store"]
    KS --> VER["Model Versioning"]
    VER --> EVAL["Model Evaluation"]
    EVAL --> MET["Performance Metrics"]
    MET --> REG["Model Registry"]
```

---

## 10. Verification Pipeline Architecture

Pipeline verifikasi otomatis 5 pilar arsitektur dan pengujian ketahanan.

```mermaid
flowchart TD
    SCH["Audit Scheduler"] --> VER["Master Audit Suite"]
    VER --> SEC["Security Test H05"]
    SEC --> AUTH["Authentication Test H02"]
    AUTH --> RBAC["RBAC Permission Test"]
    RBAC --> PERF["Performance Test"]
    PERF --> CHS["Chaos Injection Test"]
    CHS --> REP["Master Audit Report"]
    REP --> DASH["Dashboard Verification Panel"]
```

---

## 11. Deployment Topology Diagram

Topologi penyebaran node agent, NATS cluster, Go backend, Python AI, Docker, dan extension.

```mermaid
graph TD
    subgraph EdgeDevices [Target Edge Infrastructure]
        LA["Linux Agent Debian Ubuntu Service"]
        WA["Windows Agent Win32 Service"]
    end

    subgraph MessagingCluster [Event Streaming Layer]
        NATS["NATS JetStream Cluster Docker"]
    end

    subgraph CoreBackendNode [Core Server Node]
        GB["Go Backend Server Biner Docker"]
        PA["Python AI Core Runtime"]
        DB["SQLite Persisted Databases"]
    end

    subgraph WebInterface [User Interface Layer]
        PORTAL["Web Portal UI"]
        EXT["Chrome Extension Assistant"]
    end

    subgraph AutomationStack [Workflow Control Stack]
        DK["Docker Engine"]
        N8N["n8n Container"]
    end

    LA & WA --> NATS
    NATS --> GB
    GB --> PA & DB
    PORTAL & EXT --> GB
    DK --> N8N & NATS
```

---

## 12. Class Dependency Graph

Grafik hubungan antar class utama dalam arsitektur Incident Analysis.

```mermaid
graph TD
    classDef cls fill:#6d28d9,stroke:#5b21b6,color:#fff,stroke-width:2px;

    C_INGEST["TelemetryIngestService"]:::cls
    C_HW["HardwareTelemetryCollector"]:::cls
    C_ENT["EnterpriseConnectors"]:::cls
    C_LLM["LLMRouter"]:::cls
    C_RAG["RAGEngine"]:::cls
    C_CON["ConsensusEngine"]:::cls
    C_CRI["CriticEngine"]:::cls
    C_POL["PolicyEngine"]:::cls
    C_TRU["TrustEngine"]:::cls
    C_DEC["DecisionOrchestrator"]:::cls
    C_SM["StateMachine"]:::cls
    C_REP["ReplayEngine"]:::cls
    C_QUE["QuestionEngine"]:::cls
    C_OBS["ActiveObserverDaemon"]:::cls
    C_CHA["AutonomousChaosWorker"]:::cls
    C_AUD["AuditLogger"]:::cls

    C_HW & C_ENT --> C_INGEST
    C_INGEST --> C_AUD
    C_OBS --> C_INGEST & C_POL & C_QUE
    C_QUE --> C_CRI --> C_CON
    C_CON --> C_DEC --> C_POL
    C_POL --> C_TRU & C_SM
    C_DEC --> C_LLM & C_RAG
    C_CHA --> C_HW & C_AUD
    C_REP --> C_SM
```

---

## 13. Microservice Architecture by Domain

Pemisahan domain microservices pada arsitektur sistem Incident Analysis.

```mermaid
graph TD
    subgraph PortalDomain [Domain Portal UI]
        D_PORTAL["Web Portal UI Chrome Extension"]
    end
    subgraph BackendDomain [Domain Backend API]
        D_BACKEND["Go REST WebSocket Server"]
    end
    subgraph AIDomain [Domain AI Engine]
        D_AI["Python AI Supervisor LLM Router"]
    end
    subgraph TelemetryDomain [Domain Telemetry]
        D_TEL["Hardware Enterprise Connectors"]
    end
    subgraph LearningDomain [Domain Learning]
        D_LEARN["Temporal Remediation Learner"]
    end
    subgraph KnowledgeDomain [Domain Knowledge]
        D_KNOW["RAG Engine Vector Store"]
    end
    subgraph GovernanceDomain [Domain Governance]
        D_GOV["Policy Engine HITL Safeguard"]
    end
    subgraph MonitoringDomain [Domain Monitoring]
        D_MON["247 Active Observer Daemon"]
    end
    subgraph VerificationDomain [Domain Verification]
        D_VERIF["Master Audit Chaos Worker"]
    end
    subgraph AutomationDomain [Domain Automation]
        D_AUTO["n8n Workflow Automation Engine"]
    end
    subgraph AgentDomain [Domain Agent]
        D_AGENT["Linux Windows Monitoring Agents"]
    end
    subgraph StorageDomain [Domain Storage]
        D_STORE["SQLite DBs NATS Persistence"]
    end

    D_PORTAL --> D_BACKEND
    D_BACKEND --> D_AI & D_STORE
    D_AGENT --> D_TEL --> D_STORE
    D_AI --> D_KNOW & D_GOV & D_LEARN
    D_MON --> D_AI
    D_VERIF --> D_GOV & D_TEL
    D_AUTO --> D_BACKEND
```

---

## 14. Database Relationship Data Store Model

Visualisasi hubungan antar penyimpanan SQLite dan file store.

```mermaid
erDiagram
    INCIDENT_ANALYSIS_DB ||--o{ TELEMETRY_RECORDS : stores
    INCIDENT_ANALYSIS_DB ||--o{ INCIDENT_LOGS : records
    SPRINT_O_DB ||--o{ STATE_MACHINE_TRANSITIONS : tracks
    SPRINT_O_DB ||--o{ ESCALATION_POLICIES : enforces
    SPRINT_Q_RAG_DB ||--o{ VECTOR_EMBEDDINGS : indexes
    SPRINT_Q_RAG_DB ||--o{ DOCUMENT_CHUNKS : contains
    COGNITIVE_MEMORY_DB ||--o{ OBSERVER_SWEEPS : persists
    COGNITIVE_MEMORY_DB ||--o{ LONG_TERM_MEMORIES : retains
    LOCAL_POLICY_CACHE ||--o{ HITL_RULES : caches
    LOCAL_KNOWLEDGE_BASE ||--o{ OFFLINE_RULES : stores
```

---

## 15. Data Flow Diagram DFD

Aliran data dari input telemetri hingga pembaruan pengetahuan dan visualisasi.

```mermaid
flowchart LR
    INP["Input Hardware User Query"] --> PROC["Data Processing Ingestion"]
    PROC --> INF["AI Inference LLM RAG"]
    INF --> DEC["Action Decision"]
    DEC --> REM["Remediation Execution"]
    REM --> AUD["Audit Logging"]
    AUD --> KNOW["Knowledge Base Update"]
    KNOW --> VIS["Dashboard Visualization"]
```

---

## 16. C4 Model Architecture

C4 Model diagram yang terdiri dari Level 1 Context, Level 2 Container, Level 3 Component, dan Level 4 Code.

```mermaid
graph TD
    subgraph Level1Context [Level 1 System Context Diagram]
        USER["System Operator Admin"] --> SYS["Incident Analysis System"]
        SYS --> INFRA["Managed Enterprise Infrastructure"]
        SYS --> EXT_AI["Cloud LLM Provider OpenAI"]
    end

    subgraph Level2Container [Level 2 Container Diagram]
        WEB["Web Portal UI HTML JS"] --> GO_API["Go Dashboard REST API"]
        GO_API --> PY_AI["Python AI Core Engine"]
        GO_API --> NATS["NATS JetStream Broker"]
        PY_AI --> DB["SQLite Databases"]
    end

    subgraph Level3Component [Level 3 Component Diagram]
        ROUTER["LLM Router"] --> RAG_C["RAG Engine"]
        ROUTER --> POL_C["Policy Engine"]
        RAG_C --> DAG_C["Causal DAG Engine"]
    end
```

---

## 17. System Sequence Diagram

Diagram sekuensial lengkap interaksi antarkomponen dari permintaan pengguna hingga pembaruan dashboard.

```mermaid
sequenceDiagram
    autonumber
    actor User as User
    participant P as Portal
    participant API as REST API
    participant GB as Go Backend
    participant AI as Python AI
    participant DB as Database
    participant RAG as RAG Engine
    participant LLM as LLM Provider
    participant DASH as Dashboard

    User->>P: Access Incident Analysis
    P->>API: GET api v1 incidents
    API->>GB: Forward Query
    GB->>DB: SELECT FROM incidents
    DB-->>GB: Return Incident Data
    GB-->>API: JSON Response
    API-->>P: Render Incident Cards
    User->>P: Trigger AI Diagnosis
    P->>AI: POST api v1 ai chat
    AI->>RAG: Query Vector Knowledge
    RAG-->>AI: Relevant ADR Chunks
    AI->>LLM: Inference Request with Context
    LLM-->>AI: Generated Diagnosis
    AI->>DB: Save Audit Log
    AI-->>DASH: Refresh AI Ops View Alerts
```

---

## 18. State Machine Diagram

Siklus transisi status pengamatan, diagnosa, konsensus, mitigasi, dan pembelajaran sistem.

```mermaid
stateDiagram-v2
    [*] --> Idle
    Idle --> Observe : System Telemetry Stream
    Observe --> Analyze : Anomaly Event Detected
    Analyze --> Reason : Build Causal DAG
    Reason --> Consensus : Multi Agent Evaluation
    Consensus --> Decision : Plan Formulated
    Decision --> Remediation : Policy Approved HITL
    Remediation --> Verify : Health Check Pass
    Verify --> Learn : Rehydrate Knowledge RAG
    Learn --> Idle : Cycle Completed
```

---

## 19. Layered Architecture Diagram

Arsitektur berlapis enterprise dari Layer Presentasi hingga Layer Persistensi.

```mermaid
graph TD
    classDef l1 fill:#0284c7,stroke:#0369a1,color:#fff;
    classDef l2 fill:#0d9488,stroke:#0f766e,color:#fff;
    classDef l3 fill:#7c3aed,stroke:#6d28d9,color:#fff;
    classDef l4 fill:#4c1d95,stroke:#3b0764,color:#fff;
    classDef l5 fill:#b45309,stroke:#78350f,color:#fff;
    classDef l6 fill:#334155,stroke:#1e293b,color:#fff;
    classDef l7 fill:#15803d,stroke:#166534,color:#fff;

    subgraph Layer1 [1 Presentation Layer]
        P_UI["Web Portal HTML JS Chrome Extension"]:::l1
    end

    subgraph Layer2 [2 Business Logic Layer]
        P_BL["Go Dashboard Server REST APIs State Machine"]:::l2
    end

    subgraph Layer3 [3 AI Engine Layer]
        P_AI["Python AI Core LLM Router Causal DAG Supervisor"]:::l3
    end

    subgraph Layer4 [4 Learning Layer]
        P_LN["Feature Extraction Temporal Learning Model Registry"]:::l4
    end

    subgraph Layer5 [5 Knowledge Layer]
        P_KN["RAG Engine Sentence Transformers Vector Indexing"]:::l5
    end

    subgraph Layer6 [6 Infrastructure Layer]
        P_IN["NATS JetStream Broker Docker n8n Endpoint Agents"]:::l6
    end

    subgraph Layer7 [7 Persistence Layer]
        P_PE["SQLite Databases incident_analysis DB sprint_q_rag DB memory DB"]:::l7
    end

    Layer1 --> Layer2
    Layer2 --> Layer3
    Layer3 --> Layer4 & Layer5
    Layer4 & Layer5 --> Layer6
    Layer6 --> Layer7
```

---

## VERIFIKASI & KEPATUHAN ENTERPRISE

Seluruh 19 diagram arsitektur enterprise di atas dibangun secara konseptual dan struktural berdasarkan metadata nyata sistem Incident Analysis versi rilis 23 Juli 2026.

**Dokumen Resmi Diselesaikan pada:** 23 Juli 2026