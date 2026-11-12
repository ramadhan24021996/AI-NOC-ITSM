# SYSTEM INVENTORY
## OSI NOC IT AI — Full System Component Inventory
**Source:** Direct filesystem analysis  
**Status:** VERIFIED from directory listing and file reads

---

## ROOT DIRECTORY STRUCTURE

```
./
├── .env                          # Environment config (SECRETS EXPOSED)
├── .env.backup.20260804_094142   # Backup env
├── .gitignore
├── .dockerignore
├── docker-compose.yml            # Main deployment (649 lines, 15+ services)
├── docker-compose.ha.yml         # HA variant
├── go.mod / go.sum               # Go module root
├── playwright.config.js          # E2E test config
├── pyrightconfig.json            # Python type checking
├── cognitive_memory.db           # SQLite for cognitive memory (root level)
├── CLIENT_DISTRIBUSI_GO/         # Windows agent distribution packages
├── SERVER/                       # All server-side code
├── portal/                       # Go dashboard server (frontend + backend)
├── LAUNCHER_SERVICE_GO/          # (Unknown, possibly archived)
├── DOCUMENTATION/                # Pre-existing documentation folder
├── docs/                         # Audit documentation (THIS AUDIT)
├── config/                       # Configuration files
├── docker/                       # Docker config (nginx, nats, redis, postgres)
├── manifests/                    # Kubernetes manifests (present but status unknown)
├── scripts/                      # Operational scripts
├── tests/                        # Test directory
├── chrome_extension/             # Browser extension
├── n8n_docker/                   # n8n workflow automation container
├── data/                         # Data directory
├── artifacts/                    # Build artifacts
├── build/                        # Build output
├── bin/                          # Compiled binaries
├── release_binaries/             # Release packages
├── security_reports/             # Security scan reports
├── workflows/                    # Workflow definitions
└── knowledge_imports/            # Knowledge base import files
```

---

## SERVER SUBSYSTEMS

### 1. SERVER/go_core — Go Ingestion & Core Server
**Language:** Go  
**Role:** Telemetry ingestion, incident service, AI analysis proxy, authentication, database

| Module | File | Purpose | Status |
|--------|------|---------|--------|
| ingestion | ingestion_server.go (4346 lines) | TCP/HTTP multiplexed ingestion server | VERIFIED |
| ingestion | incident_service.go (488 lines) | Incident workflow: creation, escalation, resolution | VERIFIED |
| ingestion | ai_analysis_service.go (938 bytes) | Wraps Go AI engine | VERIFIED |
| ingestion | chat_service.go (2637 bytes) | Chat session management + Redis pub/sub | VERIFIED |
| ingestion | telegram_service.go (4008 bytes) | Telegram bot notifications | VERIFIED |
| ingestion | dedup_filter.go (4665 bytes) | Deduplication filter | VERIFIED |
| ingestion | normalization.go (7722 bytes) | Telemetry normalization engine | VERIFIED |
| ingestion | enterprise_log_parser.go (6934 bytes) | Enterprise log parsing | VERIFIED |
| ai | ai_engine.go (849 lines) | AI supervisor, RCA, fleet correlation | VERIFIED |
| ai | embedding_worker.go (3090 bytes) | Vector embedding background worker | PARTIALLY_IMPLEMENTED |
| database | database.go (342 lines) | GORM connection, models, pool config | VERIFIED |
| database | schema.go (1422 lines) | 60+ table DDL definitions | VERIFIED |
| config | config.go (9770 bytes) | Config loading from env/DB | VERIFIED |
| security | security.go (7377 bytes) | Security manager, key handling | VERIFIED |
| security | hardening_security.go (10070 bytes) | Hardening utilities | VERIFIED |
| collector | agent_collector.go (8180 bytes) | Agent data collector | VERIFIED |
| scheduler | (directory) | Distributed scheduler | VERIFIED |
| ingestion | syslog_aggregator.go (4350 bytes) | Syslog ingestion | VERIFIED |
| ingestion | site_partitioner.go (2724 bytes) | Multi-site partitioning | VERIFIED |

### 2. SERVER/python_ai_core — Python AI Core
**Language:** Python 3.x  
**Role:** AI orchestration, LLM routing, RAG, governance, learning

