# Enterprise Autonomous AI OS — Implementation Master Plan
**Dokumen:** Rencana Implementasi Step-by-Step  
**Target Sistem:** OSI Incident Analysis Platform (Production)  
**Dibuat:** 2026-07-09  
**Prinsip:** Reuse, Extend, Wrap — TIDAK ada penulisan ulang dari nol  

---

## Audit Aktual Sistem yang Berjalan

Setelah audit mendalam terhadap source code dan database produksi, sistem ini **jauh lebih matang** dari perkiraan awal.

### Modul Python yang SUDAH ADA

| File | Fungsi | Status |
|------|--------|--------|
| `ai_supervisor.py` | Orkestrasi utama NATS + incident pipeline | ✅ AKTIF |
| `state_machine.py` | State Machine insiden (NEW→RESOLVED) | ✅ AKTIF |
| `trust_engine.py` | Skoring kepercayaan per-agen | ✅ AKTIF |
| `policy_engine.py` | OPA-style governance rules | ✅ AKTIF |
| `consensus_engine.py` | Multi-step consensus | ✅ AKTIF |
| `closure_engine.py` | Knowledge edge reinforcement | ✅ AKTIF |
| `rag_engine.py` | pgvector semantic search | ✅ AKTIF |
| `replay_engine.py` | Simulasi ulang insiden | ✅ AKTIF (Reuse utk Digital Twin) |
| `blast_radius_engine.py` | Impact propagation analysis | ✅ AKTIF (World Model proto) |
| `critic_engine.py` | Evaluasi tindakan AI | ✅ AKTIF |
| `causal_mapper.py` | Root cause causal graph | ✅ AKTIF |
| `knowledge_edge_manager.py` | Manajemen bobot knowledge graph | ✅ AKTIF |
| `seed_rag.py` | Seeder knowledge vectors | ✅ ADA (perlu dijadikan daemon) |
| `schemas/learning_schema.py` | Schema pembelajaran | ✅ ADA (perlu diperluas) |

### Tabel Database yang SUDAH ADA (125 tabel)

| Kategori | Tabel Kunci | Status AI OS |
|----------|-------------|--------------|
| **State/Recovery** | `rollback_logs`, `rollback_events`, `replay_sessions` | Reuse → Recovery Domain |
| **Knowledge** | `knowledge_vectors`, `knowledge_edges`, `golden_resolutions` | Reuse → Knowledge Fabric |
| **Evidence** | `ai_evidence_logs`, `ai_audit_trail` (partitioned) | Reuse → Experience Graph |
| **Policy** | `policy_rules`, `opa_policy_rules`, `learning_gate_policy` | Reuse → Governance Layer |
| **Trust** | `agent_trust_scores`, `agent_heartbeats` | Reuse → Trust Engine |
| **Fleet/World** | `fleet_topology`, `dependency_map`, `device_dependencies`, `network_paths` | Reuse → World Model |
| **Observability** | `ai_reflection_logs`, `critic_logs`, `trace_integrity_reports` | Reuse → Observability Fabric |

---

## Kesimpulan Audit: Yang BENAR-BENAR Hilang

Berdasarkan audit aktual (bukan asumsi):

1. **Tidak ada Global Runtime State Manager** — `state_machine.py` hanya untuk insiden, bukan untuk AI system-level.
2. **Tidak ada Internal API Contract** — modul saling dipanggil langsung, bukan via interface.
3. **Tidak ada Cognitive Trace** — `ai_audit_trail` ada tapi tidak menyimpan reasoning trace.
4. **Tidak ada Learning Loop Aktif** — `seed_rag.py` statis, tidak ada daemon belajar.
5. **Tidak ada Knowledge Freshness** — `knowledge_vectors` tidak punya kolom `age` atau `last_validated`.
6. **Tidak ada Unified Knowledge Abstraction** — `blast_radius_engine`, `causal_mapper`, `rag_engine` beroperasi terpisah.
7. **Tidak ada Meta-Cognition** — AI tidak mengevaluasi efisiensi nalarnya sendiri.

---

