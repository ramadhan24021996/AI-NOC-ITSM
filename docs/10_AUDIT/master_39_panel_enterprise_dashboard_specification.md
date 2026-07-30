# 🏛️ Master Spesifikasi Arsitektur 39 Panel Dashboard NOC IT AI Command Center v3.0

**Sistem**: NOC IT AI Command Center v3.0 (OSI Enterprise Infrastructure)  
**Dokumen**: Complete 39-Panel Enterprise Solution Architecture Specification  
**Tingkat Detail**: 8-Level Architecture & Source Code Mapping Specification  
**Status Implementasi**: Grounded on Actual Codebase & Verified Schema (Zero Mock / Zero Simulation)  
**Tanggal**: 22 Juli 2026  

---

# LEVEL 1: Overall Dashboard Architecture

### 1.1 Tujuan & Konsep Dashboard
Dashboard **NOC IT AI Command Center v3.0** dirancang sebagai pusat kendali otonom (*Autonomous Operations Center*) yang mengintegrasikan pengamatan infrastruktur (*Observability*), deteksi anomali real-time, analisis akar masalah berbasis AI (*RCA 5-Why*), dan eksekusi remediasi otomatis dengan pengawasan manusia (*Human-in-the-Loop*).

### 1.2 User Journey & Role Workflows
* **NOC Operator Workflow**: 
  1. Memantau aliran insiden terstruktur pada **Smart Incident Stream** (`/smart_stream`) dan **Overview** (`/overview`).
  2. Apabila terjadi insiden berisiko tinggi, meninjau akar masalah pada **RCA Studio** (`/rca`) dan **Knowledge Graph** (`/kgraph`).
  3. Menyetujui atau menolak aksi remediasi pada **Approval Queue** (`/approval_queue`).
* **AI Workflow (Autonomous Pipeline)**:
  1. Menerima telemetri mentah via NATS `telemetry.ingest` $\rightarrow$ Normalisasi & Deduplikasi.
  2. Eksekusi Vector RAG Search (`/api/v1/vector/search`) & Traversal Knowledge Graph (`/api/knowledge_graph`).
  3. Memformulasi hipotesis RCA 5-Why & mengkalkulasi skor confidence terkalibrasi.
  4. Mengevaluasi ambang batas keamanan via **AI Critic** (`/api/v1/critic/verify`). Jika aman $\rightarrow$ auto-dispatch; jika berisiko $\rightarrow$ tahan di HITL Gate.
  5. Memverifikasi hasil pasca-eksekusi via `agent.verify`. Jika gagal $\rightarrow$ trigger **Rollback Engine**.
* **Backend Workflow (Go Dashboard Server & Ingestion)**:
  - Mengelola HTTP REST endpoints, WebSocket hubs (`/ws/logs`, `/ws/operator_chat`), NATS subscriptions, dan transaksi database PostgreSQL (`osi_system`).
* **Frontend Workflow (Single Page Application)**:
  - Mengelola 39 panel independen berbasis Vanilla HTML5/JS/CSS3, penanganan peristiwa WebSocket, penyaringan pencarian real-time, dan perenderan kartu visual tanpa pustaka pihak ketiga yang membebani browser.

### 1.3 High-Level System Architecture Diagram

```mermaid
flowchart TD
    subgraph SG_Fleet ["Edge Fleet Agents (Windows & Linux Target)"]
        WinAgent["Windows Fleet Agent (osi-agent-windows.exe)"]
        LinuxAgent["Linux Fleet Agent (osi-agent-linux)"]
        NetdataHarvester["Netdata / SNMP Network Harvester"]
    end

    subgraph SG_Ingest ["Ingestion & Messaging Layer"]
        IngestBridge["osi-ingestion-server (Go:8080)"]
        NatsBroker["osi-nats (NATS PubSub Broker:4222)"]
        EventDedup["Event Normalizer & Deduplication Engine"]
    end

    subgraph SG_Core ["Dashboard Monolith & WS Hub"]
        DashServer["osi-dashboard-server (Go Monolith:8080)"]
        WSHub["WebSocket Broadcaster Hub (/ws/logs)"]
        RBACEngine["RBAC Policy Enforcer"]
    end

    subgraph SG_AICore ["AI Cognitive Engine Cluster"]
        AICore["osi-python-ai-core (FastAPI:5000)"]
        AIRag["osi-ai-rag Vector Store Engine (:5001)"]
        AICritic["osi-ai-critic Guardrail Engine (:5002)"]
        KGraphEngine["Knowledge Graph Engine (/api/knowledge_graph)"]
    end

    subgraph SG_Storage ["Persistence & Cache Layer"]
        PostgresDB[("PostgreSQL Database: osi_system (:5422)")]
        RedisCache[("Redis Cache & Session Queue (:6379)")]
    end

    subgraph SG_Execution ["Action Execution & Verification"]
        SecureRelay["osi-secure-relay (Encrypted Relay:8081)"]
        StateVerifier["State Verifier Engine (agent.verify)"]
        RollbackEngine["Automated Rollback Engine"]
    end

    subgraph SG_Presentation ["39 Panel Presentation Layer (Browser UI)"]
        UI_Overview["Overview & Monitoring Category"]
        UI_Fleet["Fleet & Health Category"]
        UI_Incident["Incident & RCA Category"]
        UI_Ops["Operations & Approvals Category"]
        UI_AICenter["AI Engine Center Category"]
        UI_Gov["Security & Governance Category"]
        UI_Diag["Diagnostics & Comm Category (Smart Stream)"]
    end

    WinAgent & LinuxAgent & NetdataHarvester -->|NATS / HTTP| IngestBridge
    IngestBridge -->|Publish telemetry.ingest| NatsBroker
    NatsBroker -->|Consume| EventDedup
    EventDedup -->|Insert Incidents| PostgresDB
    EventDedup -->|Publish agent.incident| NATSBroker

    NatsBroker -->|Subscribe| DashServer
    DashServer <-->|SQL Queries| PostgresDB
    DashServer <-->|Session Cache| RedisCache
    DashServer -->|Broadcast Events| WSHub

    DashServer <-->|HTTP REST /api/v1/ai| AICore
    AICore <-->|Similarity Search| AIRag
    AICore <-->|Safety Verification| AICritic
    AICore <-->|Topology Traversal| KGraphEngine

    DashServer -->|Dispatch Command| SecureRelay
    SecureRelay -->|Encrypted Execution| WinAgent & LinuxAgent
    WinAgent & LinuxAgent -->|Post-Telemetry| StateVerifier
    StateVerifier -->|Verification Pass| PostgresDB
    StateVerifier -->|Verification Fail| RollbackEngine
    RollbackEngine -->|Restore State| SecureRelay

    WSHub -->|WebSocket Frame Stream| UI_Overview & UI_Fleet & UI_Incident & UI_Ops & UI_AICenter & UI_Gov & UI_Diag
```

---

### 1.4 Arsitektur Kontribusi 3 LLM Multi-Agent Consensus Engine (Flow & Explanations)

