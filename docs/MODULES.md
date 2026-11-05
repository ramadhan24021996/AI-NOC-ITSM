# Enterprise AIOS (Incident Analysis) — Complete Module Tree & Architectural Specification

> **Document Type:** Master Architectural Reference  
> **Version:** 11.3 Enterprise HA Edition  
> **Coverage:** Full Codebase Subsystems (SERVER, Portal, Edge Agent, Launcher, Infrastructure, & GitOps)

---

## 1. Executive Architecture & Subsystem Blueprint

The **Enterprise AIOS (Incident Analysis Platform)** is a distributed, autonomous, multi-agent AI operating system designed for real-time IT Infrastructure & NOC incident detection, root cause analysis (RCA), self-healing remediation, and continuous learning.

```
+---------------------------------------------------------------------------------------------------+
|                                  NOC OPERATOR & EXECUTIVE DASHBOARD                               |
|                       (Go Gin Portal Server + Vanilla JS SPA + WebSockets)                        |
+---------------------------------------------------------------------------------------------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    | (HTTP/REST & WebSockets)                                  | (NATS JetStream Bus)
                    v                                                           v
+---------------------------------------------------+       +---------------------------------------+
|                SERVER / GO CORE                   |       |         CLIENT_DISTRIBUSI_GO          |
|  - Ingestion Server (Port 18800)                  |       |  - Edge Agent (Windows / Linux)       |
|  - Telegram & Syslog Adapters                     |       |  - Deep Telemetry & Forensics         |
|  - Security & Dedup Layer                         |       |  - Edge Anomaly Watcher & Self-Healing|
+---------------------------------------------------+       +---------------------------------------+
                    |                                                           |
                    +-----------------------------+-----------------------------+
                                                  | (Event Streaming)
                                                  v
+---------------------------------------------------------------------------------------------------+
|                                    SERVER / PYTHON AI CORE                                        |
|  +---------------------------+  +---------------------------+  +-------------------------------+  |
|  |     COGNITIVE ENGINE      |  |     KNOWLEDGE & RAG       |  |     GOVERNANCE & SAFETY       |  |
|  | - Workflow Orchestrator   |  | - Agentic RAG Service     |  | - 5 Golden Rules Engine       |  |
|  | - NLU Intent Engine       |  | - GraphRAG L1-L7 Engine   |  | - Remediation Guard & Policy  |  |
|  | - LLM Router & Cache      |  | - Hybrid Re-ranking       |  | - Action Matrix & Audit Trail |  |
|  +---------------------------+  +---------------------------+  +-------------------------------+  |
|  +---------------------------+  +---------------------------+  +-------------------------------+  |
|  |   ACTIVE PROBING & TKG    |  |    LEARNING & EVOLUTION   |  |     VERIFICATION & ROLLBACK   |  |
|  | - Temporal Graph (v6-v11) |  | - LF1-LF5 Gate Framework  |  | - Pre-Verification Simulator  |  |
|  | - Blast Radius Simulator  |  | - DPO Dataset Synthesizer |  | - Post-Execution Auditor      |  |
|  | - Active Probe Pipeline   |  | - LoRA Training Pipeline  |  | - Automatic Rollback Engine   |  |
|  +---------------------------+  +---------------------------+  +-------------------------------+  |
+---------------------------------------------------------------------------------------------------+
                                                  |
                    +-----------------------------+-----------------------------+
                    | (Persisted Storage & Cache)                               | (Workflow Automation)
                    v                                                           v
+---------------------------------------------------+       +---------------------------------------+
|            DATABASE & INFRASTRUCTURE              |       |          N8N GITOPS WORKFLOWS         |
|  - PostgreSQL 16 + PGVector (GraphRAG L1-L7)      |       |  - Multi-source RAG Ingestion v4.3    |
|  - Redis 7 (Sub-20ms Semantic Vector Cache)       |       |  - Obsidian Vault Sync Daemon v4.1    |
|  - NATS JetStream 2.10 (Distributed Message Bus)  |       |  - Auto Post-Mortem Publisher v4.2    |
+---------------------------------------------------+       +---------------------------------------+
```

---

## 2. Full Directory & Module Tree Map

