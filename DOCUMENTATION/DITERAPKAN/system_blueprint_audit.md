# 🔍 LIVE SYSTEM AUDIT BLUEPRINT — OSI Incident Analysis
> **Diaudit pada:** 2026-07-04 16:15 WIB  
> **Metode:** Langsung dari proses, container, port, dan database yang berjalan (bukan dari dokumentasi)

---

## 1. 🖥️ HARDWARE & OS

| Item | Detail |
|---|---|
| **OS** | Ubuntu 26.04 LTS (Resolute Raccoon) |
| **Kernel** | Linux 7.0.0-27-generic |
| **CPU** | Intel Core i5-4210U @ 1.70GHz (2 core / 4 thread) |
| **RAM** | 7.2 GiB total / 4.8 GiB used / 2.4 GiB available |
| **Swap** | 4.0 GiB total / 2.4 GiB used |
| **Disk** | 233 GB (119 GB used / 103 GB free — 54%) |
| **NIC Aktif** | `enp7s0` IP: **10.20.0.163/24** |
| **Uptime** | 4 jam 49 menit |
| **Load Average** | 0.58 / 2.48 / 4.23 |

---

## 2. 🐳 DOCKER CONTAINERS — STATUS LIVE

| Container | Image | Status | Uptime | Port(s) |
|---|---|---|---|---|
| `osi-nginx` | nginx:1.25-alpine | ✅ Up | 5 jam | 8099→80, 9443→443 |
| `osi-postgres` | pgvector/pgvector:pg15 | ✅ Up (healthy) | 5 jam | 127.0.0.1:5433→5432 |
| `osi-redis` | redis:7-alpine | ✅ Up (healthy) | 5 jam | internal:6379 |
| `osi-nats` | nats:2.9-alpine | ✅ Up | 4 jam | 4222→4222 |
| `osi-ingestion-server` | incident-analysis-ingestion-server | ✅ Up | 5 jam | 18800, 18802, 19999 |
| `osi-secure-relay` | b93067e3ed16 | ✅ Up | 5 jam | 9998→9998 |
| `osi-dashboard-server` | incident-analysis-dashboard-server | ✅ Up | 17 menit | internal:9999 |
| `osi-telegram-bot` | incident-analysis-telegram-bot-listener | ✅ Up | 22 menit | — |
| `osi-python-ai-core` | incident-analysis-python-ai-core | ✅ Up | 2 jam | — |
| `osi-portainer` | portainer/portainer-ce | ✅ Up | 5 jam | 9000, 9444 |
| `pgadmin_container` | dpage/pgadmin4:8.4 | ✅ Up | 5 jam | 5051→80 |
| `n8n_workflow_engine` | n8nio/n8n:latest | ✅ Up | 5 jam | 5678→5678 |
| `netdata_master` | netdata/netdata | ✅ Up (healthy) | 5 jam | 19999, 8125 UDP |

---

## 3. 📡 PORT MAP LENGKAP

| Port | Protokol | Service | Akses |
|---|---|---|---|
| 4222 | TCP | NATS Message Broker | Internal Docker + Host |
| 5051 | TCP | pgAdmin 4 Web UI | Public |
| 5432 | TCP | PostgreSQL (host native) | localhost only |
| 5433 | TCP | PostgreSQL (Docker) | 127.0.0.1 only |
| 5678 | TCP | n8n Workflow Engine | Public |
| 6379 | TCP | Redis | localhost only |
| 7070 | TCP | LAUNCHER_SERVICE_GO (Windows clients) | Public |
| 8099 | TCP | Nginx HTTP → redirect HTTPS | Public |
| 8125 | UDP | Netdata StatsD | Public |
| 9000 | TCP | Portainer HTTP | Public |
| 9443 | TCP | Nginx HTTPS (Dashboard) | Public |
| 9444 | TCP | Portainer HTTPS | Public |
| 9998 | TCP | Secure Relay (Agent→Server) | Public |
| 18800 | TCP | Ingestion Server (Agent data) | Public |
| 18802 | TCP | Ingestion Server WebSocket | Public |
| 19999 | TCP | Netdata Dashboard | Public |
| 22 | TCP | SSH Server | Public |

---

## 4. 🔧 DOCKER NETWORKS