## Strategic Evolution Priorities (The Cognitive Era)

Berdasarkan evaluasi terhadap pipeline reaktif saat ini (Detect → Analyze → Action), evolusi sistem ke depan (Fase 3-6) akan difokuskan pada 5 kapabilitas AGI (*Artificial General Intelligence*) terapan untuk operasional IT:

1. **Task Planner (Goal → Plan → Execute)**
   Alih-alih langsung mengeksekusi tindakan (reaktif), AI akan memiliki *Goal Engine* dan *Decision Engine*. Sistem akan memecah masalah menjadi *Task Planning* (DAG), menganalisis dependensi (Dependency Analysis), dan menghasilkan *Execution Plan* yang terstruktur.
2. **World Model (Enterprise Knowledge Graph)**
   Sistem tidak hanya memahami teks insiden, tetapi memahami topologi penuh perusahaan. AI akan memiliki representasi graf riil (Cabang → Switch → Server → ERP) sehingga saat node mati, korelasi dan *Blast Radius* dapat dikalkulasi secara topologis, bukan sekadar berbasis insiden.
3. **Knowledge Synthesis (Self-Improving Agent)**
   Fungsi RAG akan berevolusi dari sekadar membaca (*retrieval*) menjadi menulis (*synthesis*). Jika recovery berhasil, AI akan secara otonom merangkum draf SOP baru, mengirimkannya ke reviewer (Human), dan menjadikannya pengetahuan baru yang permanen.
4. **Meta-Cognition (Refleksi & Kalibrasi Diri)**
   Evaluasi mendalam terhadap kualitas dan akurasi keputusan AI. Melalui *Evolution Engine* dan *Arch Auditor*, sistem akan merenungkan: "Apakah diagnosis ini akurat?", "Apakah approval manusia ini bisa dipersingkat di masa depan?", dan menyesuaikan *threshold* keamanannya sendiri.
5. **Resource Optimizer (Cost-Benefit Analysis)**
   Keputusan mitigasi akan menyertakan analisis biaya operasional (downtime vs safety). AI akan menimbang strategi (contoh: *Restart Service* 10 detik vs *Reboot* 5 menit) untuk secara dinamis memilih jalur yang paling murah dan aman.

---

## ROADMAP IMPLEMENTASI — 6 FASE

> Setiap fase berdiri sendiri dan AMAN untuk production. Fase berikutnya hanya dimulai setelah fase sebelumnya stabil.

---

## FASE 1: Fondasi Runtime & Observabilitas
**Estimasi:** 2–3 minggu  
**Risiko:** Sangat Rendah (hanya penambahan, tanpa mengubah logika inti)  
**Status Prasyarat:** Semua tabel sudah ada ✅

### Step 1.1 — Global AI Runtime State Manager
**Tujuan:** Setiap worker Python memiliki status diri (`BOOTING`, `READY`, `DEGRADED`, `SAFE MODE`)

**File Baru:** `SERVER/python_ai_core/runtime/ai_runtime_state.py`
```python
# Enum + State Tracker yang ditulis ke Redis key: "ai_runtime:<worker_name>"
# BOOTING -> READY -> LEARNING | EXECUTING -> DEGRADED -> SAFE MODE
```
**Integrasi:** Di `ai_supervisor.py`, set state saat startup dan transisi.
**Database:** Tidak perlu tabel baru. Gunakan Redis key `ai_runtime:{worker}`.

### Step 1.2 — Enterprise Observability Fabric (Cognitive Trace)
**Tujuan:** Setiap keputusan AI menghasilkan trace yang bisa di-replay

**Tambahkan kolom ke `ai_audit_trail`:**
```sql
ALTER TABLE ai_audit_trail 
ADD COLUMN IF NOT EXISTS reasoning_trace JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS planning_trace  JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS policy_trace    JSONB DEFAULT '{}',
ADD COLUMN IF NOT EXISTS memory_trace    JSONB DEFAULT '{}';
```
**Integrasi:** `audit_logger.py` diperluas untuk menyimpan trace JSON.