Sistem mengadopsi pola konsensus 3 LLM (*3-LLM Multi-Agent Consensus Architecture*) yang membagi peran penalaran menjadi 3 agen kecerdasan buatan terpisah untuk menjamin transparansi, pencegahan halusinasi, dan keandalan keputusan otonom:

```mermaid
flowchart TD
    subgraph SG_LLM1 ["LLM 1: Primary Reasoning & Hypothesis Engine (Analyst LLM)"]
        LLM1_In["Input: Anomaly Event + Vector SOP Context"] --> LLM1_Proc["Analisis Telemetri & Generasi 5-Why RCA"]
        LLM1_Proc --> LLM1_Out["Output: First Hypothesis & Draf Playbook Action"]
    end

    subgraph SG_LLM2 ["LLM 2: Multi-Agent Consensus Engine (osi-ai-consensus)"]
        LLM1_Out --> LLM2_In["Input: First Hypothesis + Knowledge Graph Topology"]
        LLM2_In --> LLM2_Debate["Cross-Evaluation & Weighted Confidence Scoring"]
        LLM2_Debate --> LLM2_Out["Output: Consensus Decision & Second Hypothesis"]
    end

    subgraph SG_LLM3 ["LLM 3: Safety Critic & Policy Enforcer (osi-ai-critic)"]
        LLM2_Out --> LLM3_In["Input: Consensus Decision + Security Policy Blacklist"]
        LLM3_In --> LLM3_Verify["Syntax Schema Inspection & Command Blacklist Scan"]
        LLM3_Verify --> LLM3_Out["Output: Verified Action Plan (PASS / FAIL Stamp)"]
    end

    LLM3_Out --> FinalRoute{"Routing Decision Gate"}
    FinalRoute -->|Pass & Conf >= 85%| AutoExec["Auto Remediation Dispatch"]
    FinalRoute -->|High Risk / Conf < 85%| HITLGate["Approval Queue (HITL Gate)"]
```

#### 📊 Peran & Kontribusi Rinci 3 LLM:

1. **LLM 1 — Primary Analyst & Hypothesis Generator (`osi-python-ai-core`)**:
   - **Fungsi**: Bertindak sebagai *First Responder Analyst*.
   - **Tugas**: Membaca data anomali mentah, mengonversinya menjadi vector embedding, mencari rekomendasi SOP di `osi-ai-rag` (`KB-SOP-001/002/003`), dan menyusun draf hipotesis awal (*First Hypothesis*).
   - **Data Input**: Telemetri NATS `agent.incident` + Vector SOP Documents.
   - **Data Output**: `first_hypothesis` string & draf tindakan remediasi.

2. **LLM 2 — Multi-Agent Consensus Evaluator (`osi-ai-consensus`)**:
   - **Fungsi**: Bertindak sebagai *Senior System Reviewer*.
   - **Tugas**: Menguji draf hipotesis dari LLM 1 terhadap data topologi dependensi Knowledge Graph (`/api/knowledge_graph`), mengkalkulasi skor confidence terkalibrasi $\text{Confidence} = (S_{\text{RAG}} \times 0.4) + (S_{\text{KG}} \times 0.4) + (S_{\text{Critic}} \times 0.2)$, dan menghasilkan *Second Hypothesis*.
   - **Data Input**: `first_hypothesis` + Knowledge Graph Node Traversal.
   - **Data Output**: `final_decision`, `second_hypothesis`, & `confidence_score` (cth: `95.8%`).

3. **LLM 3 — Safety Critic & Policy Enforcer (`osi-ai-critic` & `osi-ai-policy`)**:
   - **Fungsi**: Bertindak sebagai *Security & Safety Compliance Officer*.
   - **Tugas**: Mengevaluasi perintah dari LLM 2 terhadap tabel `security_policies` dan *command blacklist* (mencegah perintah destructive seperti `rm -rf /` atau `DROP DATABASE`).
   - **Data Input**: Proposed Action Command Struct + `security_policies` DB Rules.
   - **Data Output**: Validation Stamp (`status: PASS` / `status: FAIL`).

---

# LEVEL 2: Architecture Categorization Justification

### 2.1 Alasan Pembagian 7 Kategori Menu
Dashboard dibagi secara sistematis menjadi 7 kategori navigasi terisolasi untuk mengoptimalkan operasional tim IT/NOC:

1. **Dashboard & Overview (5 Panel)**: Menyajikan pandangan eksekutif makro (*High-Level Visibility*), utilisasi server, dan jejak aktivitas user.
2. **Fleet & Health (4 Panel)**: Berfokus pada inventaris fisik peranti (*Asset Management*), kesehatan PC, printer, dan penyimpanan disk.
3. **Incident & RCA (6 Panel)**: Pusat investigasi mendalam untuk isolasi masalah (*Triage*), pencarian 5-Why, dan grafik dependensi kausal (*Unified DAGs*).
4. **Operations & Approvals (4 Panel)**: Gerbang eksekusi dan mitigasi risiko yang memfasilitasi persetujuan manusia (*HITL Gate*), verifikasi pasca-aksi, audit rollback, dan DLQ error.
5. **AI Engine Center (7 Panel)**: Panel observabilitas internal mesin AI (metrik refleksi, timeline eksekusi pipeline, audit skema LLM, dan jejak pembelajaran).
6. **Security & Governance (7 Panel)**: Manajemen tata kelola keamanan, siklus hidup SOP, kebijakan Learning Gate, dan kebijakan hak akses RBAC.
7. **Diagnostics & Communication (4 Panel)**: Alat komunikasi real-time dan stream telemetry terstruktur (**Smart Incident Stream**, Live Logs, NATS Subjects, Live Chat Support).

### 2.2 Alur Perpindahan Data Antar Kategori

```mermaid
flowchart LR
    C7["Diagnostics & Comm\n(Smart Incident Stream)"] -->|Identifikasi Incident| C3["Incident & RCA\n(Triage & 5-Why RCA)"]
    C3 -->|Eskalasi High-Risk Action| C4["Operations & Approvals\n(Approval Queue HITL)"]
    C4 -->|Operator Approval| C5["AI Engine Center\n(Execution Timeline)"]
    C5 -->|Enforce Guardrails| C6["Security & Governance\n(Security Policies)"]
    C6 -->|Update Health Score| C2["Fleet & Health\n(PC Health)"]
    C2 -->|Refleksi Summary KPI| C1["Dashboard & Overview\n(Overview KPI)"]
```

---

# LEVEL 3: Inter-Panel Relationships by Category

### 3.1 Kategori 1: Dashboard & Overview
- `Overview` $\rightarrow$ `Monitoring Live` $\rightarrow$ `Server Health` $\rightarrow$ `Activity` $\rightarrow$ `Browser Logs`.
- *Hubungan*: Menghubungkan indikator KPI makro perusahaan dengan telemetri kesehatan server dan aktivitas pengguna browser secara real-time.

