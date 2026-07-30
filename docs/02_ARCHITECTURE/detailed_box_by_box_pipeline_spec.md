# 📖 Spesifikasi Detail Kotak-demi-Kotak (Box-by-Box Internal Pipeline Mechanics)

**Sistem**: NOC IT AI Command Center v3.0 (OSI Infrastructure)  
**Dokumen**: Deep-Dive Mechanics, Code Mapping, Input/Output JSON Schemas & Resiliency for Every Flowchart Node  
**Tanggal Audit**: 22 Juli 2026  

---

## 📄 Ringkasan Eksekutif

Dokumen ini merupakan panduan pendamping tingkat lanjut untuk diagram flowchart **End-to-End Agent Telemetry Pipeline**. Dokumen ini mengupas **mekanisme internal di dalam setiap kotak (node/box)** pada diagram, mencakup lokasi file kode sumber (*source code mapping*), kontainer pembawa, algoritma pemrosesan, skema input-output data, serta proteksi kegagalan (*error-handling & resiliency*).

---

## 🟢 STAGE 1: AGENT TELEMETRY GENERATION (Windows & Linux Fleet)

### 1.1 `W_AGENT` — Windows Fleet Agent
- **Kontainer / Process**: Agent Binary `osi-agent-windows.exe` di peranti Windows target.
- **Lokasi Kode**: `SERVER/agent/windows/main.go` & `portal/dashboard/fleet/`
- **Mekanisme Internal**:
  1. **Service Sampler Loop**: Menguji status Windows Service (`Winmgmt`, `Spooler`, `W3SVC`, `MSSQLSERVER`) setiap 5 detik.
  2. **EventLog Harvester**: Membaca Windows Event Log (*System & Application*) dengan ID 7034 (Service Crash), 1000 (App Error), 5156 (Firewall Block).
  3. **Metric Collector**: Mengambil utilisasi CPU (WMI/Win32_Processor), RAM (GlobalMemoryStatusEx), dan Disk I/O.
- **Input Data**: Telemetri mentah OS Windows & WMI Queries.
- **Output Data (JSON Payload)**:
  ```json
  {
    "agent_id": "PC-MKT-NUC",
    "os_type": "windows",
    "timestamp": "2026-07-22T11:45:00Z",
    "metrics": { "cpu_pct": 98.4, "ram_pct": 91.2, "disk_pct": 84.0 },
    "services": { "winmgmt": "DEADLOCK", "spooler": "RUNNING" },
    "event_logs": [{ "event_id": 7034, "source": "Service Control Manager", "message": "Winmgmt terminated unexpectedly." }]
  }
  ```
- **Proteksi Kegagalan**: Memiliki lokal buffer SQLite jika koneksi NATS terputus (*offline queue* maks 10.000 log).

---

### 1.2 `L_AGENT` — Linux Fleet Agent
- **Kontainer / Process**: Daemon Binary `osi-agent-linux` di peranti Linux target.
- **Lokasi Kode**: `SERVER/agent/linux/main.go` & `portal/dashboard/fleet/`
- **Mekanisme Internal**:
  1. **Systemd Monitor**: Membaca status unit systemd via DBus API (`systemctl status`).
  2. **Procfs Reader**: Membaca `/proc/stat`, `/proc/meminfo`, `/proc/net/dev` tanpa membuat overhead CPU.
  3. **Syslog Streamer**: Menangkap log `/var/log/syslog` dan `/var/log/auth.log` secara real-time.
- **Input Data**: Kernel `/proc` filesystem & Systemd DBus.
- **Output Data (JSON Payload)**:
  ```json
  {
    "agent_id": "LINUX-it-mkt-NUC12WSH-B",
    "os_type": "linux",
    "timestamp": "2026-07-22T11:45:00Z",
    "metrics": { "cpu_pct": 14.2, "ram_pct": 48.5, "disk_pct": 52.1 },
    "services": { "nginx": "active", "postgresql": "active" }
  }
  ```
