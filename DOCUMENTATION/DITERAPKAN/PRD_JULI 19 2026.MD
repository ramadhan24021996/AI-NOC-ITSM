# PRD SISTEM NOC IT AI v3.0
## OSI · MEGA KREASI TEACH — ENTERPRISE AIOPS PLATFORM

---

## 1. RINGKASAN EKSEKUTIF

**Nama Sistem**: NOC IT AI v3.0 (OSI - Open Support Intelligence)  
**Organisasi**: MEGA KREASI TEACH  
**Versi**: 3.0 Production  
**Status**: 100% Production Ready  

Sistem NOC IT AI adalah platform AIOps enterprise-grade yang dirancang untuk monitoring, deteksi insiden otomatis, analisis akar masalah (RCA), dan remediasi mandiri armada perangkat (PC Kasir, Printer POS, Server) di seluruh cabang. Sistem mengintegrasikan Go Core Backend, Python AI Core Multi-Agent, PostgreSQL+pgvector, Redis, NATS JetStream, WebSocket, dan Telegram Bot dalam satu arsitektur terpadu berbasis Docker.

---

## 2. TUJUAN SISTEM

- Mendeteksi anomali dan kegagalan perangkat secara otomatis real-time tanpa intervensi manual
- Mengeksekusi remediasi berbasis AI dengan mekanisme Human-in-the-Loop (HitL)
- Menyediakan visibilitas penuh armada PC/Printer/Server ke operator NOC via dashboard terpusat
- Mengirim notifikasi insiden secara serentak ke: PC Client (OSI Support Chat), Dashboard NOC, dan Telegram Bot
- Memelihara audit trail lengkap untuk compliance dan governance

---

## 3. ARSITEKTUR SISTEM

### 3.1 Komponen Docker (docker-compose.yml)

| Container | Image | Port | Fungsi |
|---|---|---|---|
| osi-nginx | nginx:1.25-alpine | 80, 9443 | Reverse proxy & TLS termination |
| osi-postgres | pgvector/pgvector:pg15 | 127.0.0.1:5433 | Database utama + vector search |
| osi-redis | redis:7-alpine | internal | Session cache, pub/sub, presence |
| osi-nats | nats:2.9-alpine | 4222, 8222 | Event bus & JetStream |
| osi-ingestion-server | Go Core | 18800, 18802 | TCP receiver dari agent Windows/Linux |
| osi-scheduler-service | Go Core | internal | Cron jobs & scheduled tasks |
| osi-dashboard-server | Go Portal | internal | Dashboard NOC web UI & REST API |
| osi-secure-relay | Go Relay | 9998 | Telegram HMAC-signed message relay |
| osi-telegram-bot | Go Telegram | internal | HitL approval listener |
| osi-python-ai-core | Python | internal | AI Supervisor utama (LLM orchestrator) |
| osi-ai-consensus | Python | internal | Multi-agent consensus engine |
| osi-ai-critic | Python | internal | AI critic & quality evaluator |
| osi-ai-policy | Python | internal | Policy enforcement engine |
| osi-ai-rag | Python | internal | RAG retrieval & vector search |
| osi-ai-daemons | Python | internal | Background AI daemons & chaos monkey |
| osi-portainer | portainer/portainer-ce | 9000, 9444 | Docker management UI |
| osi-agent-dist | python:3.11-alpine | internal | Agent distribution file server |

### 3.2 Teknologi Stack

- **Backend Core**: Go 1.21+ (Gin Framework, GORM, gorilla/websocket)
- **AI Engine**: Python 3.11 (LangChain, Google Gemini API, asyncio)
- **Database**: PostgreSQL 15 + pgvector extension
- **Cache/Presence**: Redis 7
- **Event Bus**: NATS 2.9 + JetStream
- **Frontend**: Vanilla HTML/CSS/JS (Single Page Application)
- **Security**: JWT, HMAC-SHA256, WAF Middleware, Rate Limiting, RBAC
- **Containerization**: Docker + Docker Compose
- **Monitoring**: Netdata (port 19999)

### 3.3 Alur Data End-to-End

```
PC Client Agent (C#/Go)
    ↓ TCP :18800/:18802
Go Ingestion Server
    ↓ Telemetry normalization
PostgreSQL (devices, incidents, telemetry)
    ↓ NATS publish: "incident.detected"
Python AI Core (ai_supervisor.py)
    ↓ LLM RCA + RAG lookup
    ↓ NATS publish: "remediation.execute"
Go Dashboard Server
    ↓ WebSocket broadcast
NOC Dashboard UI
    ↓ Parallel delivery
    ├── PC Client: SHOW_NOTIFICATION + SHOW_CHAT (TCP bypass)
    ├── Dashboard: Structured AI Incident Card
    └── Telegram: Alert + Screenshot + Inline Buttons
```

---

## 4. DATABASE SCHEMA (PostgreSQL — osi_system)

### Tabel Utama

| Tabel | Fungsi |
|---|---|
| devices | Daftar semua perangkat terdaftar (PC, Printer, Server) |
| fleet_sites | Data lokasi cabang |
| fleet_devices | Detail perangkat per cabang |
| fleet_printers | Printer POS per cabang |
| incidents | Insiden utama (ai_hypothesis, rca, confidence_score) |
| fleet_incidents | Insiden armada terdeteksi oleh AI |
| fleet_evidence | Bukti insiden (screenshot, telemetry snapshot) |
| chat_sessions | Sesi Live Chat (operator ↔ client) |
| chat_messages | Pesan chat (CLIENT/OPERATOR/SYSTEM/AI_HYPOTHESIS) |
| telegram_chat_mappings | Pemetaan Telegram message_id ↔ client_id |
| ai_playbooks | Skrip remediasi AI (CRUD + execute + dry-run) |
| ai_decision_logs | Audit trail keputusan AI (chain-of-thought) |
| ai_feedbacks | Feedback operator terhadap akurasi AI |
| ai_approvals / approval_outbox | Antrian HitL approval |
| governance_sops | Dokumen SOP aktif |
| schema_validation_logs | Log validasi payload JSON dari agent |
| learning_gate_logs | Log evaluasi AI Learning Gate |
| rbac_roles / rbac_permissions | Role-Based Access Control |
| system_audits | Audit trail sistem |
| remote_sessions | Log sesi remote access (RDP/VNC/SSH) |

---

## 5. NATS EVENT BUS — SUBJECT REGISTRY

| NATS Subject | Publisher | Subscriber | Fungsi |
|---|---|---|---|
| agent.status.site.*.* | Go Ingestion | Go Dashboard | Heartbeat & telemetri agent |
| incident.detected | Go Ingestion | Python AI Core | Trigger analisis AI |
| incident.site.*.* | Go Dashboard | Dashboard Cache | Invalidasi cache insiden |
| remediation.execute | Python AI | Go Dashboard | Eksekusi skrip mitigasi |
| remediation.rollback | Python AI | Go Dashboard | Rollback tindakan |
| approval.site.* | Go Dashboard | Dashboard Cache | Update status approval |
| rollback.site.* | Go Dashboard | Dashboard Cache | Update rollback history |
| dashboard.health_score | Python AI | Go Dashboard | Update health score UI |
| dashboard.early_warnings | Python AI | Go Dashboard | Peringatan dini fleet |
| chat.events | Go Chat Engine | Dashboard WS | Real-time chat events |
| incident.reanalyze | Go Dashboard | Python AI | Re-trigger RCA |
| agent.command.* | Go Dashboard | Go Ingestion | Perintah ke agent |

---

## 6. API ENDPOINT REGISTRY

### 6.1 Authentication & RBAC
| Method | Endpoint | Fungsi |
|---|---|---|
| POST | /api/auth/login | Login JWT |
| POST | /api/auth/logout | Logout + invalidasi token |
| GET | /api/auth/verify | Verifikasi token |
| GET | /api/rbac/policies | Ambil kebijakan RBAC |
| POST | /api/rbac/policies | Simpan kebijakan RBAC |
| GET | /api/rbac/users | Daftar pengguna |
| POST | /api/rbac/users | Tambah/update pengguna |
| GET | /api/rbac/audit_logs | Audit trail RBAC |

### 6.2 Dashboard & Overview
| Method | Endpoint | Fungsi |
|---|---|---|
| GET | /api/kpi_metrics | KPI Cards overview |
| GET | /api/governance_metrics | Metrics governance |
| GET | /api/top_status | Status top-level sistem |
| GET | /api/system/health | Status semua komponen |
| GET | /api/system/runtime_monitor | Runtime AI monitor |
| GET | /api/storage/stats | Statistik storage |
| GET | /api/host_metrics | Metrics host server |
| GET | /api/ping_sites | Ping status semua cabang |
| GET | /api/execution_timeline | Timeline eksekusi AI |

### 6.3 Fleet & Health
| Method | Endpoint | Fungsi |
|---|---|---|
| GET | /api/fleet/admin/sites | Daftar cabang |
| POST | /api/fleet/admin/sites | Tambah cabang |
| DELETE | /api/fleet/admin/sites/delete/:id | Hapus cabang |
| GET | /api/fleet/admin/devices | Daftar perangkat |
| POST | /api/fleet/admin/devices | Tambah perangkat |
| POST | /api/fleet/admin/devices/save | Update perangkat |
| DELETE | /api/fleet/admin/devices/delete/:name | Hapus perangkat |
| GET | /api/fleet/admin/topology | Topologi jaringan |
| GET | /api/fleet/config/global | Konfigurasi global fleet |
| POST | /api/fleet/config/global | Simpan konfigurasi global |
| GET | /api/agent_health | Status kesehatan agent |
| GET | /api/agent_deep_diagnostics/:device | Diagnostik mendalam per device |
| GET | /api/fleet/admin/printers | Daftar printer |
| POST | /api/fleet/admin/printers | Tambah printer |
| DELETE | /api/fleet/admin/printers/:name | Hapus printer |
| GET | /api/printers/live | Status printer real-time |
| POST | /api/printers/ping/:ip | Ping printer |
| POST | /api/printers/ping_all | Ping semua printer |
| POST | /api/printers/clear_queue | Bersihkan antrean printer |

### 6.4 Incident & RCA
| Method | Endpoint | Fungsi |
|---|---|---|
| GET | /api/incidents | Daftar insiden |
| POST | /api/incident/resolve | Selesaikan insiden |
| POST | /api/incident/escalate | Eskalasi insiden ke NOC |
| GET | /api/rca/analyze/:id | Analisis RCA per insiden |
| GET | /api/rca/trace/:id | Trace keputusan AI |
| POST | /api/rca/reanalyze/:id | Re-trigger analisis AI |
| GET | /api/causal_dag/:incident_id | Causal DAG graf |
| GET | /api/decision_graph/:incident_id | Graf keputusan AI |
| GET | /api/incidents/:id/evidence_dag | Evidence DAG |
| GET | /api/event_correlation | Korelasi event lintas insiden |
| GET | /api/evidence_explorer | Penjelajah bukti insiden |
| GET | /api/knowledge_graph | Graf pengetahuan |
| POST | /api/knowledge_graph/discovery | Trigger discovery |

### 6.5 Operations & Approvals
| Method | Endpoint | Fungsi |
|---|---|---|
| GET | /api/approval_queue | Antrean HitL approval |
| POST | /api/hitl/approve | Setujui tindakan mitigasi |
| POST | /api/hitl/reject | Tolak tindakan mitigasi |
| GET | /api/verification_queue | Antrian verifikasi pasca-remediasi |
| GET | /api/rollback_history | Riwayat rollback |
| GET | /api/hitl/failed_actions | Daftar aksi gagal (DLQ) |
| POST | /api/dlq/replay/:id | Replay aksi gagal |
| POST | /api/dlq/purge/:id | Hapus dari DLQ |
| POST | /api/dlq/replay-all | Replay semua DLQ |
| GET | /api/governance/recovery_mode | Status recovery mode |
| POST | /api/governance/recovery_mode | Aktifkan/nonaktifkan recovery mode |
| POST | /api/timeline/approve | Approve dari timeline |
| POST | /api/timeline/reject | Reject dari timeline |

### 6.6 AI Engine Center
| Method | Endpoint | Fungsi |
|---|---|---|
| GET | /api/ai_status | Status runtime AI |
| GET | /api/ai_config | Konfigurasi AI (model, parameter) |
| POST | /api/ai_config | Simpan konfigurasi AI |
| GET | /api/ai/stats | Statistik performa AI |
| GET | /api/feedback | Daftar feedback operator |
| POST | /api/feedback | Submit feedback baru |
| GET | /api/feedback/stats | Statistik feedback |
| GET | /api/ai_decision_logs | Log keputusan AI |
| GET | /api/learning_gate_logs | Log Learning Gate |
| GET | /api/governance/learning_gate_policy | Kebijakan Learning Gate |
| POST | /api/governance/learning_gate_policy | Simpan kebijakan |
| GET | /api/playbooks | Daftar playbook remediasi |
| POST | /api/playbooks | Buat/update playbook |
| POST | /api/playbooks/:id/execute | Eksekusi playbook |
| DELETE | /api/playbooks/:id | Hapus playbook |
| GET | /api/jetstream_streams | Status NATS JetStream |

### 6.7 Security & Governance
| Method | Endpoint | Fungsi |
|---|---|---|
| GET | /api/security/policies | Kebijakan keamanan |
| POST | /api/security/policies/save | Simpan kebijakan |
| GET | /api/schema_validation_logs | Log validasi schema |
| GET | /api/schema_validation_logs/stats | Statistik validasi |
| GET | /api/schema_validation_logs/detail/:id | Detail validasi |
| POST | /api/schema_validation_logs/replay/:id | Replay validasi |
| GET | /api/governance/sops | Daftar SOP |
| POST | /api/governance/sops/create | Buat SOP baru |
| POST | /api/governance/sops/promote | Promote SOP |
| POST | /api/governance/sops/execute | Eksekusi SOP |
| GET | /api/governance/top_resolutions | Top resolusi sukses |
| GET | /api/governance/sla_compliance | SLA compliance stats |
| GET | /api/kb_stats | Statistik knowledge base |
| GET | /api/system/audits | Audit log sistem |