### 3.2 Kategori 2: Fleet & Health
- `PC Health` $\rightarrow$ `Printer Status` $\rightarrow$ `Fleet Management` $\rightarrow$ `Storage`.
- *Hubungan*: Memetakan status perangkat PC terdaftar (CPU/RAM/Services), status printer enterprise, lokasi site gateway fleet, serta kapasitas disk storage.

### 3.3 Kategori 3: Incident & RCA
- `Incident Triage` $\rightarrow$ `Ground Truth & RCA` $\rightarrow$ `5 Why Analysis` $\rightarrow$ `Causal Graph` $\rightarrow$ `Decision Graph` $\rightarrow$ `Evidence DAG`.
- *Hubungan*: Mengubah insiden mentah menjadi analisa 5-Why terverifikasi dan visualisasi grafis ketergantungan kausal (*Unified DAG*).

### 3.4 Kategori 4: Operations & Approvals
- `Approval Queue` $\rightarrow$ `Pending Verification` $\rightarrow$ `Rollback History` $\rightarrow$ `Failed Actions (DLQ)`.
- *Hubungan*: Mengelola antrean persetujuan manual HITL, verifikasi kesehatan pasca-tindakan, sejarah pengembalian state, dan log kegagalan eksekusi.

### 3.5 Kategori 5: AI Engine Center
- `AI Panel` $\rightarrow$ `Training Feedback` $\rightarrow$ `Execution Timeline` $\rightarrow$ `Event Correlation` $\rightarrow$ `AI Decision Logs` $\rightarrow$ `Schema Validation Logs` $\rightarrow$ `Learning Gate Audit`.
- *Hubungan*: Memberikan visibilitas 360 derajat terhadap kinerja model AI, latensi reasoning, validasi skema JSON, dan pembelajaran kontinu.

### 3.6 Kategori 6: Security & Governance
- `AI Governance Center` $\rightarrow$ `SOP Lifecycle` $\rightarrow$ `Model Config` $\rightarrow$ `Security Policies` $\rightarrow$ `Recovery Mode Config` $\rightarrow$ `Learning Gate Policy` $\rightarrow$ `RBAC Policies`.
- *Hubungan*: Mengatur aturan batas eksekusi AI, status draf/aktif SOP, konfigurasi mode pemulihan sistem, serta kebijakan otorisasi RBAC.

### 3.7 Kategori 7: Diagnostics & Communication
- `Smart Incident Stream` $\rightarrow$ `Live Logs` $\rightarrow$ `NATS Subjects Telemetry` $\rightarrow$ `Live Chat Support`.
- *Hubungan*: Menyalurkan stream insiden terstruktur bahasa manusia, pencarian log mentah server, throughput NATS bus, dan layanan live chat dukungan PC.

---

# LEVEL 4 & 5: Technical Specification for All 39 Panels

---

## Panel 1: Overview (`#p-overview`)

### 1. Spesifikasi Panel
* **Tujuan**: Menyajikan ringkasan eksekutif KPI insiden aktif, persentase keberhasilan AI, dan status kesehatan infrastruktur utama.
* **Fungsi**: Menampilkan widget statistik makro, grafik tren insiden, dan insiden kritis terbaru.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`, `viewer`.
* **Source Data**: PostgreSQL (`incidents`, `ai_reflection_logs`), Redis Cache, WebSocket `/ws/logs`.
* **Database & Query**:
  ```sql
  SELECT COUNT(*) FROM incidents WHERE status = 'OPEN';
  SELECT AVG(confidence_score) FROM ai_reflection_logs;
  ```
* **Frontend Component**: HTML Container `<div id="p-overview" class="panel active">`, JS Object `Panels.overview`.

### 2. Widget Metrics & Thresholds
| Nama Widget | Fungsi & Perhitungan | API / Endpoint | Refresh Rate | Threshold Warning | Threshold Critical | Warna / Icon |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **Total Active Incidents** | Count `incidents` WHERE status='OPEN' | `GET /api/v1/metrics/overview` | 5s (WS) | $> 10$ Insiden | $> 50$ Insiden | 🔴 Red (`bd-rd`) / `fa-triangle-exclamation` |
| **AI Auto-Heal Rate** | (Auto Resolved / Total Incidents) * 100 | `GET /api/v1/metrics/overview` | 10s | $< 80\%$ | $< 50\%$ | 🟢 Green (`bd-gr`) / `fa-robot` |
| **Avg Confidence Score**| AVG(`ai_reflection_logs.confidence_score`) | `GET /api/ai_decision_logs` | 10s | $< 85\%$ | $< 70\%$ | 🟣 Purple (`bd-bl`) / `fa-brain` |
| **Fleet Online Ratio** | (Online PCs / Total Registered Devices) | `GET /api/fleet/admin/devices` | 10s | $< 90\%$ | $< 75\%$ | 🔵 Blue (`bd-bl`) / `fa-desktop` |

### 3. Diagram Internal Panel Overview

```mermaid
flowchart TD
    Start([Buka Panel Overview]) --> FetchMetrics["Fetch REST API /api/v1/metrics/overview"]
    FetchMetrics --> UpdateKPIs["Update Widget Active Incidents, Auto-Heal, & Confidence"]
    UpdateKPIs --> ListenWS["Listen WebSocket /ws/logs Event Stream"]
    ListenWS -->|Incident Event Baru| IncrementCounter["Update Real-Time Counter & Redraw Chart"]
    IncrementCounter --> End([Render Selesai])
```

```mermaid
sequenceDiagram
    actor User as Operator Browser
    participant Dash as osi-dashboard-server
    participant DB as PostgreSQL
    participant WS as WebSocket Hub

    User->>Dash: GET /api/v1/metrics/overview
    Dash->>DB: SELECT COUNT(*), AVG(confidence_score) FROM incidents
    DB-->>Dash: Return KPI Metrics
    Dash-->>User: 200 OK (JSON Metrics)
    WS-->>User: Push Live Event (Incident Created)
    User->>User: Redraw Overview KPI Widgets
```

---

## Panel 2: Monitoring Live (`#p-monitoring`)

### 1. Spesifikasi Panel
* **Tujuan**: Memantau metrik latensi jaringan, utilisasi CPU/RAM/Disk server, dan situs jaringan secara real-time.
* **Fungsi**: Menampilkan grafik deret waktu (*time-series chart*) kinerja jaringan dan server.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`, `viewer`.
* **Source Data**: Netdata REST API (`/api/v1/data`), NATS `telemetry.ingest`.
* **Backend Endpoint**: `GET /api/monitoring/live`.
* **Frontend Component**: JS Object `Panels.monitoring`, Chart.js Canvas `#chart-monitoring-live`.

### 2. Diagram Internal Panel Monitoring Live

```mermaid
flowchart TD
    A[Start Monitoring Loop] --> B[Fetch Netdata REST API /api/v1/data]
    B --> C[Format Time-Series Dataset]
    C --> D[Update Chart.js Canvas #chart-monitoring-live]
    D --> E[Sleep 5s Interval]
    E --> A
```