```
incident-analysis/
├── CLIENT_DISTRIBUSI_GO/                  # Cross-Platform Edge Telemetry Agent (Go / C# / Python)
│   ├── 05_SIAP_DISTRIBUSI/                # Binary Distribution Packages & Setup Executables
│   │   ├── INSTALL_AGENT.bat              # Batch Script Installer for Windows Agents
│   │   ├── LINUX_AGENT_INSTALLER.zip      # Archived Linux Agent Deployment Package
│   │   ├── WINDOWS_AGENT_INSTALLER.zip    # Archived Windows Agent Deployment Package
│   │   ├── agent.exe                      # Compiled Windows Telemetry Agent
│   │   ├── agent_tray.exe                 # System Tray GUI Executable
│   │   ├── linux_chat_ui.py               # Desktop Chat UI Client for Linux Operators
│   │   ├── osi-agent-linux_2.0.0_amd64.deb# Debian/Ubuntu Agent Package (v2.0.0)
│   │   ├── osi-agent-linux_2.1.0_amd64.deb# Debian/Ubuntu Agent Package (v2.1.0)
│   │   └── updater.exe                    # Auto-Update Agent Launcher
│   ├── agent/                             # Core Edge Telemetry Engine (Go)
│   │   ├── ChatForm.cs                    # C# WinForms Chat GUI Component
│   │   ├── agent.exe                      # Built Agent Binary
│   │   ├── browser_ext_server.go          # WebSocket Bridge Server for Browser Extensions
│   │   ├── deep_telemetry.go              # Low-level CPU, Memory, Disk, & Process Telemetry
│   │   ├── edge_anomaly_watcher.go        # On-device Anomaly Detection & Threshold Alerting
│   │   ├── main.go                        # Agent Daemon Entry Point & Initialization
│   │   ├── nats_failover_client.go        # Resilient NATS Client with Fallback & Reconnect
│   │   ├── probes/                        # Active Diagnostic Probes (Ping, DNS, TCP, HTTP)
│   │   ├── remediation_subscriber.go     # Subscribes to Execution Remediation Commands
│   │   ├── telemetry_publisher.go        # Streams Real-Time Metrics to Ingestion Server
│   │   ├── tier0_self_healing.go          # Local Tier-0 Automated Remediation Actions
│   │   ├── topology_collector.go          # Local Network & Peripheral Topology Discovery
│   │   └── v8_forensics.go                # System Log & Memory Dump Forensics Collector
│   ├── browser_extension/                 # Chrome / Edge Extension for Web Monitoring
│   │   ├── background.js                  # Service Worker Script for DOM & Network Sniffing
│   │   ├── manifest.json                  # Manifest V3 Extension Specification
│   │   ├── popup.html                     # Extension Popup User Interface
│   │   └── popup.js                       # Extension Interactivity & Local Storage Bridge
│   ├── collectors/                        # Metric & Log Collector Plugins (Go)
│   │   ├── browser_collector.go           # Web Navigation & HTTP Performance Telemetry
│   │   ├── cpu_collector.go               # CPU Utilization & Core Thermal Telemetry
│   │   ├── disk_collector.go              # Storage I/O, Capacity, & SMART Health Telemetry
│   │   ├── dns_collector.go               # DNS Resolution Latency & Query Failures
│   │   ├── eventlog_collector.go          # Windows Event Log & Linux Journald Parser
│   │   ├── memory_collector.go            # RAM Consumption & OOM Condition Telemetry
│   │   ├── network_collector.go           # Bandwidth, Interface Packets, & Drop Rates
│   │   ├── printer_collector.go           # CUPS & Spooler Printer Status Telemetry
│   │   ├── process_collector.go           # Process Tree & Resource Usage Monitoring
│   │   ├── security_collector.go          # Auth Failures, USB Connections, & Privilege Logs
│   │   └── wifi_collector.go              # RSSI Signal Strength, BSSID, & SSID Telemetry
│   ├── installer/                         # Windows Installer Builder Configuration
│   │   ├── installer.exe                  # Compiled Setup Executable
│   │   ├── main.go                        # Custom Go Setup Launcher
│   │   └── setup.iss                      # Inno Setup Compiler Script
│   ├── linux_agent/                       # Native Linux Daemon (Go / Python)
│   │   ├── browser_ext_server.go          # Linux Local WebSocket Receiver
│   │   ├── build_deb.sh                   # Script to Build Debian `.deb` Package
│   │   ├── deb_pkg/                       # DEBIAN Directory Structure & Systemd Files
│   │   ├── deep_telemetry_linux.go        # Linux `/proc` and `/sys` Telemetry Parser
│   │   ├── linux_chat_ui.py               # Tkinter/PyQt Client Interface
│   │   ├── linux_tray_agent.py            # AppIndicator / System Tray Icon for Linux
│   │   ├── main.go                        # Linux Daemon Entry Point
│   │   └── update_linux_agent.sh          # Silent Background Updater
│   ├── releases/                          # Packaged Production Binary Releases
│   └── scripts/                           # Maintenance & Deployment Scripts
├── LAUNCHER_SERVICE_GO/                   # Process Supervisor & Watchdog Daemon (Go)
│   ├── main.go                            # Service Supervisor Loop & Process Restarter
│   ├── helpers_unix.go                    # Unix Process Control & Signal Handling
│   └── helpers_windows.go                 # Windows Service Manager Interop
├── SERVER/                                # Backend AI OS Core & Services
│   ├── ai_kernel/                         # Subsystem Kernel Abstractions
│   │   ├── message_bus/                   # Event Bus Protocols & Interfaces
│   │   └── scheduler/                     # Task Scheduling Interfaces
│   ├── database/                          # DB Migration & Connection Handlers
│   ├── go_core/                           # High-Throughput Telemetry Ingestion (Go)
│   │   ├── discovery/                     # Network Asset Auto-Discovery Engine
│   │   ├── ingestion/                     # Ingestion Server (Port 18800) & Syslog Listener
│   │   │   ├── ingestion_server.go        # Log Normalizer, Dedup, & NATS Publisher
│   │   │   └── telegram_service.go        # Telegram Operator Approval & Alert Bot
│   │   └── security/                      # Token Validation & Payload Decryption
│   ├── integration/                       # External API Integration Adapters
│   │   ├── gateway/                       # Unified NOC Integration Gateway
│   │   ├── grpc/                          # gRPC Service Base & Stubs
│   │   ├── rest/                          # REST Handler Base Abstractions
│   │   ├── telegram/                      # Telegram Bot Adapter
│   │   └── websocket/                     # WebSocket Streaming Gateway Base
│   ├── jarvis/                            # Conversational Voice & Cognitive Assistant
│   │   ├── cognition/                     # NLU & Intent Engine
│   │   │   ├── intent_pipeline.py         # Intent Parser & Sub-intent Classification
│   │   │   ├── llm_command_translator.py  # Voice Command to System Action Translator
│   │   │   └── opening_engine.py          # Dynamic Contextual Opening Generator
│   │   ├── noc/                           # NOC Incident Bridge
│   │   ├── planning/                      # Action Catalog & Safety Validator
│   │   ├── remote/                        # Remote Browser Control Bridge
│   │   ├── runtime/                       # Jarvis Presentation Runtime Engine
│   │   └── voice/                         # Voice Processing Subsystem
│   │       ├── stt_provider.py            # Faster-Whisper Speech-To-Text Adapter
│   │       ├── stt_service.py             # Speech Recognition Service Facade
│   │       ├── tts_provider.py            # Kokoro-TTS & Parametric WAV Synthesizer
│   │       ├── tts_service.py             # Text-To-Speech Service Facade
│   │       └── wake_word_detector.py      # OpenWakeWord Detection Engine
│   ├── knowledge/                         # Local Knowledge Base & Store Handlers
│   ├── memory/                            # Short & Long-Term Memory Persistence
│   ├── n8n_docker/                        # GitOps Workflow Automation Files
│   ├── orchestrator/                      # Cognitive Decision & Execution Orchestrator
│   │   ├── cognitive/                     # Multi-Agent Conflict Resolver
│   │   ├── coordinator/                   # Execution Coordinator
│   │   ├── decision_intelligence/         # Solution Validator Engine
│   │   ├── dispatcher/                    # Task Dispatcher Subsystem
│   │   └── planner/                       # Execution Planner Subsystem
│   ├── python_ai_core/                    # Main Enterprise AI Operating System Engine (Python)
│   │   ├── active_probing/                # Active Probing & Temporal Knowledge Graph
│   │   │   ├── active_diagnostic_probing.py# Probing Pipeline Engine
│   │   │   ├── aios_temporal_knowledge_graph.py# Time-Travel World Model (v6-v11)
│   │   │   └── safety_simulation_engine.py# Blast Radius Pre-execution Simulator
│   │   ├── adapters/                      # Gateway Adapters
│   │   │   ├── mcp_adapter.py             # Model Context Protocol (MCP) Gateway
│   │   │   └── output_synthesizer.py      # LLM Response Synthesizer & Validator
│   │   ├── core/                          # AI OS Core Runtimes & Services
│   │   │   ├── db_connector.py            # PostgreSQL & Redis Database Connector
│   │   │   ├── jarvis_response_engine.py  # Response Formatting Engine
│   │   │   ├── llm_cost_optimizer.py      # Token Cost & Model Routing Optimizer
│   │   │   ├── logger.py                  # Structured JSON Logger
│   │   │   ├── nlu_engine.py              # TF-IDF & Vector Intent Classifier
│   │   │   ├── semantic_cache_manager.py  # Redis Sub-20ms Vector Cache
│   │   │   └── workflow_orchestrator.py   # Multi-Agent Workflow Engine
│   │   ├── engines/                       # Core Analytical & RAG Engines
│   │   │   ├── agentic_rag_engine.py      # Dynamic RAG Query Reformulation
│   │   │   ├── counterfactual_engine.py   # What-If Counterfactual Analysis
│   │   │   ├── engine_adapters.py         # Unified Interface Adapters
│   │   │   ├── multi_source_knowledge_aggregator.py# Multi-Source Knowledge Ingestion
│   │   │   ├── rag_engine.py              # Hybrid Re-ranking & Vector Search Engine
│   │   │   └── telemetry_log_index_engine.py# Log Stream Indexing & Compaction
│   │   ├── evaluation/                    # AI Quality & Evaluation
│   │   │   └── llm_judge_evaluator.py     # Automated LLM-as-a-Judge Scorecard
│   │   ├── execution/                     # Remediation Execution
│   │   │   ├── execution_engine.py        # Safe Action Runner
│   │   │   ├── rollback_engine.py         # State Snapshot & Rollback Exec
│   │   │   └── verification_engine.py     # Post-Execution Validator
│   │   ├── fusion_stream/                 # Real-time Stream Fusion
│   │   ├── governance/                    # Policy, Security, & Compliance Rules
│   │   │   ├── action_matrix.py           # HITL Approval & Action Permissibility Matrix
│   │   │   ├── ai_model_registry.py       # LLM Endpoint Registry
│   │   │   ├── execution_orchestrator.py  # Governance Approval Loop
│   │   │   ├── five_golden_rules_engine.py# Enterprise Security Rules Enforcer
│   │   │   ├── graph_config_registry.py   # Dynamic Configuration Registry
│   │   │   ├── graph_security_audit_trail.py# Tamper-Proof Audit Logging
│   │   │   ├── obsidian_vault_parser.py   # SOP Markdown Vault Parser
│   │   │   ├── post_mortem_generator.py   # Automatic Post-Mortem Report Generator
│   │   │   ├── post_mortem_vault_exporter.py# Vault Exporter
│   │   │   ├── remediation_guard.py       # Pre-Execution Safety Guard
│   │   │   ├── remediation_policy_engine.py# Policy Rule Matcher
│   │   │   ├── script_signature.py        # Remediation Script Cryptographic Verification
│   │   │   └── sop_canary_deployment.py   # Canary Deployment Verifier for SOPs
│   │   ├── knowledge/                     # Knowledge Evolution & Conflict Resolution
│   │   │   ├── conflict_detector.py       # Knowledge Contradiction Detector
│   │   │   ├── deduplication_engine.py    # Vector & Semantic Deduplication
│   │   │   ├── knowledge_evolution_engine.py# Continuous Graph Evolution
│   │   │   ├── knowledge_fabric.py        # GraphRAG Knowledge Store Facade
│   │   │   └── vendor_doc_store.py        # Vendor Manual Ingestion Store
│   │   ├── learning/                      # Self-Improving Learning Framework (LF1-LF5)
│   │   │   ├── audit/                     # Learning Audit Logger
│   │   │   ├── distributed_lock.py        # Distributed Lock Engine (Redis/Memory)
│   │   │   ├── dpo_dataset_synthesizer.py # Direct Preference Optimization (DPO) Dataset Builder
│   │   │   ├── evaluator/                 # Evaluation Contracts
│   │   │   ├── feature_store/             # Enterprise Feature Store (Registry & Validators)
│   │   │   ├── graph_embedding.py         # Graph Embedding Generator
│   │   │   ├── graph_feature_store.py     # Graph Feature Store Layer
│   │   │   ├── knowledge_store/           # Knowledge Persistence
│   │   │   ├── lora_training_pipeline_orchestrator.py# Automated LoRA Fine-Tuning Pipeline
│   │   │   ├── metrics/                   # Prometheus & Quality Metrics Tracker
│   │   │   ├── registry/                  # Learning Capability Registry
│   │   │   ├── sandbox_promotion_engine.py# Sandbox Safety Promotion Gate
│   │   │   ├── scheduler/                 # Async Job Scheduler
│   │   │   ├── unified_embedding_manager.py# Unified Embedding Manager
│   │   │   └── versioning/                # Semantic Version Controller
│   │   ├── llm_router.py                  # Multi-LLM Provider Router (Gemini, OpenAI, Groq, DeepSeek)
│   │   ├── routers/                       # Fast-API Style Micro-Routers
│   │   │   ├── api_router.py              # Root REST Router with AuthGuard Protection
│   │   │   ├── incident_router.py         # Incident State Machine Router
│   │   │   ├── remediation_router.py      # Remediation Routing Engine
│   │   │   └── telemetry_router.py        # Telemetry Stream Router
│   │   ├── run_orchestrator.py            # AI OS Standalone Orchestrator Launcher
│   │   ├── security/                      # Zero-Trust Security Layer
│   │   │   ├── auth_guard.py              # HMAC-HS256 Token Auth & RBAC Guard
│   │   │   └── privacy_redactor.py        # Automatic PII & Credentials Redactor
│   │   ├── services/                      # High-Level Business Logic Services
│   │   │   ├── agentic_rag_service.py     # Agentic RAG Service Facade
│   │   │   ├── cmdb_baseline_service.py   # Configuration Management Baseline Service
│   │   │   ├── graph_workflow_orchestrator.py# Graph Workflow Engine
│   │   │   ├── kedb_runbook_service.py    # Known Error Database & Runbook Matcher
│   │   │   ├── obsidian_sync_daemon.py    # Markdown Vault Sync Daemon
│   │   │   └── vendor_discovery_plugins.py# Vendor Discovery Plugins
│   │   ├── supervisor/                    # NATS Message Consumer Supervisor
│   │   │   ├── dispatcher.py              # Message Handler Dispatcher
│   │   │   ├── pipeline_logger.py         # Pipeline Execution Logger
│   │   │   └── handlers/                  # Specific Message Handlers
│   │   ├── telemetry/                     # Infrastructure Connectors
│   │   │   └── enterprise_dns_dhcp_connector.py# DNS & DHCP Server Telemetry Connector
│   │   └── tests/                         # Comprehensive Unit & Integration Test Suites
│   │       ├── test_active_diagnostic_probing.py
│   │       ├── test_aios_v11_production_architecture.py
│   │       ├── test_causal_engine.py
│   │       ├── test_full_causal_pipeline_integration.py
│   │       ├── test_graphrag_e2e_integration.py
│   │       ├── test_jarvis_intent_pipeline.py
│   │       ├── test_phase3_multi_agent_platform.py
│   │       └── test_production_readiness_suite.py
│   ├── repositories/                      # Storage Repositories Layer
│   ├── security/                          # Server Security Utilities
│   └── shared/                            # Shared Utilities & Data Structures
├── config/                                # System & Infrastructure Configuration
│   ├── nats_cluster/                      # NATS JetStream Cluster Docker Compose
│   ├── prometheus/                        # Prometheus Alert Rules & Scrape Configs
│   └── redis/                             # Redis Enterprise Caching Config
├── docker/                                # Containerization Build Scripts & Manifests
│   ├── nats/                              # NATS Server Config
│   ├── nginx/                             # Nginx High Availability Reverse Proxy (`nginx_ha.conf`)
│   ├── pgadmin/                           # PgAdmin Management Container Config
│   └── postgres/                          # PostgreSQL 16 + PGVector Extension & Init Scripts
│       └── init_scripts/                  # GraphRAG L1-L7 Database Schema (`add_graphrag_l1_l7_schema.sql`)
├── docker-compose.yml                     # Standard Standalone Production Services Compose
├── docker-compose.ha.yml                  # High Availability Multi-Node Cluster Compose
├── docs/                                  # Comprehensive System Documentation
│   ├── 01_REQUIREMENTS/                   # Product Requirements & Specifications
│   ├── 02_ARCHITECTURE/                   # Architectural Diagrams & Design Docs
│   ├── 03_DATABASE/                       # GraphRAG & PostgreSQL Schemas
│   ├── 04_API/                            # OpenAPI Specs & REST API Specs
│   ├── 05_AGENT/                          # Edge Agent Protocols & Deployment Manuals
│   ├── 06_SECURITY/                       # Zero-Trust & RBAC Governance Specs
│   ├── SOP_VAULT/                         # Standard Operating Procedure Markdown Vault
│   └── MODULES.md                         # Master System Subsystem Reference
├── n8n_docker/                            # GitOps Workflow Automation Files
│   ├── workflows_gitops/                  # Production JSON Workflow Exports
│   │   ├── auto_postmortem_publisher_v4_2.json# Auto Post-Mortem Generation Workflow
│   │   ├── multi_source_rag_ingestion_v4_3.json# Document Ingestion & Embedding Pipeline
│   │   └── obsidian_vault_sync_v4_1.json  # SOP Vault Synchronization Workflow
│   └── netdata_config/                    # NetData Observability Container Specs
├── portal/                                # Dashboard API Gateway & NOC User Interface (Go / JS)
│   ├── Dockerfile                         # Containerization Build for Portal
│   ├── asset_api.go                       # IT Asset Management API Endpoints
│   ├── backup_trash/                      # Isolated Backup & Deprecated File Archive
│   ├── chat_engine.go                     # Interactive NOC Operator Chat Backend
│   ├── cognitive_memory_api.go            # AI Memory Graph Inspection API
│   ├── dashboard/                         # Backend Package Split
│   │   └── api/                           # Handlers Package (`ai_handlers.go`, `fleet_crud.go`, `rbac_handlers.go`, `rca_handlers.go`, `sop_handlers.go`, `storage_handlers.go`)
│   ├── dashboard_server.go                # Main HTTP Router & Middleware Handler
│   ├── jarvis_api.go                      # Voice Assistant WebSocket & REST API
│   ├── ldap_auth.go                       # Active Directory / LDAP Authentication Module
│   ├── main.go                            # Portal Entry Point
│   ├── multi_agent_api.go                 # Multi-Agent Status & Consensus Inspection API
│   ├── pkg/                               # Internal Helper Packages
│   │   ├── auth/                          # JWT Token & Session Management
│   │   ├── chat/                          # Chat Channel Types & Message Structs
│   │   └── services/                      # Database & External Connection Managers
│   ├── predictive_api.go                  # Anomaly & Metric Trend Prediction API
│   ├── relay/                             # Agent Telemetry Relay Server
│   ├── server_auditor.go                  # Real-Time Security Audit Stream Handler
│   ├── server_chat.go                     # Real-Time NOC Chat WebSocket Hub
│   ├── server_ws.go                       # Main WebSocket Event Broadcast Hub
│   ├── sprint_o_api.go                    # Advanced SLA & SLO Monitoring API
│   ├── state_machine.go                   # Incident Lifecycle State Machine
│   ├── static/                            # Static Assets Subsystem
│   │   ├── css/                           # Custom Styling & Glassmorphic Themes
│   │   ├── js/                            # Modular SPA Frontend Controllers
│   │   │   ├── core/                      # Core Web Services (`data-service.js`, `nav.js`, `ws-service.js`)
│   │   │   └── panels/                    # UI Panel Logic (`overview.js`, `rca.js`, `fleet.js`, `governance.js`, `models.js`)
│   │   └── models/                        # 3D Avatar Meshes (`WaltHead.obj`)
│   └── templates/                         # HTML5 Modular Template Architecture
│       ├── aios_v11_3_dashboard.html      # Production Master Unified Dashboard
│       ├── assemble.sh                    # Component Compiler Script
│       ├── components/                    # Modal & Toast UI Widgets
│       ├── layouts/                       # Header & Sidebar Base Layouts
│       ├── modules/                       # Specialized Panel Modules
│       └── partials/                      # Reusable HTML Fragment Components
├── scripts/                               # Maintenance, Build, & Automation Tooling
│   ├── build_templates.py                 # HTML Component Assembly Builder
│   ├── generate_sbom_and_scan_sca.sh      # Software Bill of Materials & Security Scanner
│   ├── master_production_readiness_audit.py# Automated Production Gate Verifier
│   ├── migrations/                        # SQL Migration Scripts
│   ├── n8n_gitops_sync.py                 # Sync Tool for n8n Workflows
│   ├── production_hardening_auditor_v2.py # Hardening & Security Audit Script
│   └── verify.sh                          # One-Touch System Verification Script
└── tests/                                 # End-to-End & Integration Test Specifications
    ├── integration/                       # System Integration Tests
    └── unit/                              # Core Unit Tests
```