- **Proteksi Kegagalan**: Auto-restart via Systemd service recovery (`Restart=always`, `RestartSec=3s`).

---

### 1.3 `NET_AGENT` — SNMP / Netdata / Syslog Harvester
- **Kontainer / Process**: Container `netdata_master` & Syslog Receiver Daemon.
- **Lokasi Kode**: `portal/dashboard/metrics/metrics.go`
- **Mekanisme Internal**:
  1. Poll SNMP OID (`.1.3.6.1.2.1.2.2.1`) dari Cisco/Nexus Switch setiap 10 detik.
  2. Menerima Syslog UDP port 514 dari Network Appliances.
- **Output Data**: Standardized Metric Telemetry Payload ke NATS Broker.

---

### 1.4 `NATS_IN` — NATS Ingestion Bus (`telemetry.ingest`)
- **Kontainer**: `osi-nats` (`nats:4222`)
- **Lokasi Kode**: `portal/router/router.go` & NATS Config
- **Mekanisme Internal**:
  1. Menerima pub/sub message dari puluhan ribu agen pada subject `telemetry.ingest`.
  2. Mengalirkan payload dengan latensi *sub-millisecond* (< 1.0 ms).
- **Input Data**: Raw Agent JSON Payloads.
- **Output Data**: High-throughput Ingestion Stream.

---

## 🟡 STAGE 2: INGESTION, NORMALIZATION & DEDUPLICATION

### 2.1 `ING_BRIDGE` — Ingestion Bridge (`osi-ingestion-server`)
- **Kontainer**: `osi-ingestion-server` (Go Microservice)
- **Lokasi Kode**: `portal/dashboard/incident/incident.go`
- **Mekanisme Internal**:
  1. Validasi Token Otentikasi Agen (`Bearer API_TOKEN`) terhadap tabel `rbac_users`.
  2. Enforce Rate Limiter (maks 500 req/sec per IP) untuk mencegah DoS.
- **Input Data**: Payload NATS `telemetry.ingest`.
- **Output Data**: Authenticated & Sanitized Telemetry Struct.

---

### 2.2 `DEDUP` — Event Normalizer Engine (Time-Window Deduplication)
- **Kontainer**: `osi-ingestion-server`
- **Lokasi Kode**: `portal/dashboard/incident/incident.go` (Fungsi `NormalizeAndDeduplicate`)
- **Mekanisme Internal**:
  1. Menggunakan Slide Window Hash Table (60 detik) berdasarkan `(device_name, error_code, service_name)`.
  2. Jika insiden serupa diterima dalam window 60 detik, **tambahkan event count counter (+1)** alih-alih membuat baris baru.
  3. Mengelompokkan 500+ log berulang menjadi 1 Master Anomaly Event.
- **Input Data**: Sanitized Telemetry Struct.
- **Output Data**: Aggregated Master Anomaly Struct (`Grouped Count: N`).

---

### 2.3 `PG_RAW` — PostgreSQL Data Persistence
- **Kontainer**: `osi-postgres` (Database: `osi_system`)
- **Tabel Terkait**: `incidents`, `telemetry_logs`, `devices`
- **Mekanisme Internal**:
  1. Menyimpan Master Anomaly Event ke tabel `incidents` dengan status awal `OPEN`.
  2. Meng-update kolom `last_seen` dan `status` pada tabel `devices`.

---

### 2.4 `NATS_INC` — NATS Anomaly Publisher (`agent.incident`)
- **Kontainer**: `osi-nats`
- **Subject**: `agent.incident`
- **Mekanisme Internal**: Mempublikasikan pesan anomali ter-deduplikasi ke NATS Subject `agent.incident` untuk memicu analisis AI.

---

## 🔵 STAGE 3: AI COGNITIVE REASONING & CONSENSUS CLUSTER

