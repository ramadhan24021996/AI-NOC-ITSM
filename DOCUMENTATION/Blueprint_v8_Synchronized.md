# OSI NOC IT AI — Blueprint v8.0 (Synchronized Edition)
## Dokumen Arsitektur Resmi — Source of Truth

> **Terakhir diperbarui:** 2026-06-26  
> **Diaudit dari:** Source code aktual + Container runtime + Database schema  
> **Status Sistem:** PRODUCTION RUNNING

---

## PHASE 1 — Ringkasan Arsitektur Aktual

### Tujuan Sistem
Platform AIOps enterprise untuk monitoring, deteksi insiden, analisis RCA berbasis AI, manajemen fleet Windows client, dan komunikasi real-time antara operator NOC dengan client melalui chat terintegrasi.

### Stack Teknologi Nyata
| Layer | Teknologi | Status |
|---|---|---|
| Reverse Proxy | nginx:1.25-alpine | ✅ Running |
| Dashboard Backend | Go / Gin Framework | ✅ Running |
| Ingestion Server | Go / net/http | ✅ Running |
| AI Core | Python 3.10 / asyncio + NATS | ✅ Running |
| Message Bus | NATS JetStream 2.9 | ✅ Running |
| Database | PostgreSQL 15 | ✅ Running (healthy) |
| Cache | Redis 7 | ✅ Running (healthy) |
| Notification | Telegram Bot (Go) | ✅ Running |
| Secure Relay | Go binary | ✅ Running |
| Container Management | Portainer CE 2.39.4 | ✅ Running (BARU) |
| Client Agent | Go binary (Windows) | ✅ Deployed |
| Client UI | C# WinForms (ChatForm) | ✅ Deployed |

---

## PHASE 2 — Audit Docker (10 Container Aktif)

| Container | Image | Port Host | Network |
|---|---|---|---|
| osi-nginx | nginx:1.25-alpine | 8099→80, 9443→443 | frontend+backend |
| osi-dashboard-server | incident-analysis-dashboard-server | (internal 9999) | frontend+backend |
| osi-ingestion-server | incident-analysis-ingestion-server | 18800, 18802 | backend |
| osi-postgres | postgres:15-alpine | 127.0.0.1:5433→5432 | backend |
| osi-redis | redis:7-alpine | (internal 6379) | backend |
| osi-nats | nats:2.9-alpine | (internal 4222,6222,8222) | backend |
| osi-python-ai-core | incident-analysis-python-ai-core | — | backend |
| osi-secure-relay | incident-analysis-secure-relay | 9998 | backend |
| osi-telegram-bot | incident-analysis-telegram-bot-listener | — | backend |
| osi-portainer | portainer/portainer-ce:latest | 9000, 9444→9443 | frontend+backend |

**Volumes:** postgres_data, redis_data, nats_data, portainer_data  
**Networks:** osi-frontend (bridge), osi-backend (bridge)

---

## PHASE 3 — Database PostgreSQL (45 Tabel)

### Tabel Core
| Tabel | Fungsi |
|---|---|
| incidents | Insiden dari telemetry (Python legacy) |
| fleet_incidents | Insiden dari Go agent baru |
| devices | Registry perangkat real-time |
| fleet_devices | Extended device info |
| fleet_sites | Lokasi/site manajemen |
| telemetry_logs | Partitioned by month |
| telemetry_logs_y2026m05..09 | Partisi bulanan |

### Tabel AI & Analytics
ai_audit_trail, ai_metrics, ai_confidence_calibration, ai_reflection_logs, ai_evidence_logs, ai_approval_logs, ai_blast_radius_logs, golden_resolutions, golden_solutions, knowledge_vectors, rag_historical_logs

### Tabel Fleet & Monitoring
fleet_networks, fleet_printers, fleet_processes, fleet_services, fleet_usbs, fleet_evidence, health_scores, cmdb_assets

### Tabel Chat & Komunikasi
chat_sessions, chat_messages, chat_feedback

### Tabel Governance & Security
governance_approvals, rbac_policies, immutable_audit_log, system_audits, incident_post_mortems, incident_states, incident_acknowledgements, incident_feedback, pending_remediations, remote_sessions, dlq_hybrid, config_versions, telegram_chat_mappings, operator_presence

---

## PHASE 3 — Dashboard Feature Inventory (17 Menu)

### MONITORING GROUP
| Menu | Panel ID | API Utama | Status |
|---|---|---|---|
| Overview | overview | /api/incidents, /api/devices, /api/system_status, /api/kpi_metrics | ✅ |
| Monitoring Live | monitoring | /api/devices, /ws/logs | ✅ |
| Activity & Issues | activity | /api/incidents, /activity | ✅ |
| Server Health | server | /api/system/health, /api/host_metrics, /api/system/audits | ✅ |