| Module | Files Count | Key Files | Status |
|--------|-------------|-----------|--------|
| core/ | 25 files | workflow_orchestrator.py, db_connector.py, event_correlation_engine.py | VERIFIED |
| agents/ | 15 files | incident_agent.py, specialist_agents.py, security_agent.py | PARTIALLY_IMPLEMENTED |
| engines/ | 19 files | rag_engine.py, critic_engine.py, agentic_rag_engine.py, causal_dag_engine.py | VERIFIED |
| cognition/ | 37 files | knowledge_graph.py, hypothesis_engine.py, evidence_fabric.py | PARTIALLY_IMPLEMENTED |
| governance/ | 44 files | execution_orchestrator.py, hitl_authorization_gate.py, sop_registry_engine.py | PARTIALLY_IMPLEMENTED |
| learning/ | 22+ files | lora_training_pipeline_orchestrator.py, dpo_dataset_synthesizer.py | PLACEHOLDER |
| services/ | 26 files | intent_classifier.py, knowledge_graph_service.py, multi_agent_service.py | PARTIALLY_IMPLEMENTED |
| memory/ | 13 files | unified_memory_manager.py, knowledge_memory.py, short_term_memory.py | PARTIALLY_IMPLEMENTED |
| knowledge/ | 11 files | knowledge_fabric.py, knowledge_auto_builder.py | PARTIALLY_IMPLEMENTED |
| multi_agent/ | 8 files | orchestrator.py, planner_critic_consensus.py | PARTIALLY_IMPLEMENTED |
| routers/ | 5 files | api_router.py (key REST endpoints), incident_router.py | PARTIALLY_IMPLEMENTED |
| security/ | (dir) | auth_guard.py | VERIFIED |
| api/ | rest_api_server.py | REST server entrypoint | PARTIALLY_IMPLEMENTED |
| llm_router.py | 1 file (678 lines) | Multi-provider LLM routing, 9 providers | VERIFIED |
| ai_supervisor.py | 1 file (14253 bytes) | Python AI supervisor | PARTIALLY_IMPLEMENTED |
| state_machine.py | 1 file (9458 bytes) | Incident state machine | VERIFIED |

### 3. SERVER/jarvis — JARVIS Voice & NOC AI
**Language:** Python  
**Role:** Voice AI, NOC bridge, proactive intelligence, remediation

| Module | Files | Purpose | Status |
|--------|-------|---------|--------|
| noc/noc_bridge.py | 1156 lines | HTTP bridge to Go dashboard API | VERIFIED |
| proactive/jarvis_proactive_announcer.py | 37291 bytes | Proactive alerts & announcements | PARTIALLY_IMPLEMENTED |
| proactive/noc_voice_intelligence.py | 27913 bytes | NOC voice intelligence | PARTIALLY_IMPLEMENTED |
| proactive/predictive_forecaster.py | 4928 bytes | Predictive failure forecasting | PARTIALLY_IMPLEMENTED |
| remediation/one_click_remediator.py | 5413 bytes | One-click remediation | PARTIALLY_IMPLEMENTED |
| __init__.py | 8191 bytes | JARVIS init and startup | VERIFIED |

### 4. portal/ — Go Dashboard Server
**Language:** Go  
**Role:** Web dashboard, REST API for dashboard, chat, AI proxy

| File | Size | Purpose | Status |
|------|------|---------|--------|
| dashboard_server.go | 12060 bytes | Main dashboard HTTP server | VERIFIED |
| chat_engine.go | 67654 bytes | Chat engine (WebSocket + REST) | VERIFIED |
| jarvis_api.go | 12353 bytes | JARVIS API proxy | VERIFIED |
| sprint_o_api.go | 12868 bytes | Sprint O API endpoints | VERIFIED |
| server_ws.go | 6080 bytes | WebSocket handling | VERIFIED |
| server_auditor.go | 11075 bytes | System auditor | VERIFIED |
| state_machine.go | 8394 bytes | Portal state machine | VERIFIED |
| ldap_auth.go | 600 bytes | LDAP auth stub | PLACEHOLDER |