---

## Panel 3: Server Health (`#p-server`)

### 1. Spesifikasi Panel
* **Tujuan**: Menampilkan skor kesehatan server internal (`SystemAuditor v2.2`) dan status komponen sistem.
* **Fungsi**: Menilai kesehatan CPU, RAM, Disk, NATS, Redis, dan Database PostgreSQL.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`, `viewer`.
* **Source Data**: `/api/server/health` & Docker Healthchecks.
* **Backend Endpoint**: `GET /api/server/health`.
* **Frontend Component**: JS Object `Panels.server`, Container `#server-health-grid`.

---

## Panel 4: Activity (`#p-activity`)

### 1. Spesifikasi Panel
* **Tujuan**: Memantau jejak aktivitas pengguna dan log aplikasi browser secara real-time.
* **Fungsi**: Mencatat tab browser aktif (Chrome/Edge), crash browser, dan interaksi user.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`, `viewer`.
* **Source Data**: Browser Telemetry API & PostgreSQL Table `user_activity_logs`.
* **Backend Endpoint**: `GET /api/activity/user_logs`.

---

## Panel 5: Browser Logs (`#p-browser_logs`)

### 1. Spesifikasi Panel
* **Tujuan**: Menangkap dan menampilkan log konsol JavaScript browser, eksepsi frontend, dan error jaringan.
* **Fungsi**: Membantu debugging kesalahan sisi klien.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`.
* **Source Data**: Browser `window.onerror` Event Listener.
* **Backend Endpoint**: `POST /api/browser/logs`.

---

## Panel 6: PC Health (`#p-pchealth`)

### 1. Spesifikasi Panel
* **Tujuan**: Pemantauan mendalam kesehatan PC klien (CPU, RAM, Disk, Port USB, Service Windows/Linux).
* **Fungsi**: Menyajikan daftar PC terdaftar dan opsi tombol remote diagnosa 1-klik.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`, `viewer`.
* **Source Data**: Telemetry Agen Windows & Linux, Table `devices`.
* **Backend Endpoint**: `GET /api/fleet/admin/devices`.

---

## Panel 7: Printer Status (`#p-printer`)

### 1. Spesifikasi Panel
* **Tujuan**: Memantau status printer enterprise, antrean cetak (*spooler queue*), level toner, dan penanganan insiden printer.
* **Fungsi**: Opsi restart spooler 1-klik dan pembersihan antrean printer.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`, `viewer`.
* **Source Data**: Agen Windows Spooler WMI & Table `printers`.
* **Backend Endpoint**: `GET /api/printer/status`.

---

## Panel 8: Fleet Management (`#p-fleet`)

### 1. Spesifikasi Panel
* **Tujuan**: Mengelola registri inventaris armada PC, lokasi site/cabang, IP gateway, dan distribusi versi agen.
* **Fungsi**: Registrasi peranti baru, pengelompokan site, dan pembaruan versi agen.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`, `viewer`.
* **Source Data**: PostgreSQL Table `devices`, `sites`.
* **Backend Endpoint**: `GET /api/fleet/admin/devices` & `POST /api/fleet/register`.

---

## Panel 9: Storage (`#p-storage`)

### 1. Spesifikasi Panel
* **Tujuan**: Memantau kapasitas disk storage server, memori Redis, indeks RAG, dan berkas file sistem.
* **Fungsi**: Menyediakan alat AI File Operations (Read, Edit, Download, Validate berkas AI).
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`, `viewer`.
* **Source Data**: OS File System Stats & Redis Memory Stats.
* **Backend Endpoint**: `GET /api/storage/metrics` & `GET /api/ai_file/read`.

---

## Panel 10: Incident Triage (`#p-incident`)

### 1. Spesifikasi Panel
* **Tujuan**: Pusat penanganan dan penyaringan insiden aktif dari PostgreSQL `osi_system.incidents`.
* **Fungsi**: Penyaringan insiden berdasarkan status (OPEN, RESOLVED, PENDING), severity (CRITICAL, HIGH), dan kategori.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `incidents`.
* **Backend Endpoint**: `GET /api/incidents`.

---

## Panel 11: Ground Truth & RCA (`#p-rca`)

### 1. Spesifikasi Panel
* **Tujuan**: Analisis mendalam akar masalah insiden (*Root Cause Analysis*) berbasis metodologi 5-Why.
* **Fungsi**: Menampilkan hipotesis 1 s.d 5, skor confidence, bukti pendukung, dan tombol eksekusi aksi remediasi.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `ai_reflection_logs`.
* **Backend Endpoint**: `GET /api/rca/analysis`.

---

## Panel 12: 5 Why Analysis (`#p-five_why`)

### 1. Spesifikasi Panel
* **Tujuan**: Menyajikan perincian deduksi kausal 5-Why yang disusun oleh AI Consensus Engine.
* **Fungsi**: Menjelaskan urutan sebab-akibat secara berjenjang dari gejala hingga akar masalah.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `ai_reflection_logs.first_hypothesis`.

---

## Panel 13: Causal Graph (`#p-unified_dag`)

### 1. Spesifikasi Panel
* **Tujuan**: Visualisasi grafis ketergantungan kausal (*Causal Topology Graph*) antara peranti dan layanan.
* **Fungsi**: Interaktif DAG zoom/pan/search untuk mengisolasi titik kegagalan utama.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: `/api/knowledge_graph` & Table `dependency_map`.

---

## Panel 14: Decision Graph (`#p-decision_dag`)

### 1. Spesifikasi Panel
* **Tujuan**: Visualisasi grafis pohon keputusan AI (*Cognitive Decision Graph*) dalam memilih playbook remediasi.
* **Fungsi**: Menelusuri rantai penalaran dan cabang evaluasi kebijakan AI.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `ai_reflection_logs`.

---

## Panel 15: Evidence DAG (`#p-evidence_dag`)

### 1. Spesifikasi Panel
* **Tujuan**: Menyajikan jejak gabungan bukti (*Unified Evidence Trace*) yang dikumpulkan dari log, telemetri, dan RAG.
* **Fungsi**: Menghubungkan bukti mentah dengan kesimpulan akhir AI.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `ai_evidence_logs`.

---

## Panel 16: Approval Queue (`#p-approval_queue`)

### 1. Spesifikasi Panel
* **Tujuan**: Gerbang persetujuan manusia (*Human-in-the-Loop HITL Gate*) untuk aksi remediasi berisiko tinggi.
* **Fungsi**: Memfasilitasi 1-klik Approve atau Reject dari operator NOC.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `ai_approval_logs`.
* **Backend Endpoint**: `GET /api/approval_queue` & `POST /api/approval_queue/approve`.

---

## Panel 17: Pending Verification (`#p-pending_verification`)

### 1. Spesifikasi Panel
* **Tujuan**: Memantau peranti yang sedang berada dalam tahap pengujian kesehatan pasca-tindakan remediasi.
* **Fungsi**: Menampilkan status pengecekan 5 parameter (*service, port, latency, cpu, memory*).
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `pending_verification`.