### Step 1.3 — Internal API Contract Interface
**Tujuan:** Mengurangi coupling antar modul

**File Baru:** `SERVER/python_ai_core/api/internal_api.py`
```python
# Interface abstract BaseClass untuk:
# MemoryAPI, KnowledgeAPI, PlanningAPI, PolicyAPI, ExecutionAPI
# Semua modul yang sudah ada IMPLEMENT interface ini (wrapper)
```
**Catatan:** Modul lama tidak diubah, hanya dibungkus dengan Adapter Pattern.

---

## FASE 2: Recovery & Resilience Domain
**Estimasi:** 2–3 minggu  
**Risiko:** Rendah  
**Status Prasyarat:** `rollback_logs`, `replay_sessions`, `rollback_events` sudah ada ✅

### Step 2.1 — AI Task Checkpoint System
**Tujuan:** Setiap tugas learning/planning dapat di-resume jika worker crash

**File Baru:** `SERVER/python_ai_core/runtime/checkpoint_manager.py`
```python
# Checkpoint disimpan ke Redis dengan TTL 24 jam
# Format: {"task_id": ..., "state": ..., "progress": ..., "payload": ...}
# Methods: save_checkpoint(), load_checkpoint(), delete_checkpoint()
```

### Step 2.2 — Memperkuat Replay Engine sebagai Recovery Foundation
**Tujuan:** Memanfaatkan `replay_engine.py` yang SUDAH ADA untuk recovery AI tasks

**Perubahan:** Tambahkan method `resume_from_checkpoint(task_id)` di `replay_engine.py`.
**Database:** Reuse `replay_sessions` + tambah kolom `task_type` dan `is_learning_task`.

```sql
ALTER TABLE replay_sessions 
ADD COLUMN IF NOT EXISTS task_type    VARCHAR(50) DEFAULT 'incident',
ADD COLUMN IF NOT EXISTS is_ai_task   BOOLEAN DEFAULT FALSE,
ADD COLUMN IF NOT EXISTS checkpoint   JSONB DEFAULT '{}';
```

### Step 2.3 — SAFE MODE Handler
**Tujuan:** Jika worker gagal N kali, otomatis masuk SAFE MODE dan hanya accept `incident.triggered`

**Integrasi di:** `ai_supervisor.py` — tambahkan error counter dan fallback handler.

---

## FASE 3: Knowledge Domain — Unified Fabric & Freshness
**Estimasi:** 3–4 minggu  
**Risiko:** Sedang  
**Status Prasyarat:** `knowledge_vectors`, `knowledge_edges`, `learning_gate_policy` sudah ada ✅

### Step 3.1 — Knowledge Freshness Runtime
**Tujuan:** Setiap vektor pengetahuan memiliki metadata usia dan validitas

**Tambahkan kolom ke `knowledge_vectors`:**
```sql
ALTER TABLE knowledge_vectors 
ADD COLUMN IF NOT EXISTS status          VARCHAR(20) DEFAULT 'GOLDEN',
ADD COLUMN IF NOT EXISTS last_validated  TIMESTAMP  DEFAULT NOW(),
ADD COLUMN IF NOT EXISTS usage_count     INTEGER    DEFAULT 0,
ADD COLUMN IF NOT EXISTS success_count   INTEGER    DEFAULT 0,
ADD COLUMN IF NOT EXISTS failure_count   INTEGER    DEFAULT 0,
ADD COLUMN IF NOT EXISTS freshness_score FLOAT      DEFAULT 1.0,
ADD COLUMN IF NOT EXISTS source_doc      TEXT,
ADD COLUMN IF NOT EXISTS source_version  VARCHAR(50),
ADD COLUMN IF NOT EXISTS telemetry_version INTEGER DEFAULT 1;
```

### Step 3.2 — Knowledge Provenance Tracker
**Tujuan:** Setiap pengetahuan dapat dilacak asal-usulnya (CI/CD for Knowledge)