| Network | Driver | Subnet | Digunakan oleh |
|---|---|---|---|
| `incident-analysis_osi-backend` | bridge | 172.18.0.0/16 | ingestion, postgres, redis, nats, ai-core, telegram, relay |
| `incident-analysis_osi-frontend` | bridge | 172.19.0.0/16 | nginx, dashboard, portainer |
| `n8n_docker_n8n_network` | bridge | 172.20.0.0/16 | n8n, netdata |
| `bridge` (docker0) | bridge | 172.17.0.0/16 | default |

---

## 5. 🗄️ DATABASE — PostgreSQL (osi_system)

### Extensions Aktif
| Extension | Version |
|---|---|
| plpgsql | 1.0 |
| **pgvector** | **0.8.3** (vector AI search) |

### Live Data Count
| Tabel | Records |
|---|---|
| incidents | 69 |
| devices | 2 |
| chat_messages | **216,487** |
| fleet_incidents | **74,665** |
| incident_events | **178,285** |

### Tabel-tabel Kunci (95 total)
| Kategori | Tabel |
|---|---|
| **Core Incident** | incidents, incident_events, incident_states, incident_assignments, incident_closure, incident_acknowledgements, incident_feedback, incident_post_mortems |
| **Fleet** | fleet_incidents, fleet_devices, fleet_sites, fleet_networks, fleet_services, fleet_processes, fleet_printers, fleet_usbs, fleet_topology, fleet_evidence |
| **AI Engine** | ai_audit_trail, ai_reflection_logs, ai_approval_logs, ai_blast_radius_logs, ai_evidence_logs, ai_confidence_calibration, ai_metrics |
| **Policy & Governance** | policy_rules, policy_versions, policy_snapshots, policy_audit_trail, opa_policy_rules, rbac_policies, governance_sops, governance_approvals |
| **Approval / HITL** | approval_queue, approval_events, approval_outbox, hitl_audit_logs, operator_profiles, operator_presence, operator_answers |
| **Chat / Telegram** | chat_messages, chat_sessions, chat_archive, chat_feedback, telegram_chat_mappings |
| **Security** | security_events, security_policy_rules, immutable_audit_log, system_audits |
| **Rollback / Remediation** | rollback_policies, rollback_events, rollback_logs, retry_history, pending_remediations |
| **Knowledge / RAG** | knowledge_vectors, rag_historical_logs, golden_resolutions, golden_solutions |
| **Telemetry** | telemetry_logs (partitioned), telemetry_logs_y2026m05..m10 |
| **Trust / Verification** | agent_trust_scores, agent_heartbeats, verification_logs, verification_events, trace_integrity_reports |
| **Misc** | decision_graphs, dependency_map, network_paths, cmdb_assets, blast_radius_registry, escalation_rules, escalation_log, dlq_hybrid, idempotency_registry |

### Top Tabel by Size
| Tabel | Ukuran |
|---|---|
| chat_messages | **192 MB** |
| incident_events | **80 MB** |
| fleet_incidents | **61 MB** |
| escalation_log | **31 MB** |
| devices | 736 kB |

---

## 6. 🧠 PYTHON AI CORE — Modul Engine

Running sebagai: `osi-python-ai-core` Docker container (terlihat di host dengan PID 189255)

### Engine Modules (SERVER/python_ai_core/)
| File | Fungsi |
|---|---|
| `ai_supervisor.py` (89 KB) | **Orchestrator utama** — menerima event NATS, memanggil semua engine, logging pipeline AI |
| `state_machine.py` | FSM (Finite State Machine) untuk lifecycle incident |
| `escalation_engine.py` | Auto-escalation berdasarkan severity & SLA |
| `closure_engine.py` | Enforcement penutupan incident |
| `presence_daemon.py` | Monitor kehadiran operator (HITL) |
| `blast_radius_engine.py` | Kalkulasi dampak blast radius incident |
| `replay_engine.py` | Simulasi & replay scenario incident |
| `policy_engine.py` | Evaluasi policy OPA-style |
| `critic_engine.py` | AI self-critic & confidence scoring |
| `consensus_engine.py` | Voting multi-model LLM |
| `trust_engine.py` | Agent trust score management |
| `llm_router.py` | Routing ke LLM berdasarkan severity & cost |
| `question_engine.py` | Klarifikasi pertanyaan ke operator |
| `rag_engine.py` | Retrieval-Augmented Generation (pgvector) |
| `counterfactual_engine.py` | What-if analysis |
| `audit_logger.py` | Immutable audit trail |