---

## 3. Subsystem Detailed Specifications

### 3.1. CLIENT_DISTRIBUSI_GO (Cross-Platform Edge Telemetry Agent)
- **Languages:** Go 1.22, C# (.NET WinForms for GUI), Python 3.14 (Linux UI & Tray)
- **Key Responsibilities:**
  1. Low-level resource metric collection (CPU, RAM, Disk I/O, Network interfaces, Process trees, DNS resolution, Printer spooler, Wi-Fi RSSI).
  2. Edge anomaly detection (`edge_anomaly_watcher.go`) with sub-second local threshold evaluation.
  3. Tier-0 automated self-healing (`tier0_self_healing.go`) executing immediate remediation without network roundtrips for known local failures.
  4. Resilient multi-broker NATS connectivity (`nats_failover_client.go`) supporting offline buffer queueing and automatic broker reconnection.
  5. Local WebSocket bridge (`browser_ext_server.go`) interfacing with the Chrome/Edge extension for browser navigation telemetry.

### 3.2. SERVER / GO CORE (High-Throughput Ingestion Engine)
- **Languages:** Go 1.22
- **Key Responsibilities:**
  1. High-throughput log and telemetry ingestion server listening on port **18800**.
  2. Telemetry deduplication, signature generation, and stream normalization.
  3. Telegram Bot integration service (`telegram_service.go`) delivering interactive operator notification buttons for HITL approval queues.
  4. Syslog protocol parser accepting RFC 5424 telemetry from routers, switches, and firewall appliances.