**Tabel Baru:** `knowledge_provenance`
```sql
CREATE TABLE IF NOT EXISTS knowledge_provenance (
    id              SERIAL PRIMARY KEY,
    vector_id       INTEGER REFERENCES knowledge_vectors(id),
    source_type     VARCHAR(50), -- 'RFC', 'VENDOR_DOC', 'INCIDENT', 'OPERATOR'
    source_url      TEXT,
    doc_version     VARCHAR(50),
    ingested_by     VARCHAR(100),
    approved_by     VARCHAR(100),
    status          VARCHAR(20) DEFAULT 'DRAFT', -- DRAFT, VALIDATED, GOLDEN, DEPRECATED
    created_at      TIMESTAMP DEFAULT NOW(),
    approved_at     TIMESTAMP
);
```

### Step 3.3 — Knowledge Worker Daemon
**Tujuan:** Mengaktifkan `seed_rag.py` menjadi background service

**File Baru:** `SERVER/python_ai_core/learning/knowledge_worker.py`
```python
# Subscribe NATS: "learning.knowledge.ingest"
# Payload: {"source": "RFC", "url": "...", "topic": "Redis"}
# Action: Parse -> Embed -> Save ke knowledge_vectors (status=DRAFT)
```

### Step 3.4 — Unified Knowledge Fabric (Abstraction Layer)
**Tujuan:** Satu titik akses untuk semua grafik (Knowledge, Evidence, Capability, World)

**File Baru:** `SERVER/python_ai_core/knowledge/knowledge_fabric.py`
```python
# class KnowledgeFabric:
#   query_knowledge(topic, context) -> unified results from vectors + edges
#   query_experience(incident_type) -> from ai_evidence_logs
#   query_world(device_id) -> from fleet_topology + dependency_map
```

---

## FASE 4: Execution Domain — Planning, Decision & Multi-Agent
**Estimasi:** 3–4 minggu  
**Risiko:** Sedang  
**Status Prasyarat:** `consensus_engine.py`, `policy_engine.py`, `trust_engine.py` sudah aktif ✅

### Step 4.1 — Goal Engine
**Tujuan:** AI memiliki tujuan operasional terukur

**Tabel Baru:** `ai_goals`
```sql
CREATE TABLE IF NOT EXISTS ai_goals (
    id            SERIAL PRIMARY KEY,
    goal_name     VARCHAR(100) NOT NULL,
    target_metric VARCHAR(100),  -- e.g., 'availability', 'mttr', 'false_positive_rate'
    target_value  FLOAT,
    current_value FLOAT,
    priority      INTEGER DEFAULT 5,
    is_active     BOOLEAN DEFAULT TRUE,
    updated_at    TIMESTAMP DEFAULT NOW()
);
INSERT INTO ai_goals (goal_name, target_metric, target_value, priority)
VALUES 
  ('High Availability',  'uptime_pct',         99.9, 1),
  ('MTTR Reduction',     'mttr_minutes',        30,   2),
  ('Knowledge Coverage', 'coverage_pct',        90,   3),
  ('Low False Positive', 'false_positive_rate', 0.05, 4);
```

**File Baru:** `SERVER/python_ai_core/planning/goal_engine.py`

### Step 4.2 — Decision Engine
**Tujuan:** AI memilih postur: Act / Learn / Wait / Ask Human

**File Baru:** `SERVER/python_ai_core/planning/decision_engine.py`
```python
# Input: confidence, risk, policy_result, resource_usage, incident_context
# Output: DecisionSignal.ACT | LEARN | WAIT | ESCALATE
# Wraps policy_engine.py — bukan menggantikannya
```

### Step 4.3 — Multi-Agent Negotiation Upgrade
**Tujuan:** Mengupgrade `consensus_engine.py` ke mode negosiasi

**Perubahan di:** `consensus_engine.py`
- Tambahkan `negotiate_round(agents: list, proposal: dict) -> NegotiationResult`
- Setiap agent diberi giliran menyampaikan keberatan sebelum konsensus final

---

## FASE 5: Evolution Domain — Learning Loop & Curiosity
**Estimasi:** 4–5 minggu  
**Risiko:** Sedang-Tinggi  
**Status Prasyarat:** Fase 1–4 selesai