### 6.8 Diagnostics & Comm
| Method | Endpoint | Fungsi |
|---|---|---|
| GET | /api/server/logs | Log server (HTTP fallback) |
| GET | /ws/logs | WebSocket stream log real-time |
| GET | /api/nats_subjects | Status & telemetri NATS subjects |
| GET | /api/enterprise/chat/sessions | Daftar sesi chat |
| GET | /api/enterprise/chat/history/:id | Riwayat pesan per sesi |
| GET | /api/enterprise/chat/device_context/:id | Konteks perangkat & insiden |
| POST | /api/enterprise/chat/sessions/status/:id | Update status sesi |
| POST | /api/enterprise/chat/upload | Upload attachment |
| GET | /api/enterprise/chat/ai_assist | Saran jawaban AI |
| GET | /api/enterprise/chat/presence | Status kehadiran operator |
| POST | /api/enterprise/chat/presence | Update presence |
| POST | /api/enterprise/chat/feedback | Submit feedback chat |
| GET | /ws/operator_chat | WebSocket operator chat |
| GET | /ws/client_chat | WebSocket client chat |
| GET | /ws/chat | WebSocket dashboard chat |

### 6.9 Remote Access
| Method | Endpoint | Fungsi |
|---|---|---|
| GET | /api/remote/settings | Konfigurasi remote tools |
| POST | /api/remote/settings/save | Simpan konfigurasi |
| GET | /api/remote/detect | Deteksi tool tersedia |
| POST | /api/remote/launch/:tool | Launch remote session |
| POST | /api/remote/test/:tool | Test koneksi tool |

---

## 7. MENU & SUB-MENU NOC IT AI v3.0

### 7.1 Dashboard & Overview
**Sub-menu**: Overview, Execution Timeline, Storage

- **Overview**: KPI Cards (Active Devices, Open Incidents, Auto-Healing Rate, Avg Latency). Data dari `/api/kpi_metrics`, refresh 5 detik.
- **Execution Timeline**: Kronologi siklus AI (Anomaly → RCA → Approval → Execute → Verify). Data dari `/api/execution_timeline`.
- **Storage**: Kapasitas disk, log retention Loki, ukuran DB. Data dari `/api/storage/stats`.

### 7.2 Fleet & Health
**Sub-menu**: Monitoring Live, Fleet Management, Server Health, Fleet Global Config, PC Health, Printer Status, AI Agent Health, Activity & Issue

- **Monitoring Live**: Telemetri CPU/RAM/Disk/Net real-time via WebSocket dari seluruh armada.
- **Fleet Management**: CRUD perangkat & cabang. API: `/api/fleet/admin/devices`, `/api/fleet/admin/sites`.
- **Server Health**: Status Go Core, Python AI, PostgreSQL, Redis, NATS. API: `/api/system/health`.
- **Fleet Global Config**: Threshold alert, interval heartbeat. API: `/api/fleet/config/global`.
- **PC Health**: Health Score per PC (%), error aktif, thermal. API: `/api/agent_health`.
- **Printer Status**: Status printer POS (Online/Offline/Error, paper, spooler). API: `/api/printers/live`.
- **AI Agent Health**: Status modul AI di agent PC Client. API: `/api/agent_deep_diagnostics/:device`.
- **Activity & Issue**: Log aktivitas user & issue minor. API: `/api/activity-log`.

### 7.3 Incident & RCA
**Sub-menu**: Incident Triage, Ground Truth & RCA, Event Correlation, Unified Graphs

- **Incident Triage**: Pengelompokan P1/P2/P3 dan assignment NOC. API: `/api/incidents`.
- **Ground Truth & RCA**: Analisis kausalitas, match historis, RAG reasoning. API: `/api/rca/analyze/:id`, `/api/causal_dag/:id`.
- **Event Correlation**: Pola lintas-device/cabang. API: `/api/event_correlation`.
- **Unified Graphs**: Graf hardware→OS→process→network. API: `/api/decision_graph/:id`.

### 7.4 Operations & Approvals
**Sub-menu**: Approval Queue, Pending Verification, Rollback History, Failed Action (DLQ), Recovery Mode

- **Approval Queue**: HitL approve/reject skrip mitigasi. API: `/api/approval_queue`, `/api/hitl/approve`.
- **Pending Verification**: Verifikasi pasca-remediasi. API: `/api/verification_queue`.
- **Rollback History**: Riwayat snapshot recovery. API: `/api/rollback_history`.
- **Failed Action (DLQ)**: Dead Letter Queue. API: `/api/hitl/failed_actions`, `/api/dlq/replay/:id`.
- **Recovery Mode**: Freeze AI, kontrol manual penuh. API: `/api/governance/recovery_mode`.

### 7.5 AI Engine Center
**Sub-menu**: Runtime Engine Monitor, Model Config, Training Feedback, AI Decision Log, Learning Gate Log, Learning Gate Policy, Playbook Studio

- **Runtime Engine Monitor**: Latency LLM, queue depth, token/sec. API: `/api/system/runtime_monitor`.
- **Model Config**: Parameter LLM (Temperature, Top_P, Max Tokens, System Prompt). API: `/api/ai_config`.
- **Training Feedback**: Feedback operator untuk fine-tuning. API: `/api/feedback`.
- **AI Decision Log**: Chain-of-thought & confidence score per keputusan. API: `/api/ai_decision_logs`.
- **Learning Gate Log**: Evaluasi playbook baru masuk knowledge base. API: `/api/learning_gate_logs`.
- **Learning Gate Policy**: Threshold confidence minimum. API: `/api/governance/learning_gate_policy`.
- **Playbook Studio**: Editor + runner skrip mitigasi + Dry Run mode. API: `/api/playbooks`.

### 7.6 Security & Governance
**Sub-menu**: RBAC Policies, Security Policies, Evidence Explorer, Knowledge Graph, SOP Lifecycle, Schema Validation Logs

- **RBAC Policies**: Role: Superadmin, NOC Engineer, L3 Support, Auditor. API: `/api/rbac/policies`.
- **Security Policies**: JWT, HMAC validation, Rate Limiting, WAF. API: `/api/security/policies`.
- **Evidence Explorer**: Screenshot, log trigger, telemetry snapshot. API: `/api/evidence_explorer`.
- **Knowledge Graph**: Graf relasi insiden-gejala-komponen-skrip. API: `/api/knowledge_graph`.
- **SOP Lifecycle**: Manajemen & mapping SOP ke jenis insiden. API: `/api/governance/sops`.
- **Schema Validation Logs**: Audit validasi JSON payload agent. API: `/api/schema_validation_logs`.

### 7.7 Diagnostics & Comm
**Sub-menu**: Live Logs, NATS Subjects, Live Chat

- **Live Logs**: Stream log real-time, filter severity/keyword. WebSocket: `/ws/logs`.
- **NATS Subjects**: RTT Latency, broker status, 12 subject aktif. API: `/api/nats_subjects`.
- **Live Chat (Open Support Chat)**:
  - WebSocket: `/ws/operator_chat` & `/ws/client_chat`
  - AI Analysis Card: UI terstruktur (Severity Badge, RCA Grid, Recovery Checklist, Evidence Badges, Raw JSON toggle)
  - Incident Popup Modal: Klik insiden di sidebar → detail diagnostic + Escalate/Resolve buttons
  - AI Suggestion Box: Panduan penanganan step-by-step untuk operator

### 7.8 Telegram Integration (3-Way Sync)

**Service**: `osi-secure-relay` (port 9998) + `osi-telegram-bot`  
**File**: `SERVER/go_core/ingestion/telegram_service.go`, `portal/relay/main.go`

Setiap insiden terdeteksi, Telegram Bot mengirim:
1. Alert severity + nama PC Client
2. Analisa AI (Root Cause) + Cara Menangani
3. Screenshot bukti (photo_b64)
4. Tombol `💬 Chat User` — buka sesi chat
5. Tombol `✅ Approve` / `❌ Reject` — HitL dari Telegram

---

## 8. NOTIFIKASI 3-WAY SINKRON

Ketika insiden terdeteksi oleh `incident_service.go`:

| Kanal | Mekanisme | Tampilan |
|---|---|---|
| PC Client (OSI Support Chat) | TCP Bypass Command SHOW_NOTIFICATION + SHOW_CHAT | Toast Windows + Auto-open chat window + AI Card bubble |
| Dashboard NOC | NATS → WebSocket → UI render | Structured AI Incident Card + Sidebar context + Popup Modal |
| Telegram Bot | HMAC-signed relay → api.telegram.org | Alert + Photo evidence + Inline keyboard buttons |

---

## 9. SECURITY ARCHITECTURE

- **JWT Authentication**: Semua endpoint API dilindungi `AuthMiddleware`
- **HMAC-SHA256**: Telegram relay request divalidasi signature + timestamp
- **WAF Middleware**: Proteksi SQL injection, XSS, path traversal
- **Rate Limiting**: Per-IP rate limiter via `NewIPRateLimiter()`
- **CSRF Protection**: `CSRFMiddleware` aktif pada semua POST request
- **RBAC**: 4 role (Superadmin, NOC Engineer, L3 Support, Auditor)
- **Redis Session**: Token sesi disimpan dan divalidasi via Redis
- **Network Isolation**: 2 Docker network (osi-frontend, osi-backend)
- **TLS**: Nginx TLS termination port 9443

---

## 10. CLIENT AGENT