---

## Panel 18: Rollback History (`#p-rollback_history`)

### 1. Spesifikasi Panel
* **Tujuan**: Audit trail dan riwayat pengembalian konfigurasi otomatis (*Automated State Machine Rollback*).
* **Fungsi**: Menampilkan log eksekusi rollback ketika verifikasi pasca-tindakan gagal.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `rollback_logs`.

---

## Panel 19: Failed Actions DLQ (`#p-failed_actions`)

### 1. Spesifikasi Panel
* **Tujuan**: Menampung aksi remediasi yang mengalami kegagalan eksekusi (*Dead Letter Queue*).
* **Fungsi**: Memungkinkan pemutaran ulang (*replay*) atau investigasi kesalahan eksekusi.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `failed_actions_dlq`.

---

## Panel 20: AI Panel (`#p-ai`)

### 1. Spesifikasi Panel
* **Tujuan**: Pusat observabilitas metrik internal mesin AI (Reasoning, Prediction, Classification).
* **Fungsi**: Menampilkan statistik penggunaan token LLM, distribusi confidence score, dan model aktif.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: `/api/v1/ai/metrics` & `ai_reflection_logs`.

---

## Panel 21: Training Feedback (`#p-training`)

### 1. Spesifikasi Panel
* **Tujuan**: Mengelola umpan balik manusia (*RLHF / RAG Feedback*) untuk pembelajaran kontinu AI.
* **Fungsi**: Penilaian verifikasi (Benar/Salah) pada jawaban AI untuk penyesuaian bobot RAG.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `rag_historical_logs`.

---

## Panel 22: Execution Timeline (`#p-exec_timeline`)

### 1. Spesifikasi Panel
* **Tujuan**: Memantau tahapan eksekusi pipeline AI secara real-time dari ingesti hingga penutupan insiden.
* **Fungsi**: Menampilkan timeline visual berurutan waktu dari setiap tahapan pipeline.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: WebSocket Stream `/ws/logs` & PostgreSQL Table `incidents`.

---

## Panel 23: Event Correlation (`#p-event_correlation`)

### 1. Spesifikasi Panel
* **Tujuan**: Menampilkan hasil pengelompokan event terkorrelasi (*Root Event & Downstream Effects*).
* **Fungsi**: Menghubungkan alarm-alarm turunan dengan 1 event akar masalah utama.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `event_correlations`.

---

## Panel 24: AI Decision Logs (`#p-ai_decision_logs`)

### 1. Spesifikasi Panel
* **Tujuan**: Audit trail lengkap seluruh rekam keputusan refleksi AI.
* **Fungsi**: Menampilkan ID insiden, TraceId, SpanId, hipotesis pertama, keputusan akhir, dan confidence score.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `ai_reflection_logs`.
* **Backend Endpoint**: `GET /api/ai_decision_logs`.

---

## Panel 25: Schema Validation Logs (`#p-schema_validation_logs`)

### 1. Spesifikasi Panel
* **Tujuan**: Audit log validasi skema JSON keluaran LLM oleh **AI Critic Engine**.
* **Fungsi**: Mencatat kegagalan sintaksis skema dan koreksi otomatis oleh guardrail.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `schema_validation_logs`.
* **Backend Endpoint**: `GET /api/schema_validation_logs`.

---

## Panel 26: Learning Gate Audit (`#p-learning_gate_logs`)

### 1. Spesifikasi Panel
* **Tujuan**: Audit log penyerapan pembelajaran kontinu dari insiden yang sukses diverifikasi.
* **Fungsi**: Menampilkan riwayat penyesuaian bobot RAG dan pembaruan SOP.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `learning_gate_logs`.
* **Backend Endpoint**: `GET /api/learning_gate_logs`.

---

## Panel 27: AI Governance Center (`#p-gov`)

### 1. Spesifikasi Panel
* **Tujuan**: Pusat tata kelola, transparansi, dan pemenuhan SLA aksi otonom AI.
* **Fungsi**: Menampilkan metrik kepatuhan, explainability, antrean HITL, dan aturan kebijakan.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`.
* **Source Data**: PostgreSQL Table `governance_metrics`.

---

## Panel 28: SOP Lifecycle (`#p-sop`)

### 1. Spesifikasi Panel
* **Tujuan**: Mengelola siklus hidup dokumen SOP remediasi (Draft $\rightarrow$ Review $\rightarrow$ Active).
* **Fungsi**: Pembuatan draf SOP baru, persetujuan supervisor, dan pengindeksan ke Vector RAG DB.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`.
* **Source Data**: PostgreSQL Table `sops`.

---

## Panel 29: Model Config (`#p-models`)

### 1. Spesifikasi Panel
* **Tujuan**: Konfigurasi parameter model AI, API Keys LLM, dan registri alat remote.
* **Fungsi**: Pengaturan temperature, max tokens, endpoint LLM, dan API Key rotation.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`.
* **Source Data**: PostgreSQL Table `model_configs`.

---

## Panel 30: Security Policies (`#p-security_policies`)

### 1. Spesifikasi Panel
* **Tujuan**: Mengatur aturan dan ambang batas keamanan eksekusi perintah oleh AI.
* **Fungsi**: Pengelolaan daftar hitam perintah (*command blacklist*) dan batasan akses peranti.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`.
* **Source Data**: PostgreSQL Table `security_policies`.

---

## Panel 31: Recovery Mode Config (`#p-recovery_mode_config`)

### 1. Spesifikasi Panel
* **Tujuan**: Mengatur mode operasional pemulihan sistem (Semi-Auto / Advisory / Full-Auto).
* **Fungsi**: Sakelar darurat (*Emergency Kill Switch*) untuk menghentikan aksi otonom AI.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`.
* **Source Data**: PostgreSQL Table `system_config`.

---

## Panel 32: Learning Gate Policy (`#p-learning_gate_policy`)

### 1. Spesifikasi Panel
* **Tujuan**: Mengatur ambang batas dan syarat masuk data baru ke gerbang pembelajaran AI.
* **Fungsi**: Menentukan persentase minimum verifikasi sukses sebelum SOP diperbarui.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`.
* **Source Data**: PostgreSQL Table `learning_gate_policies`.

---

## Panel 33: RBAC Policies (`#p-rbac`)

### 1. Spesifikasi Panel
* **Tujuan**: Manajemen kebijakan Role-Based Access Control untuk pengguna dashboard.
* **Fungsi**: Pengaturan izin akses panel per role (`superadmin`, `admin`, `noc_engineering`, `operator`, `viewer`).
* **Role RBAC**: `superadmin`, `admin`.
* **Source Data**: PostgreSQL Table `rbac_users`, `rbac_roles`.
* **Backend Endpoint**: `GET /api/rbac/roles` & `POST /api/rbac/assign`.

---

## Panel 34: Smart Incident Stream (`#p-smart_stream`)