### Step 5.1 — Curiosity Engine
**Tujuan:** Mendeteksi gap pengetahuan dari telemetri dan fleet data

**File Baru:** `SERVER/python_ai_core/learning/curiosity_engine.py`
```python
# Setiap 24 jam (scheduled via NATS):
# 1. Query cmdb_assets + fleet_devices untuk daftar teknologi aktif
# 2. Query knowledge_vectors untuk mencari yang tidak ada
# 3. Push gap ke NATS: "learning.knowledge.ingest"
```

### Step 5.2 — Digital Twin Foundation
**Tujuan:** Menggunakan `replay_engine.py` yang sudah ada sebagai Digital Twin

**Perubahan di:** `replay_engine.py`
- Tambahkan mode `DIGITAL_TWIN` yang menggunakan snapshot data produksi
- Hasil simulasi ditulis ke tabel baru `simulation_results`

```sql
CREATE TABLE IF NOT EXISTS simulation_results (
    id              SERIAL PRIMARY KEY,
    simulation_id   UUID DEFAULT gen_random_uuid(),
    incident_type   VARCHAR(100),
    knowledge_ids   INTEGER[],
    input_payload   JSONB,
    ai_response     TEXT,
    reasoning_trace JSONB,
    passed          BOOLEAN,
    score           FLOAT,
    created_at      TIMESTAMP DEFAULT NOW()
);
```

### Step 5.3 — Knowledge Supply Chain Pipeline
**Tujuan:** Pipeline otomatis dari `DRAFT` ke `GOLDEN` melalui validasi

**Flow:** `knowledge_worker ingests -> status=DRAFT -> curiosity validates -> simulation_results passed -> approval_queue -> Operator approves -> status=GOLDEN`

**Integrasi:** Gunakan tabel `approval_queue` yang SUDAH ADA.

### Step 5.4 — Continuous Architecture Auditor
**Tujuan:** Daemon yang secara periodik memeriksa drift sistem

**File Baru:** `SERVER/python_ai_core/evolution/arch_auditor.py`
```python
# Setiap 6 jam:
# 1. Bandingkan schema DB aktual dengan baseline snapshot
# 2. Periksa modul Python yang tidak aktif
# 3. Periksa NATS subjects yang tidak ada consumernya
# 4. Tulis laporan ke: system_audits (tabel yang SUDAH ADA)
```

---

## FASE 6: Meta-Cognition & AI OS Maturity
**Estimasi:** 4–6 minggu  
**Risiko:** Tinggi (perubahan pada inti reasoning)  
**Status Prasyarat:** Fase 1–5 selesai dan stabil

### Step 6.1 — Meta-Cognition Layer
**Tujuan:** AI mengevaluasi efisiensi nalar dan token usage-nya sendiri

**Tabel Baru:** `meta_cognition_logs`
```sql
CREATE TABLE IF NOT EXISTS meta_cognition_logs (
    id              SERIAL PRIMARY KEY,
    incident_id     INTEGER,
    worker_name     VARCHAR(100),
    reasoning_depth INTEGER,
    token_used      INTEGER,
    tool_accuracy   FLOAT,
    planning_cycles INTEGER,
    bias_detected   BOOLEAN DEFAULT FALSE,
    bias_type       VARCHAR(100),
    efficiency_score FLOAT,
    recommendations JSONB,
    evaluated_at    TIMESTAMP DEFAULT NOW()
);
```

**File Baru:** `SERVER/python_ai_core/cognition/meta_cognition.py`

### Step 6.2 — World Model (dari Data yang Sudah Ada)
**Tujuan:** Aktivasi `fleet_topology`, `dependency_map`, `device_dependencies` sebagai World Model

**File Baru:** `SERVER/python_ai_core/knowledge/world_model.py`
```python
# class WorldModel:
#   get_blast_radius(device_id) -> reuse blast_radius_engine.py
#   get_dependency_chain(service) -> query fleet_topology + dependency_map
#   get_critical_path() -> query network_paths
```
**Catatan:** Tidak ada tabel baru — semua menggunakan tabel yang sudah ada!