### 3.3. SERVER / PYTHON AI CORE (AI Operating System Core)
- **Languages:** Python 3.14 (AsyncIO)
- **Key Sub-Modules:**
  - **`core/workflow_orchestrator.py`**: Central execution orchestrator managing multi-agent graph workflows, planner-critic consensus, and task dispatching.
  - **`core/semantic_cache_manager.py`**: High-performance semantic vector cache leveraging Redis to deliver sub-20ms cache hits on recurring LLM queries.
  - **`engines/agentic_rag_engine.py` & `engines/rag_engine.py`**: Dynamic hybrid search engine combining BM25 keyword matching with dense pgvector embeddings across GraphRAG L1-L7 layers.
  - **`governance/five_golden_rules_engine.py` & `remediation_guard.py`**: Strict policy enforcement blocking unauthorized command execution (e.g., `rm -rf /` or unapproved router reboots).
  - **`active_probing/`**: Time-travel temporal knowledge graph (`aios_temporal_knowledge_graph.py`) tracking historical topology snapshots across versions (`v6.4.0` to `v11.0.0`). Includes blast radius safety simulator (`safety_simulation_engine.py`).
  - **`learning/` (LF1-LF5 Framework)**: Continuous learning pipeline generating Direct Preference Optimization (DPO) datasets (`dpo_dataset_synthesizer.py`) and orchestrating automated LoRA fine-tuning (`lora_training_pipeline_orchestrator.py`).
  - **`security/auth_guard.py`**: Zero-Trust API Guard enforcing HMAC-HS256 token verification, per-agent rate-limiting, and Role-Based Access Control (RBAC).