### INCIDENT GROUP
| Menu | Panel ID | API Utama | Status |
|---|---|---|---|
| Incident Triage | incident | /api/incidents, /api/incident/resolve, /api/incident/escalate | ✅ |
| Ground Truth & RCA | rca | /api/rca/analyze/:id, /api/feedback, /api/advanced_rca | ✅ |
| Causal DAG | dag | /api/causal_dag/:incident_id | ✅ |

### INFRASTRUCTURE GROUP
| Menu | Panel ID | API Utama | Status |
|---|---|---|---|
| PC Health | pchealth | /api/devices, /api/agent_deep_diagnostics/:agent_name | ✅ |
| Printer Status | printer | /api/printers/live, /api/printers/ping/:id | ✅ |
| Fleet Management | fleet | /api/fleet/admin/devices, /api/fleet/admin/sites | ✅ |
| Storage | storage | /api/storage/stats | ✅ |

### AI & LOGS GROUP
| Menu | Panel ID | API Utama | Status |
|---|---|---|---|
| AI Panel | ai | /api/ai_status, /api/ai_config, /api/system_audit/rag | ✅ |
| Training Feedback | training | /api/feedback/stats, /api/feedback | ✅ |
| Live Logs | logs | /ws/logs (WebSocket) | ✅ |
| Live Chat | (modal) | /ws/chat, /api/chat/* | ✅ |

### CONFIGURATION GROUP
| Menu | Panel ID | API Utama | Status |
|---|---|---|---|
| Governance | gov | /api/governance/*, /api/observability/* | ✅ |
| SOP Lifecycle | sop | /api/governance/sops* | ✅ |
| Model Config | models | /api/ai_config, /api/remote/settings | ✅ |

---

## PHASE 4 — Feature Mapping Blueprint v7 vs Implementasi

| Fitur Blueprint v7 | Status |
|---|---|
| NATS JetStream Event Bus | ✅ Sesuai |
| Go Ingestion + Dashboard Server | ✅ Sesuai |
| Python AI Supervisor (NATS) | ✅ Sesuai |
| RAG Engine (knowledge_vectors) | 🟡 Sebagian — tabel ada, data kosong |
| LLM Cost Optimizer | 🟡 Sebagian — code ada, Gemini key belum di-set |
| Policy Engine | ✅ Sesuai |
| Telegram Notification | ✅ Sesuai |
| RBAC / Governance | 🟡 Sebagian — tabel ada, enforcement belum penuh |
| AI Audit Trail | ✅ Sesuai |
| Fleet Management | ✅ Sesuai |
| RCA Analysis | ✅ Sesuai (fleet_incidents fallback BARU) |
| Chat Real-time (WhatsApp style) | ✅ Sesuai (BARU) |
| Deep Diagnostics (HMAC auth) | ✅ Sesuai (BARU) |
| Remote Access (Rustdesk/VNC) | 🟡 Sebagian |
| Portainer Integration | 🔵 BARU — belum di Blueprint |
| Istio / Service Mesh | 🟠 Belum diimplementasi |
| Digital Twin Graph DB | 🟠 Belum diimplementasi |
| ClickHouse Telemetry | 🔴 Deprecated — diganti PostgreSQL partitioned |
| P2P Swarm | 🔴 Deprecated — tidak pernah diimplementasi |
| AI Simulation Sandbox | 🟠 Belum — Blueprint v7 vision |
| Prediction/Security Agent | 🟠 Belum — Blueprint v7 vision |
| Model Registry / Feature Store | 🟠 Belum — Blueprint v7 vision |

---

## PHASE 5 — Implementasi Baru (Belum Terdokumentasi)

| Fitur | Lokasi |
|---|---|
| Portainer CE 2.39.4 | docker-compose.yml:220 |
| HMAC Command Auth (6 commands) | dashboard_server.go:424-441 |
| RCA Fleet Fallback | dashboard_server.go:4535 |
| WhatsApp-style Chat UI (C#) | ChatForm.cs |
| Python NATS_URL env fix | ai_supervisor.py:12 |
| Telemetry partitioned tables | PostgreSQL schema |
| Agent HMAC security key | main.go (Windows agent) |

---

## PHASE 6 — Deprecated Components

| Komponen | Alasan |
|---|---|
| ClickHouse | Diganti PostgreSQL partitioned |
| P2P Swarm | Tidak pernah diimplementasi |
| Agent05-Client device | Device offline dihapus |
| Python legacy agent | Diganti Go agent |

---

## PHASE 7 — Arsitektur Aktual

```
WINDOWS CLIENT
  Go Agent :10000 (TCP+HMAC) + ChatForm.cs
       │
       ▼
  nginx:9443 (TLS) → dashboard-server:9999 (Gin/Go)
                    → ingestion-server:18800 (net/http)
                       │
                    PostgreSQL + Redis + NATS
                       │
                    Python AI Core
                    (NATS subscriber → LLM → Policy)
                       │
                    Telegram Bot (notification)
  
  Portainer CE:9000 (Docker management)
```

---

## PHASE 8 — API Inventory (76 Endpoints)

### Auth
- POST /api/auth/login
- GET /api/auth/verify

### Devices & Monitoring
- GET /api/devices
- GET /api/agent_deep_diagnostics/:agent_name
- GET /api/host_metrics
- GET /api/system_status
- GET /api/kpi_metrics

### Incidents
- GET /api/incidents
- POST /api/incident/resolve
- POST /api/incident/escalate
- GET /api/rca/analyze/:incident_id
- GET /api/causal_dag/:incident_id
- GET /api/advanced_rca
- GET /api/offline/diagnose

### Fleet Admin
- GET/POST /api/fleet/admin/devices
- POST /api/fleet/admin/devices/approve
- POST /api/fleet/admin/devices/save
- DELETE /api/fleet/admin/devices/delete/:pc_name
- GET/POST /api/fleet/admin/sites
- GET/POST /api/fleet/admin/printers
- GET /api/fleet/admin/topology
- POST /api/fleet/admin/bitlocker/backup/:agent_name
- POST /api/fleet/admin/defender/:agent_name
- POST /api/fleet/admin/powershell/:agent_name
- POST /api/fleet/admin/schtask/:agent_name

### Printers
- GET /api/printers/live
- POST /api/printers/ping/:id
- POST /api/printers/ping_all
- POST /api/printers/update_metrics
- PUT/DELETE /api/printers/:id

### AI & Config
- GET/POST /api/ai_config
- GET /api/ai_status
- GET /api/ai/stats
- POST /api/ai_command
- GET /api/feedback/stats
- POST /api/feedback
- GET /api/system/audits
- GET /api/system/health
- GET /api/system/queues
- GET /api/system_audit/rag
- GET /api/system_audit/drift
- POST /api/system_audit/retrain_classifier
- GET /api/system_audit/ai_observability

### Governance
- GET /api/governance/sops
- POST /api/governance/sops/create
- POST /api/governance/sops/delete
- POST /api/governance/sops/promote
- GET /api/governance/sla_compliance
- GET /api/governance/top_resolutions
- GET /api/governance/recovery_mode

### Observability
- GET /api/observability/dependency_map
- GET /api/observability/slo
- GET /api/observability/trace
- GET /api/observability/capacity_forecast

### Remote Access
- GET /api/remote/settings
- POST /api/remote/settings/save
- GET /api/remote/detect
- POST /api/remote/test/:tool
- POST /api/remote/launch/:tool
- POST /api/remote/launch
- POST /api/orchestrator/command

### Chat
- GET /ws/chat (WebSocket)
- GET /api/chat/sessions
- POST /api/chat/sessions/:client_id/status
- GET /api/chat/history/:client_id
- GET /api/chat/device_context/:client_id
- GET /api/chat/suggest

### Storage & Misc
- GET /api/storage/stats
- GET /api/server/logs
- GET /api/ping_sites
- GET /ws/logs (WebSocket)
- POST /api/launcher/start
- GET /api/launcher/status

---

## PHASE 9 — Gap Analysis

| Domain | Coverage |
|---|---|
| Docker Implementation | 100% ✅ |
| Dashboard UI | 100% ✅ |
| API Implementation | 95% ✅ |
| Database Schema | 100% ✅ |
| Agent (Windows Client) | 90% ✅ |
| Blueprint Documentation | 85% 🟡 |
| Security (HMAC, RBAC) | 75% 🟡 |
| Monitoring | 80% 🟡 |
| AI Pipeline | 60% 🟡 |

---

## PHASE 10 — Rekomendasi

### 🔴 Critical
1. Set `GEMINI_API_KEY` di `.env` — AI Core tidak bisa inference tanpanya
2. Isi `knowledge_vectors` — RAG tidak efektif tanpa data

### 🟠 High
3. Retry logic Telegram Bot — sesekali DNS error
4. Buka port 10000 di Windows Firewall — Deep Diagnostics
5. Buat script auto-create partisi telemetry tahunan

### 🟡 Medium
6. Enforce RBAC per menu di UI
7. Implementasi Model Registry table
8. Batasi akses Portainer dengan firewall (LAN only)

### 🟢 Low
9. Roadmap v9: Prediction Agent, Security Agent, Simulation Sandbox
10. Istio / Service Mesh saat microservices bertambah > 15