### 3.1 `AI_CORE` — AI Cognitive Controller
- **Kontainer**: `osi-python-ai-core` (Python FastAPI Engine)
- **Lokasi Kode**: `SERVER/ai_core/cognitive_engine.py` & `portal/chat_engine.go`
- **Mekanisme Internal**:
  1. Menerima anomali dari `agent.incident`.
  2. Memulai pipeline penalaran multithreaded (RAG Search, Knowledge Graph Lookup, Critic Check).

---

### 3.2 `AI_RAG` — Vector SOP RAG Engine
- **Kontainer**: `osi-ai-rag` (Vector Store Engine)
- **Dokumen Referensi**: `KB-SOP-001`, `KB-SOP-002`, `KB-SOP-003`
- **Mekanisme Internal**:
  1. Mengonversi teks error insiden menjadi Vector Embedding.
  2. Melakukan Similarity Search (Cosine Distance) terhadap database SOP terdaftar.
  3. Mengembalikan Top-3 SOP remediasi terbaik.

---

### 3.3 `KG_GRAPH` — Knowledge Graph Engine
- **Kontainer**: `osi-dashboard-server` (Go Engine)
- **Lokasi Kode**: `portal/cognitive_memory_api.go` & `/api/knowledge_graph`
- **Mekanisme Internal**:
  1. Membaca tabel `dependency_map` & `devices`.
  2. Mengkalkulasi alur ketergantungan *upstream/downstream* (misal: `App-Web-01` → `DB-Prod-01` → `Core Switch`).
  3. Menentukan node mana yang merupakan **Akar Masalah Utama (Root Cause Node)**.

---

### 3.4 `AI_CRITIC` — AI Critic & Policy Enforcer
- **Kontainer**: `osi-ai-critic` & `osi-ai-policy`
- **Mekanisme Internal**:
  1. Memverifikasi keluaran LLM terhadap skema JSON terstruktur (*Validation Pass Rate 99.2%*).
  2. Memastikan perintah remediasi yang direkomendasikan tidak melanggar aturan keamanan (misal: melarang `rm -rf /` atau `DROP DATABASE`).

---

### 3.5 `RCA_ENGINE` — RCA 5-Why & Confidence Calibration Engine
- **Kontainer**: `osi-python-ai-core`
- **Mekanisme Internal**:
  1. Menyusun analisis 5-Why (Mengapa CPU tinggi? → Karena service Winmgmt deadlock → Mengapa deadlock? → Karena antrean spooler penuh).
  2. Mengkalkulasi skor confidence akhir (0.0% – 100.0%) dari gabungan RAG score, Graph distance, dan Critic pass.

---

## 🔴 STAGE 4: DECISION ROUTING & HUMAN-IN-THE-LOOP (HITL) GATE

### 4.1 `RISK_DECISION` — Evaluator Risiko & Confidence
- **Mekanisme Internal**:
  - IF `Confidence >= 85%` AND `RiskLevel == LOW` (cth: restart spooler / disk cleanup) → **Rute ke `AUTO_EXEC`**.
  - IF `Confidence < 85%` OR `RiskLevel == HIGH` (cth: restart database / modify route) → **Rute ke `HITL_QUEUE`**.

---

### 4.2 `AUTO_EXEC` — Auto-Approve Remediation Dispatcher
- **Mekanisme Internal**: Membuat rekam jejak persetujuan otomatis di `ai_reflection_logs` dan mendispatch perintah langsung ke Command Relay.

---

### 4.3 `HITL_QUEUE` — Approval Queue (HITL Gate)
- **Kontainer**: `osi-postgres` & `osi-dashboard-server`
- **Tabel Terkait**: `ai_approval_logs`
- **Mekanisme Internal**:
  1. Mengunci tindakan remediasi dalam status `PENDING_APPROVAL_ID_XXX`.
  2. Menampilkan kartu persetujuan pada menu **Approval Queue** di dashboard.

---