### Step 6.3 — AI Health Monitor Dashboard
**Tujuan:** Menampilkan kesehatan kognitif AI di Dashboard

**API Baru di Dashboard Server:**
```
GET /api/ai/health          -> Runtime state semua workers
GET /api/ai/cognition       -> Meta-cognition metrics 
GET /api/ai/knowledge/fresh -> Knowledge freshness scores
GET /api/ai/learning/queue  -> Status antrian pembelajaran
```

### Step 6.4 — Evolution Engine (Human-in-the-Loop)
**Tujuan:** AI mengusulkan peningkatan dirinya sendiri, Human approves

**Flow:**
1. Arch Auditor menemukan drift → tulis ke `system_audits`
2. Evolution Engine membuat proposal → masuk `approval_queue` dengan tipe `EVOLUTION`
3. Operator menyetujui/menolak via Dashboard
4. Jika disetujui → `evolution_sandbox` (test di Docker env terisolasi) → merge

---

## Tabel Ringkasan Implementasi

| Fase | Nama | Modul Baru | Tabel Baru | DB Migration | Durasi | Risiko |
|------|------|-----------|------------|--------------|--------|--------|
| 1 | Runtime & Observabilitas | `ai_runtime_state.py`, `checkpoint_manager.py`, `internal_api.py` | - | ALTER `ai_audit_trail` | 2–3 minggu | 🟢 Sangat Rendah |
| 2 | Recovery & Resilience | `checkpoint_manager.py` | - | ALTER `replay_sessions` | 2–3 minggu | 🟢 Rendah |
| 3 | Knowledge Domain | `knowledge_worker.py`, `knowledge_fabric.py` | `knowledge_provenance` | ALTER `knowledge_vectors` | 3–4 minggu | 🟡 Sedang |
| 4 | Execution Domain | `goal_engine.py`, `decision_engine.py` | `ai_goals` | - | 3–4 minggu | 🟡 Sedang |
| 5 | Evolution Domain | `curiosity_engine.py`, `arch_auditor.py` | `simulation_results` | - | 4–5 minggu | 🟠 Sedang-Tinggi |
| 6 | Meta-Cognition | `meta_cognition.py`, `world_model.py` | `meta_cognition_logs` | - | 4–6 minggu | 🔴 Tinggi |

---

## Aturan Implementasi (Wajib Dipatuhi)

1. **Setiap file baru diletakkan di subfolder** (`runtime/`, `learning/`, `planning/`, `knowledge/`, `evolution/`, `cognition/`)
2. **Setiap migration menggunakan `IF NOT EXISTS`** — aman dijalankan berulang kali
3. **Tidak ada logika incident engine yang disentuh pada Fase 1–4** — zero risk ke production
4. **Setiap fitur baru harus daftar ke NATS Subject baru**, bukan mengubah subject yang ada
5. **Feature flag via `learning_gate_policy`** — fitur baru bisa dimatikan tanpa restart

---

## Mulai dari Mana? (Rekomendasi Eksekusi Pertama)

Langkah PERTAMA yang paling aman dan berdampak langsung adalah **Step 1.2**: menambahkan kolom `reasoning_trace`, `planning_trace` ke `ai_audit_trail`. Ini memungkinkan setiap insiden yang terjadi hari ini sudah menghasilkan data observabilitas yang akan menjadi fondasi semua fase berikutnya.

**Command migrasi awal:**
```bash
docker exec osi-postgres psql -U postgres -d osi_system -c "
ALTER TABLE ai_audit_trail ADD COLUMN IF NOT EXISTS reasoning_trace JSONB DEFAULT '{}';
ALTER TABLE ai_audit_trail ADD COLUMN IF NOT EXISTS planning_trace  JSONB DEFAULT '{}';
ALTER TABLE ai_audit_trail ADD COLUMN IF NOT EXISTS policy_trace    JSONB DEFAULT '{}';
ALTER TABLE ai_audit_trail ADD COLUMN IF NOT EXISTS memory_trace    JSONB DEFAULT '{}';
"
```