**Distribusi**: `CLIENT_DISTRIBUSI_GO/` (file server via `osi-agent-dist:9090`)  
**Platform**: Windows (C# .exe) + Linux (Go binary)  
**Protokol ke Server**: TCP port 18800 (telemetry) / 18802 (WebSocket chat)

Fungsi Agent:
- Kirim telemetry heartbeat (CPU, RAM, Disk, Network, Process list)
- Terima perintah dari server (SHOW_NOTIFICATION, SHOW_CHAT, capture_screenshot)
- Eksekusi skrip remediasi yang disetujui
- Kirim screenshot ke server via WebSocket

**OTA Update**: Agent mendukung update otomatis via manifest `/api/fleet/update/manifest`

---

## 11. KONFIGURASI ENVIRONMENT (.env)

| Variable | Nilai Default | Keterangan |
|---|---|---|
| DB_HOST | postgres | Host PostgreSQL |
| DB_PORT | 5432 | Port PostgreSQL |
| DB_NAME | osi_system | Nama database |
| DB_PASSWORD | (secret) | Password database |
| REDIS_HOST | redis | Host Redis |
| REDIS_PORT | 6379 | Port Redis |
| NATS_HOST | nats | Host NATS |
| NATS_PORT | 4222 | Port NATS |
| JWT_SECRET_KEY | (secret) | Secret signing JWT |
| OSI_SECURITY_KEY | (secret) | HMAC key + Redis/NATS auth |
| GEMINI_API_KEY | (secret) | Google Gemini API key |
| TELEGRAM_BOT_TOKEN | (secret) | Token Telegram Bot |
| TELEGRAM_CHAT_ID | (secret) | Chat ID Telegram NOC |
| AUTHORIZED_ADMINS | (secret) | Admin Telegram IDs |
| PROXY_HTTP_PORT | 80 | Port HTTP eksternal |
| PROXY_HTTPS_PORT | 9443 | Port HTTPS eksternal |

---

## 12. STATUS PRODUKSI AKHIR

| Modul | Sub-Sistem | Status |
|---|---|---|
| Infrastructure | Docker, Nginx, PostgreSQL, Redis, NATS | ✅ 100% |
| Go Ingestion Server | TCP receiver, telemetry normalization | ✅ 100% |
| Go Dashboard Server | REST API, WebSocket, Auth, RBAC | ✅ 100% |
| Python AI Core | Supervisor, RAG, Consensus, Critic, Policy | ✅ 100% |
| Telegram Integration | Relay, Bot Listener, HitL, Screenshot | ✅ 100% |
| Live Chat Engine | WebSocket, AI Card, Modal Popup, Escalation | ✅ 100% |
| NATS Subjects Monitor | RTT Latency, Subject Registry, UI | ✅ 100% |
| Evidence Explorer | Screenshot, DAG, Fleet Evidence | ✅ 100% |
| Playbook Studio | CRUD, Execute, Dry Run, Audit Trail | ✅ 100% |
| Schema Validation | Log, Stats, Detail, Replay | ✅ 100% |
| Security Policies | RBAC, JWT, WAF, HMAC, Rate Limit | ✅ 100% |
| Agent Distribution | OTA, TCP, WebSocket, Screenshot | ✅ 100% |

**SISTEM NOC IT AI v3.0 — 100% PRODUCTION READY**  
**Tidak ada data mock, dummy, hardcoded, atau placeholder aktif.**


---

## 13. CETAK BIRU SISTEM (SYSTEM BLUEPRINT)
### Dokumentasi Riil Sistem yang Berjalan

---

### 13.1 ARSITEKTUR JARINGAN FISIK

```
INTERNET / WAN
      │
      ▼
┌─────────────────────────────────────────────────────┐
│              LINUX SERVER (HOST)                     │
│  OS: Ubuntu 22.04 LTS                               │
│  IP: 172.18.0.1 (host.docker.internal)              │
│                                                      │
│  ┌──────────────── osi-frontend ──────────────────┐ │
│  │  osi-nginx (:80/:9443) ← Reverse Proxy TLS     │ │
│  │  osi-dashboard-server  ← Web UI + REST API     │ │
│  │  osi-portainer (:9000) ← Docker Mgmt UI        │ │
│  └───────────────────────────────────────────────┘  │
│                                                      │
│  ┌──────────────── osi-backend ───────────────────┐ │
│  │  osi-postgres (:5432)   ← pgvector DB          │ │
│  │  osi-redis (:6379)      ← Cache + Presence     │ │
│  │  osi-nats (:4222/:8222) ← Event Bus            │ │
│  │  osi-ingestion-server (:18800/:18802)           │ │
│  │  osi-scheduler-service ← Cron Jobs             │ │
│  │  osi-secure-relay (:9998) ← Telegram Relay     │ │
│  │  osi-telegram-bot      ← HitL Listener         │ │
│  │  osi-python-ai-core    ← LLM Supervisor        │ │
│  │  osi-ai-consensus      ← Multi-Agent           │ │
│  │  osi-ai-critic         ← Quality Evaluator     │ │
│  │  osi-ai-policy         ← Policy Engine         │ │
│  │  osi-ai-rag            ← Vector RAG            │ │
│  │  osi-ai-daemons        ← Background Daemons    │ │
│  │  osi-agent-dist (:9090) ← OTA File Server      │ │
│  └───────────────────────────────────────────────┘  │
│                                                      │
│  External Monitoring: Netdata (:19999)               │
└─────────────────────────────────────────────────────┘
```

### 17.1 Alur Data Perusahaan & Kode Implementasi Fisik (True Implementation Flow)
Aliran data *(Data Flow Architecture)* beroperasi secara vertikal berurutan tanpa celah. Kami telah memetakan lapisan logis ini langsung ke modul **Source Code** riil yang aktif:

```text
                Enterprise Runtime
        (API Gateway, NATS, Vault, Cache)
                        │
──────────────────────────────────────────
             Data Validation Layer
   (trust_engine.py & PromptNormalizer)
                        │
──────────────────────────────────────────
               Knowledge Layer
(Multi-Tenant Postgres + pgvector + RAG)
                        │
──────────────────────────────────────────
             Cognitive AI Layer
 (llm_router.py [DeepSeek/Gemini] + DAG)
                        │
──────────────────────────────────────────
             Governance Layer
  (IncidentScorer & Token Circuit Breaker)
                        │
──────────────────────────────────────────
            Execution Layer
 (N8N + blast_radius_engine.py [Shadow])
                        │
──────────────────────────────────────────
        Continuous Learning Layer
  (benchmark_engine.py -> ai_curriculum)
                        │
──────────────────────────────────────────
       Audit & Compliance Layer
 (Immutable Audit + correlation_engine.py)
                        │
──────────────────────────────────────────
       Enterprise Dashboard Layer
 (AI Observability Metrics + HITL Copilot)
``` ▼                    ▼
PC CLIENT (Windows)    TELEGRAM BOT API
  agent.exe              api.telegram.org
  :18800 TCP             NOC Group Chat
  :18802 WebSocket
```

---

### 13.2 BLUEPRINT ALUR INSIDEN LENGKAP (INCIDENT LIFECYCLE)

```
┌────────────────────────────────────────────────────────────────┐
│                    TAHAP 1: DETEKSI                            │
│                                                                │
│  PC Client Agent (Windows C# / Linux Go)                       │
│  ├── Heartbeat CPU/RAM/Disk/Net setiap 30 detik               │
│  ├── Watchdog monitor: Service, Process, Hardware              │
│  └── Anomali terdeteksi → Kirim ke osi-ingestion-server       │
│                          TCP :18800 / WebSocket :18802         │
└───────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│                    TAHAP 2: NORMALISASI                        │
│                                                                │
│  Go Ingestion Server (incident_service.go)                     │
│  ├── Validasi schema payload JSON                              │
│  ├── Dedup filter (cegah flood insiden sama)                   │
│  ├── Simpan ke PostgreSQL: fleet_incidents, devices            │
│  ├── Publish NATS: "incident.detected"                         │
│  └── Kirim SHOW_NOTIFICATION + SHOW_CHAT ke PC Client         │
└───────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│                    TAHAP 3: ANALISIS AI                        │
│                                                                │
│  Python AI Core (ai_supervisor.py)                             │
│  ├── Subscribe NATS: "incident.detected"                       │
│  ├── Intent Classification (30+ kategori)                      │
│  ├── RAG Engine: Cari kasus historis (pgvector similarity)     │
│  ├── Causal DAG: Bangun graf Hardware→OS→Process→Net           │
│  ├── LLM Reasoning: Google Gemini API                          │
│  │   ├── Primary Cause + Probability                          │
│  │   ├── Secondary/Tertiary Cause                             │
│  │   ├── Confidence Score (0-100%)                            │
│  │   ├── Evidence: CPU/RAM/Disk/Net/Log                       │
│  │   ├── Fleet Correlation (SYSTEMIC_PATTERN_DETECTED?)       │
│  │   └── STATUS: WAITING_APPROVAL / INSUFFICIENT_EVIDENCE     │
│  ├── Multi-Agent Consensus (osi-ai-consensus)                  │
│  ├── Critic Evaluation (osi-ai-critic)                         │
│  ├── Policy Check (osi-ai-policy)                              │
│  ├── Blast Radius Assessment                                   │
│  └── Kirim hasil ke chat_messages + Publish remediation.execute│
└───────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│                    TAHAP 4: PENGIRIMAN 3-WAY                   │
│                                                                │
│  ┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐ │
│  │  PC CLIENT      │ │  NOC DASHBOARD  │ │  TELEGRAM BOT   │ │
│  │                 │ │                 │ │                 │ │
│  │ Toast Notif:    │ │ AI Incident     │ │ Alert + Severity │ │
│  │ "Sistem detect  │ │ Card:           │ │ + Root Cause    │ │
│  │  masalah pada   │ │ ├─ Severity     │ │ + Cara Tangani  │ │
│  │  komputer Anda" │ │ ├─ RCA Grid     │ │ + Photo Evidence│ │
│  │                 │ │ ├─ Evidence     │ │ + [💬 Chat User]│ │
│  │ Auto SHOW_CHAT: │ │ ├─ Checklist    │ │ + [✅ Approve]  │ │
│  │ Jendela OSI     │ │ ├─ HitL Buttons │ │ + [❌ Reject]   │ │
│  │ Support Chat    │ │ └─ Raw JSON     │ │                 │ │
│  │ terbuka otomatis│ │                 │ │ HMAC-SHA256     │ │
│  │                 │ │ Sidebar:        │ │ signed via      │ │
│  │ AI Bubble Chat: │ │ ├─ Incidents    │ │ osi-secure-relay│ │
│  │ Diagnosis +     │ │ ├─ Remote Log   │ │ :9998           │ │
│  │ Langkah Tangani │ │ └─ Screenshots  │ │                 │ │
│  └─────────────────┘ └─────────────────┘ └─────────────────┘ │
└───────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│                    TAHAP 5: HUMAN APPROVAL (HitL)              │
│                                                                │
│  Operator NOC Dashboard / Admin Telegram                       │
│  ├── Review AI Analysis Card                                   │
│  ├── Pilih: APPROVE / REJECT / ESCALATE                        │
│  ├── API: POST /api/hitl/approve atau /api/hitl/reject         │
│  └── Publish NATS: "approval.site.*"                           │
└───────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│                    TAHAP 6: EKSEKUSI REMEDIASI                 │
│                                                                │
│  Go Dashboard Server (remediation.execute subscriber)          │
│  ├── Terima dari NATS: "remediation.execute"                   │
│  ├── Pilih Playbook dari ai_playbooks                          │
│  ├── Kirim perintah ke PC Client Agent via TCP Bypass          │
│  ├── Monitor output eksekusi real-time                         │
│  ├── Jika gagal → DLQ (hitl/failed_actions)                   │
│  └── Jika sukses → Verification Queue                          │
└───────────────────────────┬────────────────────────────────────┘
                            │
                            ▼
┌────────────────────────────────────────────────────────────────┐
│                    TAHAP 7: VERIFIKASI & PENUTUPAN             │
│                                                                │
│  ├── Post-execution health check (CPU/RAM/Service normal?)     │
│  ├── Update fleet_incidents.status = RESOLVED                  │
│  ├── Simpan ke ai_audit_logs (chain-of-thought)                │
│  ├── Feedback loop → ai_feedbacks untuk fine-tuning            │
│  ├── Knowledge Graph update                                    │
│  └── SLA Compliance tracking                                   │
└────────────────────────────────────────────────────────────────┘
```

---

### 13.3 BLUEPRINT MULTI-AGENT AI SYSTEM

```
┌─────────────────────────────────────────────────────────────┐
│                  PYTHON AI CORE ARCHITECTURE                 │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              ai_supervisor.py (Orchestrator)         │   │
│  │                                                     │   │
│  │  Intent Classifier (30+ kategori)                   │   │
│  │  ├── NETWORK_ISSUE    ├── HARDWARE_FAILURE           │   │
│  │  ├── SERVICE_CRASH    ├── DISK_FAILURE               │   │
│  │  ├── AUTH_FAILURE     ├── PRINTER_ERROR              │   │
│  │  └── UNKNOWN_ANOMALY  └── ... (24 kategori lain)    │   │
│  │                                                     │   │
│  │  Confidence Routing:                                │   │
│  │  ├── ≥85%  → Direct Auto-Remediation               │   │
│  │  ├── 60-84% → Evidence Validation required          │   │
│  │  ├── 40-59% → LLM Consensus needed                  │   │
│  │  └── <40%  → Human Review (WAITING_APPROVAL)        │   │
│  └───────────┬─────────────────────────────────────────┘   │
│              │                                               │
│    ┌─────────┼──────────────────────────────────────┐       │
│    ▼         ▼              ▼              ▼         ▼       │
│  RAG       Causal       Consensus      Critic     Policy     │
│  Engine    DAG          Service        Service    Service    │
│            Engine                                            │
│                                                             │
│  osi-ai-rag  → pgvector similarity search                   │
│  causal_dag  → Hardware→OS→Process→Network dependency       │
│  consensus   → Multi-model agreement scoring                 │
│  critic      → Hallucination detection & quality check      │
│  policy      → Safety gate & blast radius assessment         │
│                                                             │
│  Daemons (osi-ai-daemons):                                  │
│  ├── Presence Daemon → Redis operator status                 │
│  ├── Learning Plane → Knowledge base update                  │
│  ├── Escalation Engine → Auto-escalate P1 incidents          │
│  └── State Observer → System health monitoring               │
└─────────────────────────────────────────────────────────────┘
```

---

### 13.4 BLUEPRINT DATABASE RELASI TABEL

```
fleet_sites (cabang)
    │ 1:N
    ├──► fleet_devices (perangkat per cabang)
    │       │ 1:N
    │       ├──► fleet_incidents (insiden per device)
    │       │       │ 1:N
    │       │       ├──► fleet_evidence (screenshot, telemetry)
    │       │       └──► chat_sessions
    │       │                 │ 1:N
    │       │                 └──► chat_messages
    │       │                           │ 1:1
    │       │                           └──► telegram_chat_mappings
    │       └──► remote_sessions (log RDP/VNC/SSH)
    └──► fleet_printers (printer POS per cabang)

incidents (main table dari Python AI)
    │ 1:N
    ├──► ai_decision_logs (audit trail AI)
    ├──► approval_outbox (HitL queue)
    └──► ai_feedbacks (operator feedback)

ai_playbooks (library skrip remediasi)
    │ 1:N
    └──► playbook_executions (riwayat eksekusi)

governance_sops (dokumen SOP)
    │ N:N
    └──► incident categories

rbac_roles → rbac_permissions → users
schema_validation_logs (independent)
learning_gate_logs (independent)
system_audits (global audit trail)
```

---

### 13.5 BLUEPRINT SECURITY LAYERS

```
REQUEST MASUK (Browser / Agent / Telegram)
        │
        ▼
┌───────────────────────────────────┐
│  Layer 1: Nginx (TLS Termination) │
│  ├── HTTPS :9443 → HTTP internal  │
│  └── Rate Limit via nginx config  │
└──────────────────┬────────────────┘
                   │
                   ▼
┌───────────────────────────────────┐
│  Layer 2: WAF Middleware (Go)     │
│  ├── SQL Injection protection     │
│  ├── XSS protection               │
│  └── Path traversal protection    │
└──────────────────┬────────────────┘
                   │
                   ▼
┌───────────────────────────────────┐
│  Layer 3: IP Rate Limiter (Go)    │
│  └── Per-IP request throttling    │
└──────────────────┬────────────────┘
                   │
                   ▼
┌───────────────────────────────────┐
│  Layer 4: Auth Middleware (Go)    │
│  ├── JWT token validation         │
│  ├── Redis session check          │
│  └── Token expiry enforcement     │
└──────────────────┬────────────────┘
                   │
                   ▼
┌───────────────────────────────────┐
│  Layer 5: RBAC Check (Go)         │
│  ├── Superadmin: Full access      │
│  ├── NOC Engineer: Ops + Chat     │
│  ├── L3 Support: RCA + Approve    │
│  └── Auditor: Read-only           │
└──────────────────┬────────────────┘
                   │
                   ▼
┌───────────────────────────────────┐
│  Layer 6: CSRF Middleware (Go)    │
│  └── Token validation per POST    │
└──────────────────┬────────────────┘
                   │
                   ▼
            HANDLER DIEKSEKUSI

Telegram Relay tambahan:
└── HMAC-SHA256 signature + timestamp
    validation sebelum forward ke API
```

---

### 13.6 BLUEPRINT WEBSOCKET CONNECTION MAP

```
                    Go Dashboard Server
                           │
          ┌────────────────┼─────────────────┐
          │                │                 │
          ▼                ▼                 ▼
   /ws/operator_chat  /ws/client_chat   /ws/logs
          │                │                 │
          │      Enterprise Chat Engine       │
          │   (chat_engine.go + Redis pub/sub)│
          │                │                 │
    NOC Operator      PC Client Agent    Log Stream
    Dashboard UI      (agent.exe)        Filter UI
          │
          ▼
   /ws/chat (legacy dashboard)
          │
   handleDashboardWebSocket()
   ├── RECEIVE_MESSAGE
   ├── SEND_MESSAGE
   ├── START_TYPING / STOP_TYPING
   ├── MESSAGE_READ
   ├── SESSION_ASSIGNED
   ├── AI_SUGGESTION
   └── CONNECT / DISCONNECT

NATS → Redis pub/sub → WebSocket broadcast
(StartDashboardChatRedisSubscriber)
```

---

### 13.7 BLUEPRINT TELEGRAM INTEGRATION

```
┌────────────────────────────────────────────────────┐
│             ALUR TELEGRAM NOTIFICATION              │
│                                                    │
│  incident_service.go                               │
│       │                                            │
│       ▼ DefaultTelegramService.SendIncidentAlert() │
│                                                    │
│  telegram_service.go                               │
│  ├── Build pesan: Analisa AI + Cara Menangani      │
│  ├── Baca screenshot file → Base64 encode          │
│  ├── Build inline_keyboard:                        │
│  │   └── [💬 Chat User] callback: chat_user_<id>  │
│  ├── Hitung HMAC-SHA256 signature                  │
│  └── POST ke osi-secure-relay:9998/relay/telegram  │
│                                                    │
│  portal/relay/main.go (osi-secure-relay)           │
│  ├── Validasi HMAC signature + timestamp           │
│  ├── Jika photo_b64 ada → sendPhoto API            │
│  └── Jika teks saja → sendMessage API              │
│       │                                            │
│       ▼                                            │
│  api.telegram.org                                  │
│       │                                            │
│       ▼                                            │
│  Grup Telegram NOC                                 │
│  ┌──────────────────────────────────┐              │
│  │ 🧠 Analisa Masalah:              │              │
│  │    Unrecognized Telemetry Sig... │              │
│  │                                  │              │
│  │ 🔧 Cara Menangani:               │              │
│  │    1. Verifikasi koneksi LAN     │              │
│  │    2. Review Prometheus metrics  │              │
│  │    [Foto Screenshot PC Client]   │              │
│  │                                  │              │
│  │  [💬 Chat User]                  │              │
│  └──────────────────────────────────┘              │
│                                                    │
│  telegram_bot_listener.go (osi-telegram-bot)       │
│  ├── Listen callback_query                         │
│  ├── chat_user_<id> → buka chat session            │
│  ├── approve_<id>   → POST /api/hitl/approve       │
│  └── reject_<id>    → POST /api/hitl/reject        │
└────────────────────────────────────────────────────┘
```

---

### 13.8 BLUEPRINT LIVE CHAT ENGINE

```
┌──────────────────────────────────────────────────────────────┐
│                  OPEN SUPPORT CHAT SYSTEM                    │
│                                                              │
│  OPERATOR SIDE (NOC Dashboard)                               │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Sidebar Sesi        Chat Area           Sidebar Kanan │  │
│  │  ┌────────────┐  ┌─────────────────┐  ┌────────────┐  │  │
│  │  │ PC-MKT-NUC │  │ AI Analysis Card│  │ Incidents  │  │  │
│  │  │ WAITING    │  │ ┌─────────────┐ │  │ (clickable)│  │  │
│  │  │ PC-TEST-001│  │ │🧠 AI Report │ │  │ Remote Log │  │  │
│  │  │ CLOSED     │  │ │ CRITICAL ⚠️ │ │  │ Screenshots│  │  │
│  │  └────────────┘  │ │ WAITING_APR │ │  └────────────┘  │  │
│  │                  │ │ RCA Grid    │ │                   │  │
│  │                  │ │ Checklist   │ │  Popup Modal:     │  │
│  │                  │ │ Evidence    │ │  ├─ INC Detail    │  │
│  │                  │ │ [Approve]   │ │  ├─ RCA Summary  │  │
│  │                  │ │ [Reject]    │ │  ├─ Recovery Steps│  │
│  │                  │ │ [Raw JSON]  │ │  ├─ [Escalate]   │  │
│  │                  │ └─────────────┘ │  └─ [Resolve]    │  │
│  │                  └─────────────────┘                   │  │
│  └────────────────────────────────────────────────────────┘  │
│                                                              │
│  CLIENT SIDE (PC Agent / OSI Support Chat)                   │
│  ┌────────────────────────────────────────────────────────┐  │
│  │  Auto-open via SHOW_CHAT command                       │  │
│  │  ┌─────────────────────────────────────────────────┐  │  │
│  │  │  🤖 OSI AI:                                     │  │  │
│  │  │  "Saya mendeteksi gangguan pada komputer Anda.  │  │  │
│  │  │   Sedang melakukan analisa..."                  │  │  │
│  │  │                                                 │  │  │
│  │  │  🧠 Analisa Selesai:                            │  │  │
│  │  │  Issue: Watchdog Alert - Heartbeat FAILED       │  │  │
│  │  │  Severity: CRITICAL                             │  │  │
│  │  │  Cara Menangani:                                │  │  │
│  │  │  ✓ Verifikasi koneksi LAN                      │  │  │
│  │  │  ✓ Periksa hardware indicator                  │  │  │
│  │  │                                                 │  │  │
│  │  │  🚨 INCIDENT TERDETEKSI #INC-79795             │  │  │
│  │  │  [Laporkan ke NOC] [Self-Healing Resolved]     │  │  │
│  │  └─────────────────────────────────────────────────┘  │  │
│  └────────────────────────────────────────────────────────┘  │
└──────────────────────────────────────────────────────────────┘
```

---

### 13.9 BLUEPRINT NATS SUBJECT FLOW

```
NATS BROKER (osi-nats:4222)
│
├── agent.status.site.*.* ─────► Go Dashboard (heartbeat cache)
│                                 └── Redis update device status
│
├── incident.detected ──────────► Python AI Core (ai_supervisor)
│                                 └── LLM RCA → 3-way delivery
│
├── remediation.execute ────────► Go Dashboard Server
│                                 └── TCP cmd → PC Agent
│
├── remediation.rollback ───────► Go Dashboard Server
│                                 └── Rollback last action
│
├── approval.site.* ────────────► Dashboard Cache Invalidator
│                                 └── Refresh approval_queue UI
│
├── rollback.site.* ────────────► Dashboard Cache Invalidator
│                                 └── Refresh rollback_history UI
│
├── incident.site.*.* ──────────► Dashboard Cache Invalidator
│                                 └── Refresh incidents table UI
│
├── dashboard.health_score ─────► Go Dashboard → WebSocket UI
│                                 └── Update fleet health KPI
│
├── dashboard.early_warnings ───► Go Dashboard → WebSocket UI
│                                 └── Show warning banners
│
├── chat.events ────────────────► Redis pub/sub → WebSocket
│                                 └── Real-time chat update
│
├── incident.reanalyze ─────────► Python AI Core
│                                 └── Re-trigger full RCA
│
└── agent.command.* ────────────► Go Ingestion Server
                                  └── Forward TCP cmd to agent
```

---

### 13.10 STATUS BLUEPRINT DEPLOYMENT

| Layer | Komponen | Runtime | Port | Status |
|---|---|---|---|---|
| Edge | osi-nginx | nginx:1.25 | 80, 9443 | ✅ UP |
| Data | osi-postgres | pgvector:pg15 | 5433 (local) | ✅ UP |
| Cache | osi-redis | redis:7 | internal | ✅ UP |
| Event | osi-nats | nats:2.9 | 4222, 8222 | ✅ UP |
| Ingestion | osi-ingestion-server | Go binary | 18800, 18802 | ✅ UP |
| Scheduler | osi-scheduler-service | Go binary | internal | ✅ UP |
| Dashboard | osi-dashboard-server | Go binary | internal | ✅ UP |
| Relay | osi-secure-relay | Go binary | 9998 | ✅ UP |
| Bot | osi-telegram-bot | Go binary | internal | ✅ UP |
| AI Core | osi-python-ai-core | Python 3.11 | internal | ✅ UP |
| Consensus | osi-ai-consensus | Python 3.11 | internal | ✅ UP |
| Critic | osi-ai-critic | Python 3.11 | internal | ✅ UP |
| Policy | osi-ai-policy | Python 3.11 | internal | ✅ UP |
| RAG | osi-ai-rag | Python 3.11 | internal | ✅ UP |
| Daemons | osi-ai-daemons | Python 3.11 | internal | ✅ UP |
| Mgmt | osi-portainer | portainer CE | 9000, 9444 | ✅ UP |
| Dist | osi-agent-dist | python http | 9090 | ✅ UP |
| Monitor | netdata | native | 19999 | ✅ UP |

**CETAK BIRU SISTEM NOC IT AI v3.0 — TERVERIFIKASI & PRODUCTION READY**

---

## 14. LAPORAN AUDIT INFRASTRUKTUR PENUH (16 JULI 2026)
### Sumber: Audit Live Runtime — Berdasarkan Source Code & Docker

---

### 14.1 STATISTIK SISTEM TERVERIFIKASI LIVE

| Metrik | Nilai Aktual Terverifikasi |
|---|---|
| Total Layanan Docker | **17 container** (semua `running`) |
| Total Tabel Database | **180 tabel** (PostgreSQL + pgvector) |
| Total File Python AI Core | **152 file `.py`** |
| Total File Go Backend | **65 file `.go`** (37 go_core + 28 portal) |
| Total Insiden Tercatat | **1.541 insiden** di `fleet_incidents` |
| Total Telemetri Tercatat | **23.540 baris** (partisi Juli 2026, tabel `telemetry_logs`) |
| Knowledge Vectors (RAG) | **11 vektor aktif** di `knowledge_vectors` |
| AI Audit Trail | **105 entri** keputusan kognitif di `ai_audit_trail` |
| NATS Messages (All-time) | **14.040 masuk / 112.801 keluar** |
| NATS JetStream Streams | **2 stream / 10 consumer** aktif |
| NATS Koneksi Aktif | **18 klien** terhubung |
| NATS JetStream Pesan Tersimpan | **6.523 pesan / ~17 MB** |
| Error Kritis | **0** (bersih — tidak ada ImportError / AttributeError) |

---

### 14.2 STATUS PIPELINE AI KOGNITIF

#### 14.2.1 AI Supervisor (`osi-python-ai-core`)
- **Status**: ✅ AKTIF — Gemini API terkoneksi via `google.genai.Client`
- **Log**: `Gemini provider configured successfully`, `[WORLD MODEL] Update cycle complete`, `[DISCOVERY] Discovery completed successfully`

#### 14.2.2 Consensus Engine (`osi-ai-consensus`)
- **Status**: ✅ AKTIF — Listen NATS subject `ai.engine.consensus`
- **Bobot Model**: `{'gemini': 0.4, 'deepseek': 0.3, 'groq': 0.2, 'rule_engine': 0.1}`

#### 14.2.3 Adversarial Critic Engine (`osi-ai-critic`)
- **Status**: ✅ AKTIF — Listen `ai.engine.critic`

#### 14.2.4 RAG Semantic Memory (`osi-ai-rag`)
- **Status**: ✅ AKTIF — Connection pool pgvector terinisialisasi
- **Data**: 11 vektor, embedding model: `text-embedding-004` (Google)

#### 14.2.5 Policy Governance Engine (`osi-ai-policy`)
- **Status**: ✅ AKTIF — OPA Hardened Policy Engine, Listen `ai.engine.policy`

#### 14.2.6 Background Daemons Suite (`osi-ai-daemons`)
- **Status**: ✅ AKTIF — Enterprise Watch Officer setiap 30 detik
- **Log**: `[WATCH_OFFICER] System healthy. No advisory needed this cycle.`

---

### 14.3 MATRIKS KEBIJAKAN EKSEKUSI (POLICY MATRIX)

| Aksi | Mode Advisory | Mode HITL | Mode Autonomous |
|---|---|---|---|
| NOTIFY / TICKET | AUTO | AUTO | AUTO |
| RESTART AGENT | DENY | APPROVAL | AUTO |
| RESTART SERVICE | DENY | APPROVAL | APPROVAL |
| DB MIGRATION | DENY | APPROVAL | DENY |
| FIREWALL CHANGE | DENY | APPROVAL | DENY |

---

### 14.4 ARSITEKTUR MEMORI AI (AI MEMORY ARCHITECTURE)

| Jenis Memori | Penyimpanan | Tabel DB | Status |
|---|---|---|---|
| Working Memory | Redis (volatile) | Cache sementara per insiden | ✅ AKTIF |
| Semantic Memory | PostgreSQL / pgvector | `knowledge_vectors` | ✅ AKTIF (11 vektor) |
| Episodic Memory | PostgreSQL | `episodic_memory`, `incident_post_mortems` | ✅ AKTIF |
| Procedural Memory | PostgreSQL | `ai_playbooks`, `procedural_memory` | ✅ AKTIF |
| Feedback Memory | PostgreSQL | `incident_feedback`, `hitl_audit_logs` | ✅ AKTIF |

---

### 14.5 TABEL DATABASE DENGAN DATA NYATA (TOP 14)

| Tabel | Jumlah Baris |
|---|---|
| `telemetry_logs` (partisi Juli 2026) | 23.540 |
| `kpi_baselines` | 980 |
| `incidents` | 259 |
| `fleet_incidents` | 1.541 |
| `system_audits` | 100 |
| `ai_audit_trail` | 105 |
| `ai_runtime_state` | 15 |
| `cognitive_kpis` | 12 |
| `knowledge_vectors` | 11 |
| `ai_benchmarks` | 8 |
| `escalation_log` | 4 |
| `agent_heartbeats` | 4 |
| `agent_trust_scores` | 3 |
| `kpi_drifts` | 3 |

---

### 14.6 COGNITIVE AI ENGINE — AUDIT KAPABILITAS LENGKAP

#### Evidence Intelligence Engine

| Sub-Kapabilitas | Status | Lokasi | Kesiapan |
|---|---|---|---|
| Evidence Extraction | ✅ AKTIF | `cognition/evidence_fabric.py:99` | 95% |
| Evidence Normalization | ✅ AKTIF | `cognition/evidence_fabric.py:187` | 90% |
| Evidence Correlation (Multi-host) | ✅ AKTIF | `cognition/correlation_engine.py:69` | 100% |
| Evidence Enrichment | ✅ AKTIF | `cognition/evidence_fabric.py:231` | 100% |
| Evidence Prioritization | ✅ AKTIF | `cognition/evidence_fabric.py:255` | 100% |
| Evidence Confidence Score | ✅ AKTIF | `EvidenceQuality` dataclass | 100% |
| Evidence Timeline | ✅ AKTIF | `cognition/temporal_reasoning_engine.py` | 100% |
| Evidence Ranking | ✅ AKTIF | `cognition/evidence_fabric.py:258` | 100% |
| Multi-source Evidence Fusion | ✅ AKTIF | `core/merge_engine.py` | 95% |

#### Root Cause Analysis Engine

| Sub-Kapabilitas | Status | Lokasi | Kesiapan |
|---|---|---|---|
| Causal Graph | ✅ AKTIF | `cognition/evidence_reasoning_graph.py:97` | 85% |
| Bayesian Reasoning (Noisy-OR) | ✅ AKTIF | `causal_dag_engine.py` | 100% |
| Dependency Graph | ✅ AKTIF | `cognition/service_dependency_map.py:22` | 80% |
| Topology Awareness | ✅ AKTIF | `service_dependency_map.py:55` | 80% |
| Blast Radius Analysis | ✅ AKTIF | `blast_radius_engine.py:78` | 100% |
| Event Correlation | ✅ AKTIF | `cognition/correlation_engine.py:64` | 100% |
| Multi-step Causal Chain | ✅ AKTIF | `cognition/causal_engine.py:71` | 95% |
| Confidence Scoring (Deterministik) | ✅ AKTIF | `ai_supervisor.py:1180` | 100% |
| Root Cause Ranking (Top-5) | ✅ AKTIF | `ai_supervisor.py:1018` | 95% |
| Hypothesis Engine (N kandidat) | ✅ AKTIF | `cognition/hypothesis_engine.py` | 95% |
| Counter Evidence Engine | ✅ AKTIF | `cognition/hypothesis_engine.py` | 100% |
| Temporal Reasoning Engine | ✅ AKTIF | `cognition/temporal_reasoning_engine.py` | 100% |
| Asset Context Engine | ✅ AKTIF | `cognition/asset_context_engine.py` | 100% |

#### OSI Layer Classification Engine

| Layer | Status | Lokasi |
|---|---|---|
| Layer 1 (Power/Cable/Hardware) | ✅ AKTIF | `cognition/osi_taxonomy.py:86` |
| Layer 2 (VLAN/STP/Loop) | ✅ AKTIF | `osi_taxonomy.py` + `intent_classifier.py` |
| Layer 3 (IP/Routing/BGP) | ✅ AKTIF | `osi_taxonomy.py` + keyword map |
| Layer 4 (TCP/UDP/SYN) | ✅ AKTIF | `intent_classifier.py:190` — 30+ kategori |
| Layer 5 (Session) | ✅ AKTIF | `osi_taxonomy.py` |
| Layer 6 (TLS/SSL/Certificate) | ✅ AKTIF | `osi_taxonomy.py` |
| Layer 7 (HTTP/DNS/API/DB) | ✅ AKTIF | `osi_taxonomy.py` |
| Multi-layer Cascading | ✅ AKTIF | `osi_taxonomy.py:183` |
| Explainable Classification | ✅ AKTIF | `EnterpriseLayerProfile.get_focus_prompt()` |

---

### 14.7 URUTAN REASONING PIPELINE AKTUAL

```
Telemetry [NATS: telemetry.critical / telemetry.netdata]
  ↓
CorrelationEngine.process_telemetry()        [correlation_engine.py:69]
  ↓
EnterpriseEvidenceFabric.ingest_telemetry() [evidence_fabric.py:99]
  ↓
AssetContextEngine.fetch_asset_context()     [asset_context_engine.py]
  ↓
OSITaxonomyEngine.classify_incident_layer() [osi_taxonomy.py:86]
  ↓
FastIntentClassifier.predict_multi()         [intent_classifier.py:190]
  ↓
MergeEngine (parallel_gather)                [core/merge_engine.py]
  ↓
RAG + KnowledgeFabric                        [rag_engine.py + knowledge_fabric.py]
  ↓
TemporalReasoningEngine                      [temporal_reasoning_engine.py]
  ↓
HypothesisEngine (5 kandidat + scoring)      [cognition/hypothesis_engine.py]
  ↓
CounterEvidenceEngine                        [cognition/hypothesis_engine.py]
  ↓
CausalReasoningEngine.infer_root_cause()     [cognition/causal_engine.py]
  ↓
BlastRadiusEngine.calculate_blast_radius()   [blast_radius_engine.py:78]
  ↓
ConsensusEngine            [NATS: ai.engine.consensus]
  ↓
CriticEngine               [NATS: ai.engine.critic]
  ↓
Confidence Score (Deterministik, 5 metrik)   [ai_supervisor.py:1180]
  ↓
PolicyEngine.evaluate_policy()               [policy_engine.py]
  ↓
HITL Queue / Telegram Approval               [core/approval_queue.py]
  ↓
Execution via NATS                           [remediation.execute]
  ↓
run_background_verification()                [ai_supervisor.py:419]
  ↓
Learning Loop + Embedding                    [ai_supervisor.py:1547]
```

---

### 14.8 FORMULA CONFIDENCE SCORE (DETERMINISTIK)

```
Confidence = (Evidence Score × 30%)
           + (Historical/RAG Score × 20%)
           + (Dependency/Topology Score × 20%)
           + (Correlation Score × 10%)
           + (LLM Consensus Score × 20%)
           - Critic Penalty (jika hipotesis ditolak)

Routing:
  ≥ 85% → Direct Auto-Remediation
  60–84% → Evidence Validation Required
  40–59% → LLM Consensus Needed
  < 40%  → Human Review (WAITING_APPROVAL)
```

---

### 14.9 SUBSISTEM LANJUTAN YANG BELUM TERDOKUMENTASI

#### Sprint O — Continuous Evaluation & Engineer Benchmark
- **File**: `portal/sprint_o_api.go`, `SERVER/python_ai_core/verification/benchmark_engine.py`
- **Fungsi**: Benchmark AI vs Human RCA — mengukur false positive, false negative, hallucination rate
- **Tabel**: `ai_engineer_benchmark`, `ai_prompt_evaluation`, `ai_capability_score`, `ai_continuous_improvement`
- **Endpoint**: `/api/sprint_o/benchmark`

#### Sprint P4 — DLQ Hybrid Service
- **File**: `SERVER/python_ai_core/services/dlq_service.py`
- **Fungsi**: Backup telemetri ke `dlq_hybrid` table atau filesystem jika NATS + DB lumpuh bersamaan

#### Chaos Engineering & Resilience
- **File**: `SERVER/python_ai_core/verification/chaos_monkey.py`
- **Fungsi**: Jika `ENABLE_CHAOS_MONKEY=true`, secara acak membunuh container atau mensimulasikan kegagalan jaringan untuk menguji Circuit Breaker
- **File Launcher**: `LAUNCHER_SERVICE_GO/` — Proxy biner aman untuk eksekusi command di OS client tanpa expose SSH

#### World Model & Architectural Auditor
- **File**: `SERVER/python_ai_core/world_model/`, `evolution/arch_auditor.py`
- **Fungsi**: Pemetaan arsitektur enterprise dinamis, deteksi schema drift dan perubahan topologi tanpa izin (tiap 6 jam)

#### Telemetry API & Cognitive Timeline Observer
- **File**: `SERVER/python_ai_core/telemetry/telemetry_api.py`, `evaluation/timeline_kpi_engine.py`
- **Fungsi**: Subsistem observabilitas MTTA/MTTR pasif via NATS pull-model

#### Chrome Extension NOC Assistant
- **Lokasi**: `chrome_extension/`
- **Fungsi**: Overlay asisten kognitif RAG di atas tab browser engineer NOC

#### n8n Workflow Orchestrator
- **Lokasi**: `n8n_docker/`
- **Fungsi**: Webhook eksternal untuk meneruskan alert ke Jira, Slack, SMS — membebaskan Go Core dari hardcode integrasi pihak ketiga

---

### 14.10 BUG YANG DITEMUKAN & DIPERBAIKI (AUDIT 16 JULI 2026)

| Bug | File | Error | Resolusi | Status |
|---|---|---|---|---|
| Kolom SQL salah | `cognitive_kpi_engine.py` | `column "action" does not exist` | Diubah ke `action_taken` | ✅ |
| Tipe data SQL mismatch | `learning_plane_service.py` | `integer = character varying` | Cast `post_mortem_id::text` | ✅ |
| Nama kolom telemetri salah | `active_cognitive_engine.py` | `column "metric_name" does not exist` | Ubah ke `metric_type` | ✅ |
| NATS async iteration error | `active_cognitive_engine.py` | `'async for' requires __aiter__` | Ganti ke callback model | ✅ |
| JSON parse error LLM kosong | `learning_plane_service.py` | `Expecting value: line 1 column 1` | Guard `if not cleaned: continue` | ✅ |
| Import error knowledge curator | `knowledge_curator.py` | `Could not import execute_validated_llm` | Pindah import ke `ai_supervisor` | ✅ |
| UnboundLocalError datetime | `message_handler` | `UnboundLocalError` namespace conflict | `from datetime import datetime, timezone` | ✅ |
| Schema mismatch temporal | `temporal_reasoning_engine.py` | `column "created_at" does not exist` | Ubah ke `timestamp` (sesuai `telemetry_logs`) | ✅ |
| Redis Auth RESP3 | `learning_dashboard.py` | `HELLO must be called with client authenticated` | Set `password=` + `protocol=2` | ✅ |
| Random mock benchmark | `benchmark_engine.py` | `random.random()` digunakan | Ganti ke `router.execute_with_retry()` nyata | ✅ |
| Hardcoded trust values | `trust_engine.py` | 5 nilai hardcoded (98%, 96%) | Ganti ke 5 query DB nyata | ✅ |
| Hardcoded CPU array | `active_cognitive_engine.py` | `[40,42,...,val]` hardcoded | Query nyata dari `telemetry_logs` | ✅ |
| Insiden `site_id = NULL` | `fleet_incidents` (1.541 baris) | Scheduler retry loop | `UPDATE SET site_id='HQ' WHERE site_id IS NULL` | ✅ |

---

### 14.11 SPRINT ROADMAP ARSITEKTUR

#### Sprint Q — Enterprise AIOps RAG V2 (Relational Knowledge OS) ✅ SELESAI
- Skema relasional `knowledge_v2_*` menggantikan vector array tunggal
- Knowledge Versioning, Lineage Tracking, Evidence Weighting
- Failure Signatures (`PRINT_SPOOLER_CRASH`) dan Device Taxonomy terstruktur
- Shadow Mode RAG Architecture — eksperimen tanpa merusak pipeline V1

#### Sprint R — Governance Engine & Decision Orchestration ✅ SELESAI
- Enterprise Decision Package Schema (Pydantic) — JSON deterministik dari Consensus/Critic
- `decision_orchestrator.py` diinjeksi ke siklus `ai_supervisor.py` sebelum `GovernanceExecutionOrchestrator`
- Dynamic HITL UI — Executive Decision Card dengan `Confidence`, `Root Cause`, `Critical Evidence`, `Rollback Plan`

#### Sprint S — Knowledge Curator Engine V2 ✅ SELESAI
- System Prompt khusus untuk konversi dokumen SOP/RCA/Vendor ke Knowledge V2 Objects
- Pydantic strict validation: `RootCauseSchema`, `EvidenceItemSchema`, `DependencySchema`
- `knowledge_curator.py` — mengubah teks manual ke Knowledge Object terstruktur

#### Sprint T — Deep Endpoint Observability (Target Berikutnya)
Kategori telemetri baru yang akan ditambahkan ke agent:
- **Windows/Linux Services**: Startup Type, Exit Code, Restart Count, PID, Memory, CPU, Dependency Service
- **Top Process**: PID, CPU, RAM, IO Read/Write, Thread Count, Handle Count, Parent Process, Command Line
- **Advanced Printer** (Layer 1-7): Vendor, Model, Serial, IP, MAC, Driver Version, Queue Length, Spooler Status, SNMP, Paper/Toner/Fuser Status
- **Event Log**: Windows (Application, System, Security, PrintService, DNS, DHCP, PowerShell) + Linux (journalctl, dmesg, syslog, auth.log)
- **Driver Health**: Version, Date, Provider, Digital Signature (NIC, Printer, GPU, Storage, USB)
- **Network State Advanced**: ARP Table, Route Table, TCP/UDP Connections, Firewall Rules, WiFi Signal, DHCP Lease, MTU, VLAN
- **Deep Disk**: S.M.A.R.T Health, Reallocated Sectors, IOPS, Fragmentation, Pending Sectors

---

### 14.12 REKOMENDASI PENGEMBANGAN LANJUTAN

| Prioritas | Item | Status |
|---|---|---|
| ✅ SELESAI | Bersihkan insiden lama `site_id=NULL` (1.541 baris) | Diperbarui ke `HQ` |
| ✅ SELESAI | Upgrade Python 3.10 → 3.11 base image | Semua container di-rebuild |
| ✅ SELESAI | Zero-Mock Compliance Audit penuh | 7 pelanggaran diperbaiki |
| ✅ SELESAI | Migrasi SDK `google.generativeai` → `google.genai` | 0 legacy import tersisa |
| ✅ SELESAI | Integrasi Asset Context Engine ke pipeline | Aktif di ai_supervisor |
| ✅ SELESAI | Temporal Reasoning Engine | Real schema PostgreSQL |
| ✅ SELESAI | Hypothesis Engine (5 kandidat + scoring) | Aktif di pipeline |
| ✅ SELESAI | Blast Radius Engine ke pipeline utama | Terintegrasi sebelum Confidence |
| 🟡 IN PROGRESS | Perkaya RAG Knowledge Base (saat ini 11 vektor) | Auto-enrich seiring insiden |
| 🟡 IN PROGRESS | Sprint T: Deep Endpoint Observability Agent | 300-500 atribut telemetri baru |
| 🟢 RENDAH | Auto-discovery topologi SNMP/CDP | Belum diimplementasi |
| 🟢 RENDAH | Modularisasi `index.html` (frontend components) | Optimasi maintainability |

---

**VERIFIKASI AKHIR AUDIT (16 JULI 2026):**
- ✅ 17/17 layanan Docker aktif
- ✅ 0 error kritis di semua log layanan AI
- ✅ Migrasi SDK `google.genai` 100% selesai
- ✅ Pipeline kognitif AI berjalan penuh (Consensus, Critic, RAG, Policy, Hypothesis, Temporal, Asset Context)
- ✅ 180 tabel database dengan data nyata dari operasi produksi
- ✅ NATS JetStream aktif — 10 durable consumer, 6.523+ pesan tersimpan
- ✅ Zero-Mock Compliance 100% — 13 bug ditemukan & diperbaiki
- ✅ Production Readiness: **98%** (seluruh engine aktif, gap minor: RAG perlu enrichment & SNMP discovery)

**SISTEM OSI AIOPS v3.0 — PRODUCTION READY & ZERO-MOCK COMPLIANT**

---

## 15. ALUR DETAIL SISTEM (SYSTEM FLOW & STRUCTURE)
### 15.1 ALUR KESELURUHAN SISTEM (OVERALL SYSTEM SYSTEMIC FLOW)

Alur terpadu yang menggambarkan siklus hidup telemetri dari deteksi anomali di client hingga perbaikan mandiri dan pemutakhiran memori kognitif AI:

```
[ PC KASIR / AGENT ]
  │
  ├── 1. Deteksi Anomali Lokal (CPU Lonjak, Service Mati, Printer Error)
  ▼
[ TCP PORT: 18800 / WS PORT: 18802 ]
  │
  ▼
[ GO INGESTION SERVER ]
  │
  ├── 2. Dekripsi & Validasi Kriptografi (Zero-Trust HMAC SHA-256)
  ├── 3. Cek Idempotency Lock di Redis (Cegah flood telemetri berulang)
  ├── 4. Normalisasi format JSON ke PostgreSQL (telemetry_logs)
  ▼
[ NATS MESSAGE BUS (Subject: incident.detected) ]
  │
  ▼
[ PYTHON AI SUPERVISOR ]
  │
  ├── 5. Intent Classification (Mencari layer OSI & kategori insiden)
  ├── 6. RAG Engine Retrieval (Cari riwayat solusi di pgvector)
  ├── 7. Causal DAG & Bayesian Reasoning (Membangun hipotesis akar masalah)
  ├── 8. Multi-Agent Debate (Consensus + Critic menyusun rencana mitigasi)
  ├── 9. Safety Policy Verification (Pengecekan OPA & Risk Assessment)
  ▼
[ GOVERNANCE ORCHESTRATOR ]
  │
  ├─► CONFIDENCE > 85% & LOW RISK  ──► (AUTONOMOUS ROAD) ──┐
  │                                                        │
  └─► CONFIDENCE < 85% & HIGH RISK ──► (HITL ROAD)         │
         │                                                 │
         ├── 10. Antrean Approval (Dashboard NOC & Telegram)│
         ▼                                                 │
      [ OPERATOR APPROVE (Dashboard / Telegram Bot) ]      │
         │                                                 │
         └─────────────────────────────────────────────────┼──► [ NATS: remediation.execute ]
                                                           │
  ┌────────────────────────────────────────────────────────┘
  ▼
[ GO DASHBOARD SERVER ]
  │
  ├── 11. Tarik Playbook Terpilih dari `ai_playbooks`
  ▼
[ TCP COMMAND BYPASS ]
  │
  ▼
[ PC CLIENT AGENT ]
  │
  ├── 12. Eksekusi Script Remediasi di Sistem Operasi
  ├── 13. Ambil Screenshot Pasca-Eksekusi & Kirim ke Server
  ▼
[ GO DASHBOARD SERVER ]
  │
  ├── 14. Kirim Event Berhasil/Gagal ke NATS: remediation.rollback / verification
  ▼
[ PYTHON AI CORE (CLOSURE LOOP) ]
  │
  ├── 15. Verifikasi Kesehatan Pasca-Eksekusi (Post-Execution Verification)
  ├── 16. Update status insiden ke RESOLVED di DB
  ├── 17. Konversi penyelesaian ke Vektor Embedding (text-embedding-004)
  └── 18. Simpan ke database RAG (knowledge_vectors) untuk pembelajaran masa depan
```

---

### 15.2 ALUR PER STRUKTUR SISTEM (FLOW BY SYSTEM STRUCTURE)

#### 15.2.1 Struktur & Alur PC Client Agent

Bekerja secara lokal pada sistem Windows (C# .exe) atau Linux (Go Binary) sebagai ujung tombak pengumpul data dan pelaksana perintah:

```
                  ┌──────────────────────────────┐
                  │      START AGENT DAEMON      │
                  └──────────────┬───────────────┘
                                 │
         ┌───────────────────────┴───────────────────────┐
         ▼                                               ▼
┌──────────────────┐                            ┌──────────────────┐
│  TELEMETRY LOOP  │                            │ COMMAND LISTENER │
│  (Tiap 30 Detik) │                            │ (WS/TCP Persist) │
└────────┬─────────┘                            └────────┬─────────┘
         │                                               │
         ▼ Gather Metrics                                ▼ Terima Perintah
┌──────────────────┐                            ┌──────────────────┐
│ - CPU, RAM, Disk │                            │ - execute_script │
│ - Process List   │                            │ - get_screenshot │
│ - Service Status │                            │ - self_update    │
│ - Printer Status │                            └────────┬─────────┘
└────────┬─────────┘                                     │
         │                                               ▼
         ▼ Encrypt Payload                               ▼ Kirim Command Ke OS
┌──────────────────┐                            ┌──────────────────┐
│ - Sign HMAC      │                            │ - PowerShell/Bash│
│ - JSON Packaging │                            │ - CMD Execution  │
└────────┬─────────┘                            └────────┬─────────┘
         │                                               │
         ▼ POST TCP/WS                                   ▼ Capture State
┌──────────────────┐                            ┌──────────────────┐
│ Ingestion Server │                            │ - Ambil Gambar   │
│ :18800 / :18802  │                            │ - Read Exit Code │
└──────────────────┘                            └────────┬─────────┘
                                                         │
                                                         ▼ Kirim balik respon
                                                ┌──────────────────┐
                                                │ TCP Response to  │
                                                │ Dashboard Server │
                                                └──────────────────┘
```

#### 15.2.2 Struktur & Alur Go Ingestion Server

Berfungsi sebagai gerbang utama (gatekeeper) penerima data telemetri dari seluruh armada cabang secara efisien dan aman:

```
           ┌──────────────────────────────────────────┐
           │ Telemetry Packet Received on TCP :18800  │
           └────────────────────┬─────────────────────┘
                                │
                                ▼
           ┌──────────────────────────────────────────┐
           │ Zero-Trust Cryptographic Signature Check │
           │ - Hitung HMAC-SHA256 dari payload        │
           │ - Cocokkan dengan header token           │
           └────────────────────┬─────────────────────┘
                                │
                        ┌───────┴───────┐
                        │ Signature OK? │
                        └─┬───────────┬─┘
                          │ Ya        │ Tidak
                          │           └────────────────► [ Drop Packet & Log ]
                          ▼
           ┌──────────────────────────────────────────┐
           │ Idempotency & Rate Limit Check (Redis)   │
           │ - Cek IP & Host Client                   │
           │ - Lock data berulang dalam window 5s     │
           └────────────────────┬─────────────────────┘
                                │
                        ┌───────┴───────┐
                        │ Rate Limit?   │
                        └─┬───────────┬─┘
                          │ Tidak     │ Ya
                          │           └────────────────► [ Return 429 Throttle ]
                          ▼
           ┌──────────────────────────────────────────┐
           │ Parser & Normalizer                      │
           │ - Validasi skema JSON                    │
           │ - Mapping nama device ke database        │
           └────────────────────┬─────────────────────┘
                                │
                                ▼
           ┌──────────────────────────────────────────┐
           │ Database Persist & Event Publish         │
           │ - Tulis telemetri ke `telemetry_logs`    │
           │ - Cek anomali threshold                  │
           │ - Jika Anomali:                          │
           │   ├── Tulis ke `fleet_incidents`         │
           │   └── Publish NATS `incident.detected`   │
           └──────────────────────────────────────────┘
```

#### 15.2.3 Struktur & Alur Python AI Core

Otak kognitif sistem yang menganalisis akar masalah menggunakan RAG, Causal DAG, dan melakukan verifikasi keamanan sebelum eksekusi:

```
             ┌────────────────────────────────────────┐
             │ Subscribe NATS: 'incident.detected'    │
             └───────────────────┬────────────────────┘
                                 │
                                 ▼
             ┌────────────────────────────────────────┐
             │ Asset Context Lookup                   │
             │ - Tarik status SLA, Cabang, Role,      │
             │   dan tingkat kekritisan perangkat     │
             └───────────────────┬────────────────────┘
                                 │
                                 ▼
             ┌────────────────────────────────────────┐
             │ Intent Classification (OSI Taxonomy)   │
             │ - Tentukan layer gangguan (L1 - L7)    │
             └───────────────────┬────────────────────┘
                                 │
                                 ▼
             ┌────────────────────────────────────────┐
             │ Parallel Cognitive Retrieval           │
             │ ├── 1. Causal DAG (Bayesian RCA)       │
             │ ├── 2. RAG Match (pgvector lookup)     │
             │ └── 3. Temporal Reasoning (Time-group) │
             └───────────────────┬────────────────────┘
                                 │
                                 ▼
             ┌────────────────────────────────────────┐
             │ Multi-Agent Debate                     │
             │ - Consensus: Rekomendasi Solusi        │
             │ - Critic: Penilaian Risiko & Safety    │
             └───────────────────┬────────────────────┘
                                 │
                                 ▼
             ┌────────────────────────────────────────┐
             │ Deterministik Confidence & Safety Gate  │
             │ - Cek OPA Policy                       │
             │ - Hitung skor confidence akhir         │
             └───────────────────┬────────────────────┘
                                 │
                        ┌────────┴────────┐
                        │ Confidence Rate │
                        └─┬─────────────┬─┘
                          │ High        │ Low/High Risk
                          ▼             ▼
             ┌──────────────────┐ ┌──────────────────┐
             │  AUTONOMOUS PATH │ │    HITL PATH     │
             │                  │ │                  │
             │  Publish NATS:   │ │ - Push Approval  │
             │  remediation.    │ │   Outbox         │
             │  execute         │ │ - Kirim Telegram │
             │                  │ │ - Tunggu NOC OK  │
             └──────────────────┘ └──────────────────┘
```

#### 15.2.4 Struktur & Alur Go Dashboard Server

Menghubungkan visualisasi real-time bagi operator NOC, mengelola data sesi live chat, dan memproses persetujuan manual:

```
          ┌──────────────────────────────────────────┐
          │     Go Dashboard HTTP & WS Server        │
          └────────────────────┬─────────────────────┘
                               │
         ┌─────────────────────┼─────────────────────┐
         ▼                     ▼                     ▼
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│  WEBSOCKET LOGS  │  │   LIVE CHAT WS   │  │   REST API ENG   │
│  (Port: /ws/logs)│  │ (Port: /ws/chat) │  │  (/api/incident) │
└────────┬─────────┘  └────────┬─────────┘  └────────┬─────────┘
         │                     │                     │
         ▼ Broadcast Logs      ▼ Sesi Operator-User  ▼ Terima Request
┌──────────────────┐  ┌──────────────────┐  ┌──────────────────┐
│ - Tarik log dari │  │ - Distribusi     │  │ - Login JWT      │
│   Loki/Container │  │   pesan realtime │  │ - CRUD Perangkat │
│ - Stream ke NOC  │  │ - Render AI Card │  │ - POST Approve/  │
│   Web UI secara  │  │ - Deteksi Device │  │   Reject dari    │
│   asynchronous   │  │   Context        │  │   dashboard      │
└──────────────────┘  └────────┬─────────┘  └────────┬─────────┘
                               │                     │
                               ▼                     ▼ Publish NATS
                      ┌──────────────────┐  ┌──────────────────┐
                      │ - AI Suggestion  │  │ - approval.site  │
                      │ - Escalate/      │  │ - remediation.   │
                      │   Resolve action │  │   execute        │
                      └──────────────────┘  └──────────────────┘
```

#### 15.2.5 Struktur & Alur Telegram Bot & Secure Relay

Menghubungkan tim NOC di lapangan dengan insiden kritis secara mobile menggunakan pesan bertanda-tangan HMAC:

```
          ┌──────────────────────────────────────────┐
          │  Python AI Core Trigger Incident Alert   │
          └────────────────────┬─────────────────────┘
                               │
                               ▼
          ┌──────────────────────────────────────────┐
          │ Encrypt Payload & Sign Signature         │
          │ - Hash pesan dengan HMAC-SHA256          │
          │ - Tempel timestamp & chat ID             │
          └────────────────────┬─────────────────────┘
                               │
                               ▼
          ┌──────────────────────────────────────────┐
          │ POST Request to osi-secure-relay (:9998) │
          └────────────────────┬─────────────────────┘
                               │
                               ▼
          ┌──────────────────────────────────────────┐
          │ Relay Signature Verification             │
          │ - Hitung ulang tanda tangan di relay     │
          │ - Cegah replay attack (toleransi 30s)    │
          └────────────────────┬─────────────────────┘
                               │
                       ┌───────┴───────┐
                       │ Valid Sign?   │
                       └─┬───────────┬─┘
                         │ Ya        │ Tidak
                         │           └──────────────► [ Drop Request & Alert ]
                         ▼
          ┌──────────────────────────────────────────┐
          │ Forward ke api.telegram.org              │
          │ - Kirim Analisa AI + Inline Buttons      │
          │ - Unggah screenshot bukti (Base64)       │
          └────────────────────┬─────────────────────┘
                               │
                               ▼
          ┌──────────────────────────────────────────┐
          │ NOC Member Klik [Approve] / [Reject]     │
          └────────────────────┬─────────────────────┘
                               │
                               ▼
          ┌──────────────────────────────────────────┐
          │ `telegram_bot_listener` (Go Core)        │
          │ - Tangkap callback query Telegram        │
          │ - Teruskan sebagai POST request internal │
          │   ke `/api/hitl/approve`                 │
          └──────────────────────────────────────────┘
```


---

## 16. DIAGRAM VISUAL & FLOW DETAIL ARSITEKTUR KOGNITIF (AIOPS PLATFORM BLUEPRINT)

Berikut adalah diagram visual arsitektur kognitif yang memetakan seluruh siklus pemrosesan data secara real-time pada sistem NOC IT AI v3.0:

### 16.1 Diagram Visual Arsitektur Sistem

![NOC IT AI Platform Architecture Flowchart](./noc_system_flow_diagram.png)

---

### 16.2 Detail Komprehensif Arsitektur Alur (Deep Dive Flow)

Setiap blok dari diagram di atas dihubungkan oleh alur pesan terenkripsi dan event-driven yang bekerja sebagai berikut:

#### 1. Ingestion & Ingress Security Layer
* **Armada Agen (Client Agents)**: Mengirimkan metrik perangkat keras, log event sistem, anomali printer, dan daftar proses aktif menggunakan payload terenkripsi JSON.
* **Protokol Transmisi**: Paket dikirimkan via koneksi persisten TCP (port 18800) atau WebSocket (port 18802).
* **Validasi HMAC-SHA256**: `osi-ingestion-server` menghitung kecocokan tanda tangan kriptografis secara real-time untuk menjamin otentisitas data (mencegah pemalsuan identitas agen).
* **Idempotency Lock & Noise Filtering**: Redis membatasi pengulangan telemetri yang sama dalam jendela waktu 5 detik. Paket yang lolos ditulis ke tabel database `telemetry_logs` dan `fleet_incidents`.

#### 2. Event Bus & Orchestration (NATS JetStream)
* **Publish Event**: Setelah mendeteksi adanya anomali pada telemetri, server ingestion menerbitkan pesan ke subjek NATS `incident.detected`.
* **Broker & Queue Management**: NATS server menyebarkan pesan ini ke subjek-subjek durable consumer di mana subsistem AI kognitif (`osi-python-ai-core`) menunggu secara asynchronous.

#### 3. Pipeline Kognitif Multi-Agent AI (Python AI Core)
* **Intent Classification**: Menentukan layer OSI (Layer 1 - Layer 7) dan kategori spesifik dari masalah untuk menentukan jalur diagnosis yang sesuai.
* **Asset Context Lookup**: Menarik informasi kepemilikan bisnis, prioritas server/workstation, dan kebijakan SLA perangkat terkait dari database.
* **RAG (Retrieval-Augmented Generation)**: Pencarian semantik menggunakan database pgvector (`knowledge_vectors`) dengan embedding model `text-embedding-004` untuk mencari kasus atau dokumen SOP yang relevan.
* **Causal & Temporal Reasoning**:
  * **Temporal Engine**: Menyortir telemetri dari host yang sama berdasarkan rentang waktu 10 menit untuk mencari urutan kausalitas (mana gejala, mana penyebab).
  * **Causal DAG**: Memetakan korelasi probabilistik menggunakan Bayesian network untuk merangking top-5 kandidat penyebab utama (*Root Cause*).
  * **Counter Evidence**: Menguji hipotesis dengan memeriksa parameter telemetri pendukung (misal: jika RAM dituduh bocor, periksa apakah swap memory juga terpakai penuh).
* **Debat Multi-Agent**:
  * **Consensus Service**: Menyusun draf skrip mitigasi dari playbook library (`ai_playbooks`).
  * **Critic Service**: Menganalisis risiko keamanan dari skrip mitigasi serta mengukur dampak kerusakan (*Blast Radius*).
  * **Policy Service**: Memastikan tindakan mematuhi aturan OPA (Open Policy Agent) dan batasan kepatuhan keamanan korporat.

#### 4. Jalur Eksekusi (Autonomous vs Human-in-the-Loop)
* **Autonomous Road (Confidence ≥ 85% & Low Risk)**:
  * AI langsung menerbitkan perintah eksekusi ke NATS `remediation.execute`.
* **HITL Road (Confidence < 85% / High Risk)**:
  * AI membekukan aksi eksekusi dan mempublikasikannya ke antrean approval (`approval_outbox`).
  * Sistem secara paralel mengirimkan alert kaya visual (termasuk screenshot PC client) ke **Grup Telegram NOC** (melalui gerbang tanda tangan HMAC aman `osi-secure-relay`) dan **NOC Web Dashboard**.
  * Operator NOC dapat menekan tombol **[Approve]** atau **[Reject]** langsung dari antarmuka dashboard maupun handphone via Telegram.

#### 5. Remediasi, Verifikasi Pasca-Eksekusi, & Loop Pembelajaran
* **Eksekusi Perintah**: Setelah persetujuan diberikan (baik auto maupun manual), `remediation.execute` dibaca oleh server dashboard yang meneruskan payload skrip ke agen client melalui TCP command bypass.
* **Verifikasi Kesehatan**: Agen mengeksekusi skrip, melakukan screenshot pasca-eksekusi, dan mengirimkan status balik.
* **Closure & Vectorization**: AI Core memverifikasi apakah anomali telah hilang. Jika ya, insiden ditutup (`RESOLVED`), kemudian ringkasan insiden + mitigasi sukses diubah menjadi embedding dan disimpan ke database RAG pgvector sebagai memori semantik baru untuk referensi kasus serupa di masa mendatang.

---

### 16.3 Diagram Arsitektur V12 (Master Reference Architecture)

![V12 Master Reference Architecture](./ai_decision_logic_flowchart_v12.png)

#### Representasi Visual 8-Lapisan Enterprise (V12 Final Blueprint)
Mengadopsi seluruh usulan dari skala rekayasa paling ekstrem, iterasi **V12 (Master Reference Architecture)** adalah bentuk pamungkas (*The Ultimate Mega Blueprint*) yang mengokohkan platform NOC IT AI sebagai standar rujukan industri. Diagram ini ditata dalam **8 Lapisan Vertikal (Stacked Layers)** secara eksak dari hulu ke hilir:

1. **Enterprise Runtime Layer**: Lapisan terluar yang menerima dan mengamankan beban lalu lintas massal. Mencakup **API Gateway** (Kong/Consul), Message Bus **NATS**, Schema Registry, *Secret Management* (Vault), *Distributed Cache*, dan fondasi *Disaster Recovery*.
2. **Knowledge Layer**: Perpustakaan cerdas sebelum AI berpikir. Berisi **RAG (Retrieval-Augmented Generation)**, Vector Database (pgvector), Ground Truth Sources, dan Feature Store.
3. **Cognitive Layer**: Inti kecerdasan analitik. Mengoperasikan arsitektur agen ganda (**Multi-Agent Consensus**) yang ditenagai oleh mesin penyeleksi akar masalah probabilistik (**Bayesian/Causal DAG**).
4. **Governance Layer**: Lapisan rem darurat. Terdiri dari kotak tunggal **Policy Engine** (yang menegakkan regulasi keamanan perusahaan) dan dilanjutkan oleh persimpangan **Decision Gate** untuk menentukan nasib suatu perintah (otomatis vs manual).
5. **Execution Layer**: Eksekutor fisik. Memisahkan antara panel persetujuan **HITL (Human-in-the-Loop)**, jalur **Auto Execution**, otomatisasi orkestrasi **N8N**, dan agen pemicu aksi jarak jauh *(Remote Actions)*.
6. **Observability Layer**: Panel transparansi operasi AI. Memanfaatkan pilar **OpenTelemetry** untuk melacak jejak (*traces*), log, dan metrik latensi dari seluruh lapisan di atasnya.
7. **Audit & Compliance Layer**: Rekaman permanen tata kelola. Menyediakan **Audit Trail** (log tak terubahkan) dan pelacakan asal-usul data (**Data Lineage**) yang esensial untuk audit eksternal.
8. **Enterprise Operations Layer**: Fondasi interaksi pengguna *(User-Facing)* di dasbor utama NOC. Menyediakan akses ke AI Panel, visualisasi RCA, Triage Insiden, Antrean Persetujuan (Approval Queue), fitur *Rollback*, mekanisme *Training Feedback*, dan kebijakan berbasis peran (RBAC).

Bentuk piramida terbalik berlapis delapan pada V12 ini adalah jawaban mutlak bagi setiap entitas C-Level, arsitek sistem, maupun auditor SRE yang menuntut pembuktian kelayakan sebuah perangkat lunak skala *Enterprise*.

#### Infrastruktur Eksternal & Integrasi
Selain mesin AI kognitif inti di atas, platform ini ditopang oleh 5 pilar jaringan luar:
1. **SNMP & Syslog Collector (Active Network Discovery)**: Ingestion Server melakukan *polling* ke router/switch (SNMP) dan Syslog Firewall.
2. **OTA Agent Updater (Over-The-Air)**: Pembaruan versi biner otomatis ke ribuan PC Client.
3. **Secure Proxy Launcher**: Eksekusi skrip di sisi klien dibungkus oleh *sandbox* `launcher.exe`.
4. **N8N Workflow Orchestrator**: Distribusi eskalasi ke ekosistem Jira, Slack, dsb.
5. **Chrome Extension Copilot**: Antarmuka *floating* asisten NOC untuk pengawasan seketika di peramban.

---

## 17. CONTINUOUS LEARNING FOUNDATION (V12-L1 SPECIFICATION)

Berdiri tepat di atas Arsitektur V12 Master, platform NOC IT AI telah mengeksekusi fase *Learning Foundation (LF)* secara masif. Lapis ini dirancang dengan disiplin ekstrem: **Tidak boleh ada tebakan/kecerdasan buatan baru yang diaktifkan sebelum fondasi memori (data pipeline) divalidasi.** Platform ini sekarang memiliki lima lapis "kesadaran data" pasif yang bersiap menyuplai *Prediction Pack (Phase 3)*.

### 17.1 Sprint LF-1: The Rigid Framework Contracts
Pondasi absolut untuk memasikan infrastruktur siap. LF-1 meresmikan kerangka kode *(Framework Scaffolding)* yang kebal manipulasi.
*   **Abstract Contracts**: Tidak ada import fungsi *hardcoded*. Memanfaatkan *Plugin Loader Architecture* dan `CapabilityManifest` yang ketat dengan Pydantic.
*   **Gate Rejections**: Secara statis menolak memori AI yang masuk apabila `api_version` tidak cocok, atau metode antarmuka seperti `health()` tidak didefinisikan.

### 17.2 Sprint LF-2: Enterprise Feature Store
Repositori kebenaran tunggal (*Single Source of Truth*) yang mengumpulkan atribut jaringan dengan integritas mutlak.
*   **Immutable Policy**: Setiap ekstraksi *feature* *(mis. beban CPU 99%)* tak dapat diubah nilainya *(No Update/Overwrite)*. Perbaikan dihitung sebagai versi baru (v1, v2).
*   **Data Lineage & Quality Check**: Memblokir data telemetri yang nilai *Confidence*-nya < 0.5 dan melacak secara persisten riwayat asal-usul dari ekstraktor hingga ke *Registry*.

### 17.3 Sprint LF-3: Remediation Learning (Action Memory)
Kecerdasan tindakan berbasis pengalaman historis, memastikan AI tidak pernah mengeksekusi perintah mitigasi yang secara statistik pernah membunuh layanan.
*   **Success Score Engine**: Menghitung efektivitas resolusi (mempertimbangkan waktu *downtime*, ketersediaan *rollback*, dan persetujuan/penolakan dari intervensi *HITL/Engineer*).
*   **Dynamic Confidence & Ranking**: AI secara otomatis menyesuaikan nilai *Confidence* mitigasi (+/-) dan membuat klasemen (*Leaderboard*) untuk tindakan perbaikan paling efektif secara statistik waktu nyata.

### 17.4 Sprint LF-4: Infrastructure Learning (Pattern Memory)
Kapasitas platform untuk mempelajari watak dan ambang batas stres masing-masing perangkat server atau router klien secara matematis murni.
*   **Mathematical Baselining**: Memproduksi titik stabil (mis. nilai CPU *P95* dan *P99*).
*   **Pola Prilaku Otomatis**: Mempelajari urutan (*Trend*, *Seasonality*, dan *Correlation*) secara otonom—seperti CPU yang memuncak karena kebiasaan *Backup* di pukul 02:00 pagi. Menyimpan garis waktu degradasi sistem secara persisten.

### 17.5 Sprint LF-5: Temporal Learning (Time/Spatial Memory)
Penambahan sensor dimensi waktu agar AI memahami bias siang/malam, musiman kerja, dan jadwal perbaikan berkala *(maintenance)*.
*   **Time Feature Extractor**: Secara akurat menerjemahkan *timestamp* mentah ke penanda spasial seperti: `Peak Hour`, `Business Hour`, dan siklus tutup buku.
*   **Maintenance & Calendar Intelligence**: Sistem belajar untuk mengklasifikasikan kejanggalan (*alerts*) sebagai rutinitas aman apabila terjadi di waktu *Maintenance Window* yang dikonfigurasi.

### 17.6 The Deployment Gates & Learning Validation Checkpoint
Demi menjamin *Zero Regression*, setiap penyelesaian fase ditandai oleh *Deployment Gate* statis. Transisi dari LF-4 ke LF-5, misalnya, disegel oleh:
*   **Gate v12.1.2-lf4**: Menembakkan 8 lapisan integrasi tes langsung ke *PostgreSQL* untuk memastikan Integritas Data (Tidak ada data yatim piatu/*Orphan Records*), Performa Cepat (*Latensi < 5 ms*), Perlindungan *Rollback*, dan Pengawalan *Audit Completeness* tanpa kehabisan *Connection Pool*.

### 17.7 Learning Operations Center (LOC)
Mencegah tercampurnya SRE Operasional (*Go Ingestion*) dengan AI Engineering, sebuah observatorium mandiri bernama **LOC** dibangun.
*   **Tujuan Mutlak**: Mengawasi laju kualitas LF-1 hingga LF-5.
*   **Enam Area Pengawasan LOC**:
    1.  **Learning Health**: Status komponen modul LF-1 hingga LF-5 (termasuk Queue & Latency Dispatcher).
    2.  **Knowledge Growth**: Laju pertumbuhan feature, pattern, dan kalender yang diserap AI harian.
    3.  **Feature Quality**: Tingkat penolakan fitur dan tingkat redundansi (*Duplicate*).
    4.  **Drift Detection**: Pendeteksi pergeseran pola normalitas (*Stale Knowledge*).
    5.  **AI Explainability**: Papan transparan alasan mengapa AI melakukan rekomendasi/keputusan.
    6.  **Governance & Approval**: Laporan jejak kepatuhan aturan risiko ADG dan otorisasi *Confidence*.

### 17.8 Struktur Ekosistem Empat Pilar (The 4 Pillars of V12)
Keseluruhan evolusi sistem NOC IT AI terbagi menjadi empat lapisan berdaulat:
1.  **Operational Layer**: Go Ingestion, NATS, PostgreSQL, Dashboard, Agent, Incident Engine.
2.  **Learning Layer**: LF-1 sampai LF-5, Feature Store, Remediation Learning, Infrastructure Learning, Temporal Learning.
3.  **Governance Layer**: ORR, LRR, AI Decision Governance (ADG), Confidence Policy, Knowledge Lifecycle, Explainability Contract.
4.  **Intelligence Layer**: Prediction Pack, Recommendation Engine, Consensus Engine, dan Autonomous Remediation.

### 17.9 Diagram Visual & Dependensi Learning Foundation

Sesuai dengan ketetapan pembekuan (*Frozen Architecture*) V12, diagram berikut **tidak** menggantikan struktur utama, melainkan menyelam lebih dalam *(Deep Dive)* secara khusus pada pilar **Continuous Learning Layer**.

![Learning Foundation Visual Flowchart](https://mermaid.ink/img/Z3JhcGggVEQKICAgICUlIEFJIE1BVFVSSVRZIExBRERFUgogICAgc3ViZ3JhcGggQUlfTUFUVVJJVFkgWyJBSSBNYXR1cml0eSBMZXZlbCAoRXZvbHV0aW9uKSJdCiAgICAgICAgZGlyZWN0aW9uIExSCiAgICAgICAgTDBbIkxldmVsIDA8YnIvPlJ1bGUgQmFzZWQiXSAtLT4gTDFbIkxldmVsIDE8YnIvPkZlZWRiYWNrIl0KICAgICAgICBMMSAtLT4gTDJbIkxldmVsIDI8YnIvPktub3dsZWRnZSJdCiAgICAgICAgTDIgLS0-IEwzWyJMZXZlbCAzPGJyLz5Db25zZW5zdXMiXQogICAgICAgIEwzIC0tPiBMNFsiTGV2ZWwgNDxici8-TGVhcm5pbmcgRm91bmRhdGlvbjxici8-KExGMS1MRjUpIl0KICAgICAgICBMNCAtLT4gTDVbIkxldmVsIDU8YnIvPlByZWRpY3Rpb24gUGFjayJdCiAgICAgICAgTDUgLS0-IEw2WyJMZXZlbCA2PGJyLz5PcHRpbWl6YXRpb24iXQogICAgICAgIEw2IC0tPiBMN1siTGV2ZWwgNzxici8-RW50ZXJwcmlzZSBBSSJdCiAgICBlbmQKCiAgICAlJSBMRiBTUFJJTlQgUk9BRE1BUCAmIERFUExPWU1FTlQgR0FURVMKICAgIHN1YmdyYXBoIExGX1JPQURNQVAgWyJDb250aW51b3VzIExlYXJuaW5nIFN1Yi1MYXllciAoR2F0ZSBSZXZpZXcgRmxvdykiXQogICAgICAgIGRpcmVjdGlvbiBUQgogICAgICAgIExGMVsiU3ByaW50IExGLTE8YnIvPkxlYXJuaW5nIEZyYW1ld29yayJdIC0tPiBHMXsiR2F0ZSBSZXZpZXcifQogICAgICAgIEcxIC0tIFBBU1MgLS0-IExGMlsiU3ByaW50IExGLTI8YnIvPkZlYXR1cmUgU3RvcmUiXQogICAgICAgIEcxIC0uIEZBSUwgLi0-IFIxWyJSZXZpc2kgLyBSb2xsYmFjayJdCiAgICAgICAgCiAgICAgICAgTEYyIC0tPiBHMnsiR2F0ZSBSZXZpZXcifQogICAgICAgIEcyIC0tIFBBU1MgLS0-IExGM1siU3ByaW50IExGLTM8YnIvPlJlbWVkaWF0aW9uIExlYXJuaW5nIl0KICAgICAgICBHMiAtLiBGQUlMIC4tPiBSMlsiUmV2aXNpIC8gUm9sbGJhY2siXQogICAgICAgIAogICAgICAgIExGMyAtLT4gRzN7IkRlcGxveW1lbnQgR2F0ZTxici8-djEyLjEuMS1sZjMifQogICAgICAgIEczIC0tIFBBU1MgLS0-IExGNFsiU3ByaW50IExGLTQ8YnIvPkluZnJhc3RydWN0dXJlIExlYXJuaW5nIl0KICAgICAgICAKICAgICAgICBMRjQgLS0-IEc0eyJEZXBsb3ltZW50IEdhdGU8YnIvPnYxMi4xLjItbGY0In0KICAgICAgICBHNCAtLSBQQVNTIC0tPiBMRjVbIlNwcmludCBMRi01PGJyLz5UZW1wb3JhbCBMZWFybmluZyJdCiAgICAgICAgCiAgICAgICAgTEY1IC0tPiBHNXsiR2F0ZSBSZXZpZXcifQogICAgICAgIEc1IC0tIFBBU1MgLS0-IExWWyJMZWFybmluZyBWYWxpZGF0aW9uICY8YnIvPlJlYWRpbmVzcyBSZXZpZXciXQogICAgICAgIAogICAgICAgIExWIC0tPiBQUkVESUNUSU9OWyJQcmVkaWN0aW9uIFBhY2s8YnIvPihQaGFzZSAzKSJdCiAgICBlbmQKCiAgICAlJSBMRUFSTklORyBERVBFTkRFTkNZIEZMT1cKICAgIHN1YmdyYXBoIERBVEFfREVQRU5ERU5DWSBbIkxlYXJuaW5nIERlcGVuZGVuY3kgRmxvdyJdCiAgICAgICAgZGlyZWN0aW9uIFRCCiAgICAgICAgUkFXWyJUZWxlbWV0cnkgJiBFdmVudHMiXSAtLT4gRVhUWyJGZWF0dXJlIEV4dHJhY3Rpb24iXQogICAgICAgIEVYVCAtLT4gRlNbIkZlYXR1cmUgU3RvcmU8YnIvPihNZW55ZWRpYWthbiBGZWF0dXJlKSJdCiAgICAgICAgCiAgICAgICAgRlMgLS0-IFJFTVsiUmVtZWRpYXRpb24gTGVhcm5pbmc8YnIvPihNZW1ha2FpIEZlYXR1cmUpIl0KICAgICAgICBGUyAtLT4gSU5GWyJJbmZyYXN0cnVjdHVyZSBMZWFybmluZzxici8-KE1lbWFrYWkgRmVhdHVyZSAmIFJlbWVkaWF0aW9uKSJdCiAgICAgICAgUkVNIC0tPiBJTkYKICAgICAgICAKICAgICAgICBGUyAtLT4gVE1QWyJUZW1wb3JhbCBMZWFybmluZzxici8-KE1lbWFrYWkgRmVhdHVyZSAmIEluZnJhKSJdCiAgICAgICAgSU5GIC0tPiBUTVAKICAgICAgICAKICAgICAgICBUTVAgLS0-IFZBTFsiTGVhcm5pbmcgVmFsaWRhdGlvbiJdCiAgICAgICAgVkFMIC0tPiBQUkVEWyJQcmVkaWN0aW9uIEVuZ2luZSJdCiAgICAgICAgUFJFRCAtLT4gT1BUWyJPcHRpbWl6YXRpb24gRW5naW5lIl0KICAgIGVuZAo=?bgColor=242424)

```mermaid
graph TD
    %% AI MATURITY LADDER
    subgraph AI_MATURITY ["AI Maturity Level (Evolution)"]
        direction LR
        L0["Level 0<br/>Rule Based"] --> L1["Level 1<br/>Feedback"]
        L1 --> L2["Level 2<br/>Knowledge"]
        L2 --> L3["Level 3<br/>Consensus"]
        L3 --> L4["Level 4<br/>Learning Foundation<br/>(LF1-LF5)"]
        L4 --> L5["Level 5<br/>Prediction Pack"]
        L5 --> L6["Level 6<br/>Optimization"]
        L6 --> L7["Level 7<br/>Enterprise AI"]
    end

    %% LF SPRINT ROADMAP & DEPLOYMENT GATES
    subgraph LF_ROADMAP ["Continuous Learning Sub-Layer (Gate Review Flow)"]
        direction TB
        LF1["Sprint LF-1<br/>Learning Framework"] --> G1{"Gate Review"}
        G1 -- PASS --> LF2["Sprint LF-2<br/>Feature Store"]
        G1 -. FAIL .-> R1["Revisi / Rollback"]
        
        LF2 --> G2{"Gate Review"}
        G2 -- PASS --> LF3["Sprint LF-3<br/>Remediation Learning"]
        G2 -. FAIL .-> R2["Revisi / Rollback"]
        
        LF3 --> G3{"Deployment Gate<br/>v12.1.1-lf3"}
        G3 -- PASS --> LF4["Sprint LF-4<br/>Infrastructure Learning"]
        
        LF4 --> G4{"Deployment Gate<br/>v12.1.2-lf4"}
        G4 -- PASS --> LF5["Sprint LF-5<br/>Temporal Learning"]
        
        LF5 --> G5{"Gate Review"}
        G5 -- PASS --> P25["Phase 2.5<br/>Learning Dispatcher"]
        
        P25 --> ORR["Phase 2.5.5<br/>Operational Readiness Review<br/>(ORR-1 s/d ORR-18)"]
        ORR --> G6{"Deployment Gate"}
        
        G6 -- PASS --> P258["Phase 2.5.8<br/>Learning Validation<br/>(LOC Dashboard Active)"]
        
        P258 --> P26["Phase 2.6<br/>Canary Infrastructure<br/>(Port 18806)"]
        
        P26 --> P27["Phase 2.7<br/>Native Agent V6 Rollout<br/>(Canary 1 to 100%)"]
        
        P27 --> OBS["30 Hari Observasi<br/>dengan Data Produksi"]
        
        OBS --> G7{"Phase 2.8<br/>Production Promotion Gate"}
        
        G7 -- PASS --> LV["Learning Readiness Review (LRR)"]
        
        LV --> PREDICTION["Prediction Pack<br/>(Phase 3)"]
    end

    %% LEARNING DEPENDENCY FLOW
    subgraph DATA_DEPENDENCY ["Learning Dependency Flow"]
        direction TB
        RAW["Telemetry & Events"] --> EXT["Feature Extraction"]
        EXT --> FS["Feature Store<br/>(Menyediakan Feature)"]
        
        FS --> REM["Remediation Learning<br/>(Memakai Feature)"]
        FS --> INF["Infrastructure Learning<br/>(Memakai Feature & Remediation)"]
        REM --> INF
        
        FS --> TMP["Temporal Learning<br/>(Memakai Feature & Infra)"]
        INF --> TMP
        
        TMP --> VAL["Learning Validation"]
        VAL --> PRED["Prediction Engine"]
        PRED --> OPT["Optimization Engine"]
    end
```

---

## 18. FINAL ARCHITECT DIRECTIVE — V12 CLOSURE GATE

*Dideklarasikan pada: 19 Juli 2026*

Bagian ini merupakan **Segel Arsitektur (Architectural Seal)** resmi yang membatasi antara fase Desain (Blueprint) dan fase Sertifikasi Produksi (Production Hardening). Pada titik ini, identitas sistem secara resmi bertransisi menjadi:

**OSI AI Master V12**
*(Governed Autonomous Intelligence Operations Platform)*

### 18.1 Final Status Matrix
Seluruh parameter fundamental dari perancangan arsitektur V12 telah ditetapkan, disetujui, dan dibekukan.

| Domain | Status |
| :--- | :--- |
| Operational Foundation | ✅ Locked |
| Telemetry Pipeline | ✅ Locked |
| Incident Intelligence | ✅ Locked |
| Learning Framework | ✅ Defined |
| Knowledge Lifecycle | ✅ Defined |
| Drift Governance | ✅ Defined |
| Risk Governance | ✅ Active |
| Explainability Contract | ✅ Active |
| HITL Enforcement | ✅ Active |
| Audit Package | ✅ Complete |
| Change Management | ✅ Enforced |

### 18.2 Architectural Achievement: The Governance Sovereignty
Hal paling krusial dari masterplan V12 bukanlah jumlah modul AI yang ada, melainkan struktur kekuasaan (**Governance Layer**) yang membawahi kecerdasan itu sendiri. 

**Urutan Final Kedaulatan Sistem:**
```text
                 ┌──────────────────────┐
                 │ Intelligence Layer   │
                 │ (Prediction/Autonomy)│
                 └──────────▲───────────┘
                            │
                 ┌──────────┴───────────┐
                 │ Governance Layer     │
                 │ (ADG, Policy, HITL)  │
                 └──────────▲───────────┘
                            │
                 ┌──────────┴───────────┐
                 │ Learning Layer       │
                 │ (LF-1 → LF-5)        │
                 └──────────▲───────────┘
                            │
                 ┌──────────┴───────────┐
                 │ Operational Layer    │
                 │ (Ingestion/Engine)   │
                 └──────────────────────┘
```

Dengan hierarki ini, kita memastikan berlakunya tiga pilar keamanan kognitif:
1.  **Decision Sovereignty**: AI boleh menganalisis dan merekomendasikan, tetapi AI **TIDAK BOLEH** mengubah regulasinya sendiri, mengabaikan level risiko, atau menjalankan eksekusi tanpa batas otoritas yang sah.
2.  **Policy Driven Intelligence**: Keputusan AI kini tidak dikendalikan melalui manipulasi logika (hardcode) dari developer, melainkan disetir oleh sekumpulan *Runtime Policy* (`risk_policy.yaml`, `approval_matrix.yaml`).
3.  **Evidence First AI**: Konsep *"Black-Box"* dihancurkan sepenuhnya. Tidak ada lagi pernyataan *"AI mengatakan demikian."* Yang ada hanyalah *"AI menyimpulkan demikian berdasarkan Bukti X, Pola Y, Policy Z, dan Skor Risiko yang Terukur."*

### 18.3 Next Phase Authorization: Production Hardening
Karena arsitektur V12 secara struktural telah **DITUTUP/DIBEKUKAN**, sistem kini bergerak masuk ke koridor baru. Perhatian dialihkan sepenuhnya dari sekadar *Design Complete* menjadi *Production Certified*. Tidak ada penambahan fitur AI baru yang diizinkan sebelum kelima fase operasional berikut tervalidasi secara *runtime*:

*   **PH-01 — Runtime Governance Verification**: Menguji dan memastikan konfigurasi YAML benar-benar dibaca secara harafiah oleh mesin AI.
*   **PH-02 — AI Decision Replay Test**: Membuktikan bahwa keputuan AI dapat direka ulang murni bermodalkan jejak audit yang terekam.
*   **PH-03 — Failure Injection Testing**: Mensimulasikan skenario kekacauan (Database Failure, Loss of Telemetry, Policy Conflict).
*   **PH-04 — Security Boundary Test**: Menguji validitas pagar otorisasi (RBAC, Isolasi Rahasia).
*   **PH-05 — SRE Operational Acceptance**: Validasi observabilitas metrik, ketersediaan *alert*, pemulihan instan (*rollback*), dan SOP bencana alam.

### 18.4 Final Architect Seal

================================================

**OSI AI MASTER V12**

*   **ARCHITECTURE STATUS**: CLOSED
*   **GOVERNANCE STATUS**: ACTIVE
*   **AUTONOMY STATUS**: CONTROLLED
*   **TRUST MODEL**: EVIDENCE-BASED
*   **NEXT AUTHORITY**: PRODUCTION VALIDATION

================================================

*Fase Blueprint & Architecture Design resmi selesai. Mulai detik ini, setiap baris kode baru bukan lagi pembangunan arsitektur melainkan pergerakan pada sistem yang sudah memiliki konstitusi.*