### Agent Modules (agents/)
| Agent | Fungsi |
|---|---|
| `incident_agent.py` | Analisis & diagnosis incident |
| `security_agent.py` | Deteksi ancaman keamanan |
| `recovery_agent.py` | Eksekusi remediation |
| `verification_agent.py` | Verifikasi hasil remediasi |

### Core Modules (core/)
| Module | Fungsi |
|---|---|
| `correlation_engine.py` | Korelasi event lintas-device |
| `approval_engine.py` | Gate approval HITL |
| `approval_queue.py` | Antrian persetujuan operator |
| `causal_mapper.py` | Peta kausalitas incident |
| `timeline_builder.py` | Membangun timeline event |
| `anomaly_cluster.py` | Clustering anomali |

### LLM Providers (dari ai_config.json — LIVE)
| Provider | Model | Status |
|---|---|---|
| **Google Gemini** | gemini-2.5-flash | ✅ Active |
| **Groq** | Llama-3.1 | ✅ Active (fallback/low-severity) |
| **DeepSeek** | DeepSeek Opus | ✅ Active (consensus) |

---

## 7. 🌐 GO INGESTION SERVER — Modul

Running sebagai: `osi-ingestion-server` Docker container (terlihat di host dengan PID 6236)

### Source Modules (SERVER/go_core/ingestion/)
| File | Fungsi |
|---|---|
| `ingestion_server.go` | Server utama: terima telemetri dari agent Windows (port 18800 TCP, 18802 WebSocket) |
| `incident_service.go` | Pembuatan & klasifikasi incident |
| `ai_analysis_service.go` | Bridge ke AI pipeline via NATS |
| `chat_service.go` | Injeksi notifikasi ke chat_messages |
| `telegram_service.go` | Forward notifikasi ke Telegram |
| `normalization.go` | Normalisasi & validasi payload telemetri |

### Packages pendukung
| Package | Fungsi |
|---|---|
| `config/` | Konfigurasi env |
| `database/` | Koneksi PostgreSQL |
| `security/` | HMAC-SHA256 token validation |
| `hardening/` | File descriptor & OS hardening |
| `ai/` | AI analysis integration |
| `collector/` | Data collector |
| `logger/` | Structured logging |
| `telegram_bot/` | Telegram bot listener |

---

## 8. 🖥️ DASHBOARD SERVER — Go Portal

Running sebagai: `osi-dashboard-server` Docker container (terlihat di host dengan PID 189248)

### Files (portal/)
| File | Fungsi |
|---|---|
| `dashboard_server.go` (282 KB) | **Server utama** — REST API + WebSocket + embedded HTML/JS frontend |
| `chat_engine.go` (30 KB) | Engine chat real-time dengan AI |
| `state_machine.go` (8.4 KB) | FSM dashboard side |
| `ldap_auth.go` | Autentikasi LDAP |
| `ai_config.json` | Konfigurasi LLM provider |
| `remote_settings.json` | Konfigurasi remote desktop (AnyDesk, RustDesk, VNC) |

Nginx proxy: `osi-nginx` → forward ke `osi-dashboard-server:9999` via HTTPS TLS 1.2/1.3

---

## 9. 📱 TELEGRAM BOT

Running sebagai: `osi-telegram-bot` Docker container (terlihat di host dengan PID 207341)

- **File**: `SERVER/go_core/telegram_bot/telegram_bot_listener.go` (35 KB)
- **Bot Token**: Configured via env `TELEGRAM_BOT_TOKEN`
- **Chat ID**: `7794987703`
- **Status Live**: Connected ke NATS + PostgreSQL, menunggu perintah
- **Log**: Bersih (polling timeout ditangani secara senyap tanpa log bising)
- **Fitur**: Menerima approval HITL dari operator via Telegram command

---

## 10. 🔌 SECURE RELAY

- **Container**: `osi-secure-relay` (port 9998)
- **Fungsi**: Relay aman antara Windows client agent dan server backend
- **Dockerfile**: `portal/Dockerfile.secure_relay`
- **Auth**: via `OSI_SECURITY_KEY`

---

## 11. 💻 CLIENT AGENT (Windows)