### 3.4. SERVER / JARVIS (Voice Assistant & NLU Interface)
- **Languages:** Python 3.14, ONNX Runtime
- **Key Sub-Modules:**
  - **`voice/stt_service.py`**: Faster-Whisper Speech-To-Text engine for real-time speech transcription.
  - **`voice/tts_service.py`**: Kokoro-TTS neural speech synthesizer with fallback parametric WAV generation.
  - **`voice/wake_word_detector.py`**: Real-time openwakeword engine filtering background noise and detecting system triggers ("Jarvis").
  - **`cognition/llm_command_translator.py`**: NLU translator mapping human voice prompts into structured NOC API executions.

### 3.5. PORTAL (NOC Dashboard API Gateway & SPA Backend)
- **Languages:** Go 1.22, Vanilla JavaScript (ES6+), HTML5, CSS3
- **Key Responsibilities:**
  1. Main Dashboard Server (`dashboard_server.go`) serving static assets, HTML5 layouts, and REST API handlers.
  2. WebSocket Hub (`server_ws.go` & `server_chat.go`) streaming live telemetry, topology updates, and NOC operator chat messages.
  3. Interactive Dashboard SPA featuring modular panels (Overview, RCA, Unified DAG, Monitoring, PC Health, Fleet, AI Governance, Training, Storage, Models, RBAC).
  4. Asset management (`asset_api.go`), LDAP Active Directory authentication (`ldap_auth.go`), and Known Error Database (KEDB) runbook matching.