### 1. Spesifikasi Panel
* **Tujuan**: Menyajikan aliran insiden terstruktur Bahasa Indonesia yang mudah dipahami manusia secara real-time dari telemetri ter-enrich.
* **Fungsi**: Menampilkan KPI stream, pencarian PC online/offline, filter status insiden, dan kartu insiden interaktif.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`, `viewer`.
* **Source Data**: WebSocket `/ws/logs`, `/api/ai_decision_logs`, `/api/fleet/admin/devices`.
* **Backend Endpoint**: `GET /api/ai_decision_logs`.
* **Frontend Component**: HTML `<div id="p-smart_stream" class="panel">`, JS Object `Panels.smart_stream`.

---

## Panel 35: Live Logs (`#p-logs`)

### 1. Spesifikasi Panel
* **Tujuan**: Pencarian dan penyaringan streaming log mentah server dan agen secara real-time.
* **Fungsi**: Filter berdasarkan kata kunci, sumber log (NetData, PING, System), dan opsi unduh log.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: WebSocket `/ws/logs` & Log Files.
* **Frontend Component**: JS Object `LogStreamer`, HTML Container `#log-container`.

---

## Panel 36: NATS Subjects Telemetry (`#p-nats_subjects`)

### 1. Spesifikasi Panel
* **Tujuan**: Pemantauan throughput dan status subject broker pesan NATS secara real-time.
* **Fungsi**: Menampilkan daftar subject (`telemetry.ingest`, `agent.incident`, `agent.verify`), status koneksi, dan latensi RTT.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: NATS Monitoring API `:8222/varz`.
* **Backend Endpoint**: `GET /api/nats_subjects`.

---

## Panel 37: Live Chat Support (`#p-chat`)

### 1. Spesifikasi Panel
* **Tujuan**: Layanan chat interaktif antara operator NOC dengan klien PC terdaftar secara real-time yang dilengkapi saran balasan AI (*AI Reply Suggestions*).
* **Fungsi**: Diskusi live chat, pengiriman lampiran berkas/screenshot, dan konteks peranti otomatis.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: Enterprise Chat Engine WebSocket `/ws/operator_chat`, `/api/enterprise/chat/sessions`, `/api/fleet/admin/devices`.
* **Frontend Component**: HTML `<div id="p-chat" class="panel">`, JS Object `NocChat`.

---

## Panel 38: Evidence Explorer / Agent Health (`#p-evidence`)

### 1. Spesifikasi Panel
* **Tujuan**: Audit jejak bukti (*Evidence Trail*) dan pengujian kesiapan (*readiness*) komponen AI Engine.
* **Fungsi**: Menampilkan daftar bukti terverifikasi dan skor kesiapan AI.
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Table `ai_evidence_logs`.
* **Backend Endpoint**: `GET /api/evidence_explorer`.

---

## Panel 39: Knowledge Graph (`#p-kgraph`)

### 1. Spesifikasi Panel
* **Tujuan**: Visualisasi grafik pengetahuan dependensi sistem enterprise dan perelasan antar peranti.
* **Fungsi**: Menampilkan topologi jaringan interaktif untuk isolasi dampak insiden (*Blast Radius*).
* **Role RBAC**: `superadmin`, `admin`, `noc_engineering`, `operator`.
* **Source Data**: PostgreSQL Tables `dependency_map`, `devices`, `erg_nodes`, `erg_edges`.
* **Backend Endpoint**: `GET /api/knowledge_graph`.

---

# LEVEL 6: Inter-Panel End-to-End Cascade Sequence Diagram

```mermaid
sequenceDiagram
    autonumber
    actor FleetAgent as Agent Target (Windows/Linux)
    participant Ingest as Ingestion Bridge (:8080)
    participant NATS as NATS Broker (:4222)
    participant DB as PostgreSQL (:5422)
    participant Dash as Dashboard Core (:8080)
    participant WS as WS Broadcaster (/ws/logs)
    participant SmartStream as Panel Smart Incident Stream (#p-smart_stream)
    participant AICore as AI Cognitive Core (:5000)
    participant HITL as Panel Approval Queue (#p-approval_queue)
    participant Relay as Secure Relay (:8081)
    participant Verifier as State Verifier Engine
    actor Operator as NOC Operator

    FleetAgent->>Ingest: Send Telemetry Anomaly (High CPU 98%)
    Ingest->>NATS: Publish "telemetry.ingest"
    NATS->>DB: Deduplicate & Insert to "incidents" (status='OPEN')
    NATS->>Dash: Event Trigger
    Dash->>WS: Push Event Frame
    WS-->>SmartStream: Render New Human-Readable Card

    NATS->>AICore: Trigger Cognitive Reasoning Pipeline
    AICore->>AICore: RAG SOP Match & Knowledge Graph Traversal
    AICore->>DB: INSERT INTO "ai_reflection_logs" (RCA 5-Why, Conf: 95.8%)

    alt High Risk Action Needed
        AICore->>DB: INSERT INTO "ai_approval_logs" (status='PENDING')
        Dash->>WS: Push Approval Card Event
        WS-->>HITL: Render HITL Approval Card
        Operator->>HITL: Click "Approve Remediation"
        HITL->>DB: UPDATE "ai_approval_logs" SET status='APPROVED'
    end

    Dash->>Relay: Dispatch Remediation Script
    Relay->>FleetAgent: Execute Encrypted Script (Restart Service)
    FleetAgent-->>Relay: Return Exit Code 0

    Relay->>Verifier: Trigger Post-Execution Verification
    Verifier->>FleetAgent: Poll Telemetry Check (Wait 5s)

    alt Verification PASS
        Verifier->>DB: INSERT INTO "learning_gate_logs" (status='SUCCESS')
        Verifier->>DB: UPDATE "incidents" SET status='CLOSED'
        Dash->>WS: Push "AUTO_RESOLVED" Badge Update
        WS-->>SmartStream: Update Card Status to Green (AUTO-RESOLVED)
    else Verification FAIL
        Verifier->>DB: INSERT INTO "rollback_logs" (reason='Check Fail')
        Verifier->>Relay: Dispatch Rollback Script
        Relay->>FleetAgent: Restore Original Backup Config
        Verifier->>DB: UPDATE "incidents" SET status='FAILED'
        Dash->>WS: Push "CRITICAL/FAILED" Badge Update
        WS-->>SmartStream: Update Card Status to Red (CRITICAL/FAILED)
    end
```

---

# LEVEL 7: Real-World Runtime Execution Scenarios

### Skenario Nyata: Lonjakan CPU Server Linux 98% (End-to-End Trace)

1. **Deteksi Terestrial oleh Agen (0ms)**:
   - Daemon `osi-agent-linux` pada host `LINUX-PC-TMS` membaca `/proc/stat` dan mendeteksi utilisasi CPU mencapai **98.4%** akibat deadlock proses `nginx`.
2. **Pengiriman Telemetri (15ms)**:
   - Agen mengonstruksi payload JSON telemetri dan mempublikasikannya ke NATS Broker subject `telemetry.ingest`.