### 4.4 `MANUAL_APPROVE` / `OPERATOR_REJECT` — Response Handler
- **Mekanisme Internal**:
  - Jika Operator menekan **Approve** → Ubah status menjadi `APPROVED` dan kirim perintah ke Command Relay.
  - Jika Operator menekan **Reject** → Ubah status menjadi `REJECTED`, simpan alasan penolakan ke memori AI (*operator feedback learning*), dan batalkan eksekusi.

---

## 🟣 STAGE 5: COMMAND RELAY EXECUTION & STATE VERIFICATION

### 5.1 `SECURE_RELAY` — Encrypted Command Relay
- **Kontainer**: `osi-secure-relay`
- **Mekanisme Internal**:
  1. Mengenkripsi payload perintah remediasi dengan kunci AES-256.
  2. Pengiriman via NATS / SSH / WinRM ke agen di perangkat target.

---

### 5.2 `TARGET_AGENT` — Perangkat Target (Windows / Linux)
- **Mekanisme Internal**: Agen mengeksekusi skrip remediasi (cth: `net stop winmgmt && net start winmgmt` atau `systemctl restart nginx`).

---

### 5.3 `VERIFY_AGENT` & `VERIFY_CHECK` — State Verifier & Health Check
- **Subject NATS**: `agent.verify`
- **Mekanisme Internal**:
  1. Menunggu 5 detik pasca-eksekusi.
  2. Menguji parameter kesehatan: `service_alive` (True/False), `port_open` (True/False), `response_latency_ms` (< 500ms), `cpu_normalized` (True/False).

---

### 5.4 `LEARNING_GATE` — Ingest to Learning Gate & SOP Update
- **Tabel Terkait**: `learning_gate_logs`
- **Mekanisme Internal**: Jika verifikasi **PASS**, catat insiden sebagai sukses dan tingkatkan bobot rekomendasi SOP di Vector RAG DB.

---

### 5.5 `ROLLBACK_ENGINE` — State Machine Rollback Triggered
- **Tabel Terkait**: `rollback_logs`
- **Mekanisme Internal**: Jika verifikasi **FAIL**, pemicu state machine otomatis mengeksekusi *rollback command* (misal: mengembalikan tabel routing backup) dan mencatat log kegagalan ke DLQ.

---

## 🔵 STAGE 6: MULTI-CHANNEL PRESENTATION & BROADCAST

### 6.1 `DASH_SERVER` — Dashboard Server Engine
- **Kontainer**: `osi-dashboard-server` (Go Engine)
- **Mekanisme Internal**: Menarik data ter-enrich dari PostgreSQL & NATS Bus, lalu mengonversi data menjadi JSON presentasi terstruktur.

---

### 6.2 `WS_BROADCAST` — WebSocket Real-Time Broadcaster
- **Endpoint**: `/ws/logs` & `/ws/operator_chat`
- **Mekanisme Internal**: Mendorong data insiden terstruktur ke seluruh browser klien terhubung secara real-time tanpa polling.

---

### 6.3 `TELEGRAM_BOT` — Telegram Notification Bot
- **Kontainer**: `osi-telegram-bot`
- **Mekanisme Internal**: Mengirimkan notifikasi ringkas Bahasa Indonesia ke grup Telegram Operator NOC jika terjadi insiden `CRITICAL`.

---

### 6.4 `UI_SMART` — Smart Incident Stream UI (`/smart_stream`)
- **Lokasi**: [portal/templates/index.html](file:///home/it-itsm/AI/incident-analysis/portal/templates/index.html#L7055) (`#p-smart_stream`)
- **Mekanisme Tampilan**:
  - Merender **Kartu Insiden Bahasa Manusia** yang mencakup: Nama Perangkat (Status Online/Offline), Ringkasan Insiden, Sebab Masalah, Rekomendasi AI, Confidence %, dan Tombol Aksi 1-Klik (*RCA 5-Why*, *Knowledge Graph*, *Approve HITL*).