| Komponen | File | Fungsi |
|---|---|---|
| **Agent** | `CLIENT_DISTRIBUSI_GO/agent/agent.exe` (9.8 MB) | Main agent Windows — kirim telemetri ke port 18800 |
| **Agent Tray** | `agent_tray.exe` | System tray UI di Windows |
| **Installer** | `CLIENT_DISTRIBUSI_GO/installer/installer.exe` | Setup installer Windows |
| **Updater** | `CLIENT_DISTRIBUSI_GO/updater/updater.exe` | Auto-updater OTA |
| **Launcher** | `LAUNCHER_SERVICE_GO/LAUNCHER_SERVICE_GO.exe` | Windows service launcher |
| **Chrome Ext** | `chrome_extension/` | Browser extension monitoring |

**Source**: `main.go` (Go) + `ChatForm.cs` + `tray.cs` (C# WinForms UI)

Agent terhubung dari IP: `10.20.0.49` (terlihat di log ingestion)

---

## 12. 🔄 NATS MESSAGE BROKER

- **Version**: nats-server v2.9.25
- **Config**: JetStream enabled, max_mem: 1G, max_file: 10G
- **Max Connections**: 1000, Max Payload: 1MB
- **Status**: ✅ Up 4 jam, Net I/O: 183 MB in / 1.77 MB out

---

## 13. 📊 RESOURCE USAGE LIVE

| Container | CPU | RAM | Net I/O |
|---|---|---|---|
| osi-redis | **4.45%** | 2.7 MB | 1.72/0.93 MB |
| netdata_master | 1.69% | 118 MB | 65/40 kB |
| osi-dashboard-server | 0.26% | 8.5 MB | 1.12/1.26 MB |
| n8n_workflow_engine | 0.18% | **200 MB** | 166/80 kB |
| osi-python-ai-core | 0.02% | 17 MB | 37/171 MB |
| osi-ingestion-server | 0.05% | 14.8 MB | 6.5/9.6 MB |
| osi-postgres | 0.13% | **189 MB** | 550/151 MB |
| osi-portainer | 0.03% | 21 MB | 214/80 kB |

---

## 14. 🔐 SECURITY LAYER

| Layer | Mekanisme |
|---|---|
| **Transport** | TLS 1.2/1.3 (Nginx), HMAC-SHA256 token (agent auth) |
| **API Auth** | JWT (`JWT_SECRET_KEY`) + `OSI_SECURITY_KEY` |
| **RBAC** | Tabel `rbac_policies` di PostgreSQL |
| **Audit** | Tabel `immutable_audit_log`, `system_audits`, `ai_audit_trail` |
| **Telegram** | `AUTHORIZED_ADMINS` whitelist |
| **Remote Passwords** | Fernet-encrypted di `remote_settings.json` |
| **Security Headers** | X-Frame-Options, CSP, HSTS, X-XSS-Protection via Nginx |

---

## 15. 🔁 ALUR DATA (DATA FLOW)

```
[Windows Agent 10.20.0.49]
       |
       | TCP 18800 (telemetri) / WS 18802
       v
[osi-ingestion-server] ─────► [osi-postgres] (simpan telemetri)
       |                              |
       | NATS publish                 |
       v                              |
[osi-nats :4222]                      |
       |                              |
       v                              |
[osi-python-ai-core]                  |
  ├── RAG Engine ←────────── [pgvector] (knowledge_vectors)
  ├── LLM Router → Gemini / Groq / DeepSeek (external API)
  ├── Consensus Engine
  ├── Critic Engine
  ├── Policy Engine
  ├── State Machine
  ├── Blast Radius Engine
  ├── Escalation Engine
  ├── HITL Approval Gate ──► [osi-telegram-bot] ──► Telegram Operator
  ├── Closure Engine
  └── Replay Engine
       |
       | (hasil analisis → NATS → DB)
       v
[osi-dashboard-server :9999]
  ├── REST API (incidents, devices, chat, policy, fleet)
  ├── WebSocket (real-time logs /ws/)
  ├── Chat Engine (AI chat interface)
  └── Embedded HTML/JS Frontend
       |
       v
[osi-nginx :8099/9443]
  └── HTTPS Proxy → Browser Operator
       
[osi-secure-relay :9998]
  └── Relay Windows agent → backend (untuk remote session)

[n8n :5678] ── Workflow automation (terpisah, jaringan n8n_network)
[netdata :19999] ── Monitoring resource server
[Portainer :9000] ── Docker management UI
[pgAdmin :5051] ── Database management UI
```

---

## 16. 🗺️ ARSITEKTUR DIAGRAM

```
┌─────────────────────────────────────────────────────────────────┐
│                    INTERNET / OPERATOR                           │
└──────────┬────────────────────────────────────────┬─────────────┘
           │ HTTPS :9443                             │ Telegram API
           v                                         v
┌──────────────────┐                    ┌────────────────────────┐
│   osi-nginx      │                    │  osi-telegram-bot      │
│  (Reverse Proxy) │                    │  (Go binary, port N/A) │
│  TLS 1.2/1.3     │                    └─────────┬──────────────┘
└────────┬─────────┘                              │
         │ :9999 (internal)                       │
         v                                        │
┌──────────────────────┐                          │
│  osi-dashboard-server│◄─────────────────────────┘
│  (Go, embed HTML/JS) │        NATS publish/subscribe
│  REST API + WS       │◄──────────────────────────────────────┐
└──────────┬───────────┘                                       │
           │ SQL                                               │
           v                                                   │
┌──────────────────────┐     ┌────────────────┐    ┌──────────┴───────────┐
│   osi-postgres       │◄────│   osi-redis    │    │  osi-python-ai-core  │
│   (pgvector pg15)    │     │   (cache/lock) │    │  (AI Supervisor)     │
│   95 tables          │     └────────────────┘    │  ┌─ LLM Router       │
│   192MB chat data    │                           │  │  ├ Gemini 2.5     │
└──────────────────────┘                           │  │  ├ Groq Llama     │
           ^                                       │  │  └ DeepSeek       │
           │ SQL                                   │  ├─ RAG Engine       │
           │                                       │  ├─ State Machine    │
┌──────────┴───────────┐     ┌────────────────┐   │  ├─ Policy Engine    │
│  osi-ingestion-server│────►│   osi-nats     │──►│  ├─ Escalation Eng.  │
│  (Go, :18800/:18802) │     │   (:4222 NATS) │   │  ├─ Blast Radius     │
│  HMAC-SHA256 auth    │     │   JetStream    │   │  ├─ Consensus Eng.   │
└──────────┬───────────┘     └────────────────┘   │  ├─ Critic Engine    │
           │ :18800 TCP                            │  ├─ Closure Engine   │
           │ :18802 WS                             │  └─ Replay Engine    │
           v                                       └──────────────────────┘
┌──────────────────────┐
│  Windows Client Agent│     ┌────────────────┐   ┌──────────────────────┐
│  (10.20.0.49)        │     │ osi-secure-relay│  │  TOOLS               │
│  agent.exe           │────►│  (:9998)        │  │  ├ n8n :5678         │
│  ChatForm.cs (UI)    │     └────────────────┘   │  ├ netdata :19999    │
│  Launcher Service    │                           │  ├ portainer :9000   │
│  Chrome Extension    │                           │  └ pgadmin :5051     │
└──────────────────────┘                           └──────────────────────┘
```

---

## 17. 📋 SYSTEMD SERVICES (HOST)

| Service | Status |
|---|---|
| `docker.service` | ✅ running |
| `postgresql@18-main.service` | 🛑 stopped (inactive) |
| `redis-server.service` | 🛑 stopped (inactive) |
| `ssh.service` | ✅ running |
| `anydesk.service` | ✅ running |
| `containerd.service` | ✅ running |
| `cron.service` | ✅ running |

> ⚠️ Catatan: Sebelumnya PostgreSQL dan Redis berjalan **dua kali** (host native dan Docker). Sekarang kedua service native di level host tersebut telah dihentikan, sehingga hanya versi Docker yang berjalan aktif.

---

## 18. ⚠️ TEMUAN AUDIT

| # | Temuan | Severity | Keterangan |
|---|---|---|---|
| 1 | **Redis berjalan duplikat** | 🟢 OK | Native service dihentikan (`systemctl stop redis-server`). Hanya versi Docker yang berjalan. |
| 2 | **PostgreSQL berjalan duplikat** | 🟢 OK | Native service dihentikan (`systemctl stop postgresql`). Hanya versi Docker yang berjalan. |
| 3 | **API Keys di ai_config.json plaintext** | 🟢 OK | Kunci API Gemini, Groq, dan DeepSeek telah dienkripsi menggunakan AES-256 Fernet (menggunakan `OSI_SECURITY_KEY`). |
| 4 | **Telegram Bot polling timeout** | 🟢 OK | Polling timeout diatur ke 15 detik (dengan client timeout 30 detik) untuk membuat margin yang aman, dan log timeout ditangani secara senyap. |
| 5 | **Swap Usage Tinggi** | 🟡 Medium | 3.2 GiB dari 4 GiB swap terpakai. Sisa RAM fisik cukup wajar (2.6 GiB tersedia). Rekomendasi: Jalankan `sudo swapoff -a && sudo swapon -a` untuk membersihkan swap. |
| 6 | **n8n memory 200 MB** | 🟢 Low | n8n adalah consumer RAM terbesar setelah postgres, normal untuk workflow engine. |
| 7 | **Port 7070 tanpa proses jelas** | 🟢 OK | Port 7070 digunakan secara sah oleh `anydesk.service` di level host untuk incoming direct connections. |
| 8 | **Telegram AUTHORIZED_ADMINS** | 🟢 OK | Diubah ke Telegram ID real: `7794987703` |
| 9 | **Swap aktif dari kernel boot** | 🟢 Low | Normal pada sistem dengan RAM terbatas. |
| 10 | **216K+ chat messages** | 🟢 Info | Volume data tinggi — perlu monitoring pertumbuhan tabel. |
| 11 | **Potensi Token Bloom di Context AI** | 🟢 OK | Dibatasi dengan Chat Context Cap (H3) maksimum 50 pesan terakhir secara kronologis untuk mencegah latensi tinggi. |
| 12 | **Duplikasi Pesan NATS saat Reconnect** | 🟢 OK | Ditangani dengan NATS Deduplication Key (H4) menggunakan UUID unik (`message_id`) pada event payload dan cache `sync.Map` di subscriber. |
| 13 | **Divergensi Dokumen Awal vs DB Riil** | 🟢 OK | Telah diaudit dan dipetakan dalam `auditsystem_delta_report.md`. Struktur database riil (95 tabel) sudah selaras dengan fungsionalitas produksi (seperti pemisahan `fleet_incidents` & `incidents`, `incident_states`, `incident_closure`, dll.). |
| 14 | **Race Condition Mutasi Host** | 🟢 OK | Ditangani dengan P11 Hybrid Lock Engine (Redis SET NX PX + Postgres `host_execution_locks` sebagai fallback/audit trail). |
| 15 | **Bypass Resolution Bukti Palsu** | 🟢 OK | Ditangani dengan P13 Strict Closure Quorum (validasi wajib `verification_logs` bersih dalam 30 menit terakhir sebelum penutupan). |
| 16 | **Linis/Lineage Bukti Terfragmentasi** | 🟢 OK | Ditangani dengan P12 Unified Evidence DAG API (`/api/incidents/:id/evidence_dag`) yang menggabungkan seluruh trace audit. |
| 17 | **Resolusi Statis Tanpa Feedback Loop** | 🟢 OK | Ditangani dengan P15 Knowledge Graph Edges (`knowledge_edges` table + `KnowledgeEdgeManager` dengan rumus evolusi berbasis pgvector). |
| 18 | **Imbalance NATS Telemetry Traffic** | 🟢 OK | Hasil audit JetStream (port 8222) memastikan 0 lag/redeliveries. Disparitas murni dari behavior design producer-heavy telemetry. |

---

## 19. 📦 DOCKER VOLUMES

| Volume | Digunakan oleh |
|---|---|
| `incident-analysis_postgres_data` | osi-postgres (data persisten) |
| `incident-analysis_redis_data` | osi-redis (data persisten) |
| `incident-analysis_nats_data` | osi-nats (JetStream storage) |
| `incident-analysis_portainer_data` | osi-portainer |

---

## 20. 📂 STRUKTUR DIREKTORI PROJECT

```
/home/it-itsm/AI/incident-analysis/
├── docker-compose.yml          # Orkestrasi semua container
├── .env                        # Konfigurasi environment
├── docker/
│   ├── nginx/nginx_ha.conf     # Nginx reverse proxy config
│   ├── nginx/certs/            # SSL certificate
│   ├── postgres/init/          # Init SQL schema
│   ├── redis/redis.conf        # Redis config
│   └── nats/nats-server.conf   # NATS JetStream config
├── SERVER/
│   ├── go_core/                # Go Ingestion Server
│   │   ├── ingestion/          # Core ingestion modules
│   │   ├── telegram_bot/       # Telegram bot
│   │   ├── ai/, config/, database/, hardening/, security/, logger/
│   │   └── ingestion_server    # Binary Linux
│   └── python_ai_core/         # Python AI Engine
│       ├── ai_supervisor.py    # Orchestrator (89KB)
│       ├── agents/             # 4 AI agents
│       ├── core/               # 6 core modules
│       ├── schemas/            # 7 Pydantic schemas
│       ├── verification/       # Rollback & health check
│       └── *_engine.py         # 12 specialized engines
├── portal/
│   ├── dashboard_server.go     # Dashboard + REST API (282KB)
│   ├── chat_engine.go          # Real-time chat AI (30KB)
│   ├── dashboard_server        # Binary Linux (44MB)
│   └── templates/, static/     # Frontend assets
├── CLIENT_DISTRIBUSI_GO/
│   ├── agent/                  # Windows agent (Go + C#)
│   ├── installer/              # Windows installer
│   └── updater/                # Auto-updater
├── LAUNCHER_SERVICE_GO/        # Windows service launcher
├── chrome_extension/           # Browser extension
├── n8n_docker/                 # n8n workflow data
└── OSI_SERVER_MIGRATION_v2.0.0/ # Migration package
```

---

*Audit selesai — semua data diambil langsung dari sistem live pada 2026-07-04 10:51 WIB*

---

## 21. OPTIMALISASI KINERJA SISTEM — PHASE 1 (COMPLETED)

Untuk mengatasi hambatan throughput (throughput path), kerentanan connection starvation, dan lock contention pada database, optimalisasi berikut telah diimplementasikan dan diuji:

### A. Asynchronous Verification Worker Pool (TCP Ingestion)
* **Sebelum:** Koneksi TCP yang masuk diparse dan diverifikasi HMAC SHA-256 secara sinkron pada read thread koneksi sebelum merespons, yang berpotensi menyebabkan connection starvation di bawah beban konkurensi tinggi.
* **Sesudah:** Pemrosesan koneksi didecouple dari verifikasi menggunakan buffered channel (`verifyQueue` berkapasitas 20,000) dan pool worker asinkron berkapasitas `runtime.NumCPU() * 2` (8 parallel worker). Hal ini mencegah pemblokiran socket TCP selama lonjakan trafik verifikasi.

### B. Adaptive Batch Telemetry/Log Flushing
* **Sebelum:** Batch write statis dengan ukuran 50 item dan interval tick 1 detik menyebabkan frekuensi database batch execution tinggi dan meningkatkan lock contention.
* **Sesudah:** Kapasitas buffer ditingkatkan menjadi 200 item. Menggunakan model flush adaptif: langsung melakukan flush jika buffer mencapai 200 item, atau melakukan partial flush jika antrean idle selama lebih dari 2 detik (dengan mereset timer idle saat flush terjadi).

### C. NATS JetStream Consumer Tuning (`max_ack_pending`)
* **Sebelum:** Subscription NATS JetStream untuk konsumen spesifik situs dan catch-all legacy menggunakan `max_ack_pending = 1`, yang membatasi pemrosesan pesan menjadi sekuensial ketat.
* **Sesudah:** Nilai `max_ack_pending` ditingkatkan dari `1` menjadi `128` pada file `ai_supervisor.py` untuk seluruh konfigurasi subscriber. Konsumen kini dapat memproses dan meng-acknowledge window pesan secara konkuren, mengeliminasi lag pengiriman.

### D. Covering Indexes Database untuk Contention Path
* **Sebelum:** Query filter penting pada tabel transaksi mengalami scan tabel sekuensial karena kurangnya indexing yang optimal.
* **Sesudah:** Indeks covering baru ditambahkan untuk tabel-tabel transaksi utama:
  * `fleet_incidents(status, site_id, severity)`
  * `verification_logs(incident_id, created_at DESC)`
  * `host_execution_locks(hostname, expires_at)`
  * `chat_messages(incident_id, created_at DESC)`
  * `processed_messages(message_id)`