### 5. CLIENT_DISTRIBUSI_GO/ — Windows Agent Distribution
**Language:** Go (agent), Windows-targeted  
**Role:** Windows client agent for telemetry and chat

| Directory | Purpose | Status |
|-----------|---------|--------|
| agent/ | Windows agent | VERIFIED |
| collectors/ | System metric collectors | VERIFIED |
| linux_agent/ | Linux agent variant | VERIFIED |
| browser_extension/ | Browser extension | UNKNOWN |
| installer/ | Windows installer | VERIFIED |

---

## INFRASTRUCTURE SERVICES (from docker-compose.yml)

| Service | Image/Build | Port(s) | Role | Status |
|---------|-------------|---------|------|--------|
| nginx | nginx:1.25-alpine | 80, 9443 | Reverse proxy | VERIFIED |
| postgres | pgvector/pgvector:pg15 | 127.0.0.1:5433:5432 | Primary database | VERIFIED |
| redis | redis:7-alpine | Internal only | Cache + pub/sub | VERIFIED |
| nats | nats:2.9-alpine | 4222 (ext), 8222 (monitor, localhost) | Message broker | VERIFIED |
| ingestion-server | go_core Dockerfile | 18800, 18802 | Telemetry ingestion | VERIFIED |
| scheduler-service | go_core Dockerfile | Internal | Distributed scheduler | VERIFIED |
| dashboard-server | portal/Dockerfile | Internal (proxied via nginx) | Dashboard UI + API | VERIFIED |
| secure-relay | portal/Dockerfile.secure_relay | 9998 | Secure relay for agents | VERIFIED |
| telegram-bot-listener | go_core/telegram_bot/Dockerfile | Internal | Telegram bot | VERIFIED |
| python-ai-core | python_ai_core/Dockerfile | Internal | Python AI orchestrator | VERIFIED |
| jarvis-voice-server | jarvis/Dockerfile | 8089 (internal) | JARVIS voice AI | VERIFIED |
| ai-consensus | python_ai_core/Dockerfile | Internal | AI consensus engine | VERIFIED |
| n8n | n8n_docker | 5678 | Workflow automation | VERIFIED |

---

## LANGUAGES & TECHNOLOGIES

| Language/Tech | Usage | Files Approx |
|---------------|-------|--------------|
| Go 1.21+ | Ingestion server, dashboard, telegram bot | 50+ .go files |
| Python 3.x | AI core, JARVIS, governance, learning | 200+ .py files |
| PostgreSQL 15 + pgvector | Primary database with vector search | 1 database, 60+ tables |
| Redis 7 | Cache, pub/sub for real-time chat | Integrated |
| NATS 2.9 + JetStream | Message broker, event bus | Integrated |
| Docker / Docker Compose | Containerized deployment | 1 compose, 8+ Dockerfiles |
| SQLite | Cognitive memory (local Python AI) | cognitive_memory.db |
| HTML/JS/CSS | Frontend dashboard | portal/static/, portal/templates/ |
| Nginx | Reverse proxy + TLS termination | nginx.conf |

---

## AI/LLM PROVIDERS

| Provider | Config Location | Status |
|----------|----------------|--------|
| Google Gemini | .env GEMINI_API_KEY, ai_config.json | VERIFIED |
| OpenAI GPT | .env OPENAI_API_KEY | VERIFIED |
| Groq | llm_router.py provider registry | CONFIG_DEPENDENT |
| DeepSeek | llm_router.py provider registry | CONFIG_DEPENDENT |
| Anthropic Claude | llm_router.py provider registry | CONFIG_DEPENDENT |
| Mistral | llm_router.py provider registry | CONFIG_DEPENDENT |
| Together.ai | llm_router.py provider registry | CONFIG_DEPENDENT |
| HuggingFace | llm_router.py provider registry | CONFIG_DEPENDENT |
| Ollama (local) | llm_router.py provider registry | CONFIG_DEPENDENT |

---

## TOTAL FILE COUNT (approximate)

| Area | Estimated Files |
|------|----------------|
| Go source files | 80+ |
| Python source files | 250+ |
| Configuration files | 30+ |
| Database schema | 1 file (60+ tables) |
| Docker files | 10+ |
| Test files | 15+ |
| Shell/Script files | 20+ |
| **Total** | **~460+** |