### 3.6. INFRASTRUCTURE & DOCKER SERVICES
- **PostgreSQL 16 + PGVector**: Core relational and vector database holding GraphRAG L1-L7 topologies, incidents, and embeddings.
- **Redis 7**: Sub-20ms semantic cache, distributed lock coordinator, and session memory store.
- **NATS JetStream 2.10**: High-availability event broker connecting agents, ingestion servers, and AI OS supervisors.
- **Nginx HA**: High-availability reverse proxy and SSL termination gateway (`nginx_ha.conf`).
- **n8n GitOps**: Autonomous workflow automation engine executing post-mortem publishing and SOP vault synchronization.

---

## 4. Subsystem Inter-Communication & Data Flow

```
[ Edge Agent ] --(HTTP / NATS Telemetry Stream)--> [ Go Ingestion Server ]
                                                           |
                                                   (NATS Event Bus)
                                                           v
                                                [ Python AI Supervisor ]
                                                           |
                          +--------------------------------+--------------------------------+
                          |                                |                                |
                          v                                v                                v
              [ RAG & GraphRAG Engine ]       [ Planner-Critic Engine ]       [ Governance & Safety Guard ]
                          |                                |                                |
                          +--------------------------------+--------------------------------+
                                                           |
                                                   (API Execution)
                                                           v
                                                [ Go Portal Server ]
                                                           |
                                               (WebSocket Stream / REST)
                                                           v
                                            [ NOC Operator Dashboard UI ]
```

---

## 5. Verification & Maintenance Commands

- **Python Core Syntax Verification**:
  ```bash
  python3 -m compileall SERVER/ tests/ scripts/ -q
  ```
- **Python Unit Test Execution**:
  ```bash
  PYTHONPATH=SERVER/python_ai_core python3 -m unittest discover -s SERVER/python_ai_core/tests/
  ```
- **Go Portal Compilation**:
  ```bash
  cd portal && go build ./... && go test ./...
  ```
- **Linux Agent Build & Package**:
  ```bash
  cd CLIENT_DISTRIBUSI_GO/linux_agent && ./build_deb.sh
  ```
- **Full Production Hardening Audit**:
  ```bash
  python3 scripts/production_hardening_auditor_v2.py
  ```

---
*Document compiled and verified against Enterprise AIOS Repository Commit Head.*