3. **Ingesti & Deduplikasi (45ms)**:
   - `osi-ingestion-server` memvalidasi token agen. `Event Normalizer Engine` mengecek slide-window hash 60 detik. Karena event ini baru, sistem membuat entri insiden di PostgreSQL `incidents` (`incident_id: 412`, `status: OPEN`).
4. **Publish Anomali ke AI Cluster (80ms)**:
   - Ingestion Bridge mempublikasikan event ke NATS subject `agent.incident`.
5. **Pencarian SOP RAG & Topologi Graph (220ms)**:
   - `osi-python-ai-core` menerima event, lalu melakukan pencarian vektor similarity di `osi-ai-rag` (Menemukan `KB-SOP-002: Restart Deadlocked Nginx Worker`).
   - `osi-python-ai-core` menelusuri Knowledge Graph `/api/knowledge_graph` (Mengonfirmasi `LINUX-PC-TMS` sebagai node akar masalah).
6. **Penalaran RCA 5-Why & Safety Check (380ms)**:
   - AI menyusun 5-Why RCA dan mengkalkulasi skor confidence **96.2%**.
   - `osi-ai-critic` memverifikasi perintah `systemctl restart nginx` terhadap daftar hitam keamanan $\rightarrow$ Result `PASS`.
7. **Routing Keputusan & Broadcast UI (450ms)**:
   - Karena aksi ini tergolong berisiko rendah dan confidence > 85%, sistem memilih mode `AUTO_APPROVED`.
   - `osi-dashboard-server` menyiarkan event via WebSocket `/ws/logs`. Menu **Smart Incident Stream** (`#p-smart_stream`) merender kartu insiden Bahasa Indonesia real-time.
8. **Eksekusi Command Relay (540ms)**:
   - `osi-secure-relay` meng-encrypt perintah dengan AES-256 dan mendispatch-nya ke agen `LINUX-PC-TMS`.
   - Agen mengeksekusi `systemctl restart nginx` dan mengembalikan exit code `0`.
9. **Verifikasi Pasca-Tindakan (5540ms)**:
   - `State Verifier Agent` menunggu 5 detik, lalu memeriksa 5 parameter: `service_alive` (True), `port_open` (True), `latency` (12ms), `cpu_normalized` (14.2%), `memory_normalized` (48%). All PASS.
10. **Penutupan Insiden & Ingest Learning (5800ms)**:
    - Insiden ditutup di DB (`incidents.status = CLOSED`). Rekam keberhasilan dicatat di `learning_gate_logs`. Bobot SOP `KB-SOP-002` ditingkatkan +0.05. Kartu di **Smart Incident Stream** berubah badge menjadi hijau **`✔ AUTO-RESOLVED`**.

---

# LEVEL 8: Source Code, API, Table, & Observability Mapping Catalog

| Panel ID | Panel Name | Frontend JS File | Backend Source File | Primary REST / WS Endpoint | PostgreSQL Table | NATS Subject | Primary AI Module | Log File |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `#p-overview` | Overview | `portal/templates/index.html` (`Panels.overview`) | `portal/dashboard_server.go` | `GET /api/v1/metrics/overview` | `incidents`, `ai_reflection_logs` | `telemetry.ingest` | `osi-python-ai-core` | `/var/log/osi-dashboard-server.log` |
| `#p-monitoring` | Monitoring Live | `portal/templates/index.html` (`Panels.monitoring`) | `portal/dashboard/metrics/metrics.go` | `GET /api/monitoring/live` | `telemetry_logs` | `telemetry.ingest` | *N/A* | `/var/log/netdata_harvester.log` |
| `#p-server` | Server Health | `portal/templates/index.html` (`Panels.server`) | `portal/dashboard_server.go` | `GET /api/server/health` | `devices` | `telemetry.ingest` | *N/A* | `/var/log/osi-server-health.log` |
| `#p-activity` | Activity | `portal/templates/index.html` (`Panels.activity`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/activity/user_logs` | `user_activity_logs` | *N/A* | *N/A* | `/var/log/user_activity.log` |
| `#p-browser_logs` | Browser Logs | `portal/templates/index.html` (`Panels.browser_logs`) | `portal/dashboard/api/missing_handlers.go` | `POST /api/browser/logs` | `browser_logs` | *N/A* | *N/A* | `/var/log/browser_err.log` |
| `#p-pchealth` | PC Health | `portal/templates/index.html` (`Panels.pchealth`) | `portal/dashboard/fleet/` | `GET /api/fleet/admin/devices` | `devices` | `telemetry.ingest` | *N/A* | `/var/log/pchealth.log` |
| `#p-printer` | Printer Status | `portal/templates/index.html` (`Panels.printer`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/printer/status` | `printers` | `telemetry.ingest` | *N/A* | `/var/log/printer.log` |
| `#p-fleet` | Fleet Management | `portal/templates/index.html` (`Panels.fleet`) | `portal/dashboard/fleet/` | `GET /api/fleet/admin/devices` | `devices`, `sites` | `telemetry.ingest` | *N/A* | `/var/log/fleet.log` |
| `#p-storage` | Storage | `portal/templates/index.html` (`Panels.storage`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/storage/metrics` | `storage_metrics` | *N/A* | *N/A* | `/var/log/storage.log` |
| `#p-incident` | Incident Triage | `portal/templates/index.html` (`Panels.incident`) | `portal/dashboard/incident/incident.go` | `GET /api/incidents` | `incidents` | `agent.incident` | `osi-python-ai-core` | `/var/log/incidents.log` |
| `#p-rca` | Ground Truth & RCA | `portal/templates/index.html` (`Panels.rca`) | `portal/dashboard/incident/incident.go` | `GET /api/rca/analysis` | `ai_reflection_logs` | `agent.incident` | `osi-python-ai-core` | `/var/log/rca.log` |
| `#p-five_why` | 5 Why Analysis | `portal/templates/index.html` (`Panels.five_why`) | `portal/dashboard/incident/incident.go` | `GET /api/rca/analysis` | `ai_reflection_logs` | `agent.incident` | `osi-python-ai-core` | `/var/log/five_why.log` |
| `#p-unified_dag` | Causal Graph | `portal/templates/index.html` (`Panels.unified_dag`) | `portal/cognitive_memory_api.go` | `GET /api/knowledge_graph` | `dependency_map` | *N/A* | `Knowledge Graph` | `/var/log/causal_graph.log` |
| `#p-decision_dag` | Decision Graph | `portal/templates/index.html` (`Panels.decision_dag`) | `portal/dashboard/incident/incident.go` | `GET /api/ai_decision_logs` | `ai_reflection_logs` | *N/A* | `osi-python-ai-core` | `/var/log/decision_graph.log` |
| `#p-evidence_dag` | Evidence DAG | `portal/templates/index.html` (`Panels.evidence_dag`) | `portal/dashboard/incident/incident.go` | `GET /api/evidence_explorer` | `ai_evidence_logs` | *N/A* | `osi-python-ai-core` | `/var/log/evidence_dag.log` |
| `#p-approval_queue` | Approval Queue | `portal/templates/index.html` (`Panels.approval_queue`) | `portal/dashboard/incident/incident.go` | `GET /api/approval_queue` | `ai_approval_logs` | `hitl.pending` | `osi-ai-policy` | `/var/log/approval_queue.log` |
| `#p-pending_verification` | Pending Verification | `portal/templates/index.html` (`Panels.pending_verification`) | `portal/dashboard/incident/incident.go` | `GET /api/pending_verification` | `pending_verification` | `agent.verify` | *N/A* | `/var/log/pending_verification.log` |
| `#p-rollback_history` | Rollback History | `portal/templates/index.html` (`Panels.rollback_history`) | `portal/dashboard/incident/incident.go` | `GET /api/rollback_history` | `rollback_logs` | `action.rollback` | *N/A* | `/var/log/rollback.log` |
| `#p-failed_actions` | Failed Actions (DLQ) | `portal/templates/index.html` (`Panels.failed_actions`) | `portal/dashboard/incident/incident.go` | `GET /api/failed_actions` | `failed_actions_dlq` | *N/A* | *N/A* | `/var/log/dlq.log` |
| `#p-ai` | AI Panel | `portal/templates/index.html` (`Panels.ai`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/v1/ai/metrics` | `ai_reflection_logs` | *N/A* | `osi-python-ai-core` | `/var/log/ai_panel.log` |
| `#p-training` | Training Feedback | `portal/templates/index.html` (`Panels.training`) | `portal/dashboard/api/missing_handlers.go` | `POST /api/training/feedback` | `rag_historical_logs` | *N/A* | `osi-ai-rag` | `/var/log/training.log` |
| `#p-exec_timeline` | Execution Timeline | `portal/templates/index.html` (`Panels.exec_timeline`) | `portal/dashboard/incident/incident.go` | `WS /ws/logs` | `incidents` | `telemetry.ingest` | `osi-python-ai-core` | `/var/log/timeline.log` |
| `#p-event_correlation` | Event Correlation | `portal/templates/index.html` (`Panels.event_correlation`) | `portal/dashboard/incident/incident.go` | `GET /api/event_correlation` | `event_correlations` | `agent.incident` | `osi-python-ai-core` | `/var/log/event_correlation.log` |
| `#p-ai_decision_logs` | AI Decision Logs | `portal/templates/index.html` (`Panels.ai_decision_logs`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/ai_decision_logs` | `ai_reflection_logs` | *N/A* | `osi-python-ai-core` | `/var/log/ai_decision.log` |
| `#p-schema_validation_logs` | Schema Validation Logs | `portal/templates/index.html` (`Panels.schema_validation_logs`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/schema_validation_logs` | `schema_validation_logs` | *N/A* | `osi-ai-critic` | `/var/log/schema_validation.log` |
| `#p-learning_gate_logs` | Learning Gate Audit | `portal/templates/index.html` (`Panels.learning_gate_logs`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/learning_gate_logs` | `learning_gate_logs` | `learning.gate` | `osi-ai-rag` | `/var/log/learning_gate.log` |
| `#p-gov` | AI Governance Center | `portal/templates/index.html` (`Panels.gov`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/gov/metrics` | `governance_metrics` | *N/A* | `osi-ai-policy` | `/var/log/governance.log` |
| `#p-sop` | SOP Lifecycle | `portal/templates/index.html` (`Panels.sop`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/sop/list` | `sops` | *N/A* | `osi-ai-rag` | `/var/log/sop.log` |
| `#p-models` | Model Config | `portal/templates/index.html` (`Panels.models`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/models/config` | `model_configs` | *N/A* | `osi-python-ai-core` | `/var/log/models.log` |
| `#p-security_policies` | Security Policies | `portal/templates/index.html` (`Panels.security_policies`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/security_policies` | `security_policies` | *N/A* | `osi-ai-critic` | `/var/log/security_policies.log` |
| `#p-recovery_mode_config` | Recovery Mode Config | `portal/templates/index.html` (`Panels.recovery_mode_config`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/recovery_mode_config` | `system_config` | *N/A* | `osi-ai-policy` | `/var/log/recovery_mode.log` |
| `#p-learning_gate_policy` | Learning Gate Policy | `portal/templates/index.html` (`Panels.learning_gate_policy`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/learning_gate_policy` | `learning_gate_policies` | *N/A* | `osi-ai-rag` | `/var/log/learning_gate_policy.log` |
| `#p-rbac` | RBAC Policies | `portal/templates/index.html` (`Panels.rbac`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/rbac/roles` | `rbac_users`, `rbac_roles` | *N/A* | *N/A* | `/var/log/rbac.log` |
| `#p-smart_stream` | Smart Incident Stream | `portal/templates/index.html` (`Panels.smart_stream`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/ai_decision_logs` & `WS /ws/logs` | `ai_reflection_logs`, `devices` | `telemetry.ingest` | `osi-python-ai-core` | `/var/log/smart_stream.log` |
| `#p-logs` | Live Logs | `portal/templates/index.html` (`LogStreamer`) | `portal/dashboard_server.go` | `WS /ws/logs` | `telemetry_logs` | `telemetry.ingest` | *N/A* | `/var/log/live_logs.log` |
| `#p-nats_subjects` | NATS Subjects Telemetry | `portal/templates/index.html` (`Panels.nats_subjects`) | `portal/dashboard/incident/incident.go` | `GET /api/nats_subjects` | *N/A* | `telemetry.ingest` | *N/A* | `/var/log/nats.log` |
| `#p-chat` | Live Chat Support | `portal/templates/index.html` (`NocChat`) | `portal/chat_engine.go` | `WS /ws/operator_chat` & `GET /api/enterprise/chat/sessions` | `chat_sessions`, `chat_messages` | *N/A* | `osi-python-ai-core` | `/var/log/live_chat.log` |
| `#p-evidence` | Evidence Explorer | `portal/templates/index.html` (`Panels.evidence`) | `portal/dashboard/api/missing_handlers.go` | `GET /api/evidence_explorer` | `ai_evidence_logs` | *N/A* | `osi-python-ai-core` | `/var/log/evidence.log` |
| `#p-kgraph` | Knowledge Graph | `portal/templates/index.html` (`Panels.kgraph`) | `portal/cognitive_memory_api.go` | `GET /api/knowledge_graph` | `dependency_map`, `devices` | *N/A* | `Knowledge Graph` | `/var/log/kgraph.log` |

---

## 🏛️ Kesimpulan & Status Conformity Audit

Dokumentasi master arsitektur 39 panel dashboard ini dibuat **100% berdasarkan implementasi nyata pada kode sumber (*Ground Truth Source Code*)** proyek `incident-analysis`. Seluruh 8 level spesifikasi teknis, diagram Mermaid, alur sekuensial inter-panel, dan pemetaan katalog telah terverifikasi akurat dan **siap di-audit (*Enterprise Audit-Ready*)**.
