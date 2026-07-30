# 📡 CARA KERJA SISTEM REAL-TIME & DASHBOARD n8n ENTERPRISE AI NOC
## Complete Enterprise AI Lifecycle — n8n Workflow Automation Canvas (n8n Engine v3.0)

**Dokumen:** `CARA_KERJA_SISTEM_REALTIME_N8N_DASHBOARD.md`  
**Versi:** `3.0.0-PRODUCTION-READY`  
**Klasifikasi:** `INTERNAL TECHNICAL REFERENCE`  
**Penulis:** `Enterprise AIOps Architecture Team`  

---

## 📌 OVERVIEW SINGKAT

Sistem ini adalah **Platform AIOps Enterprise Generasi ke-5** yang beroperasi secara **real-time 24/7** untuk:
- Mendeteksi insiden IT otomatis dari ribuan perangkat (PC Kasir, Server, Gateway, Container)
- Mendiagnosis akar masalah menggunakan **Causal DAG + LLM AI Reasoning**
- Mengeksekusi remediasi otomatis dengan **Human-in-the-Loop (HITL) Approval**
- Menjamin keamanan, kepatuhan regulasi, dan dapat diaudit secara forensik

Dashboard n8n Canvas **bukan sekadar visualisasi** — ia adalah **peta hidup real-time** dari seluruh aliran data, keputusan, dan eksekusi sistem.

---

## 🏗️ ARSITEKTUR 10-LAYER ENTERPRISE

```
[L0: Klien/Operator] → [L1: Web UI Dashboard] → [L2: API Gateway] → [L3: Go Core Backend]
        ↕                                                                      ↕
[L9: Dashboard Analytics] ← [L8: Integrasi Eksternal] ← ... ← [L4: Python AI Core]
                                                                      ↕
                              [L7: Agen Windows/Linux] ← [L5: NATS/PostgreSQL] ← [L6: Docker/n8n]
```

| Layer | Nama | Fungsi Utama |
|---|---|---|
| **L0** | Klien & Operator | NOC Human Operator, Telegram Bot, Chrome Extension |
| **L1** | Web UI Dashboard | 40+ Panel Real-Time (React-like Vanilla JS, 60 FPS WebSocket) |
| **L2** | API Gateway | Gin HTTP Router, Auth Middleware, Rate Limiter |
| **L3** | Go Core Backend | REST API Engine, NATS Publisher, Relay Dispatcher |
| **L4** | Python AI Core | 26-Node Complete AI Cognitive & Governance Engine |
| **L5** | Broker & Database | NATS JetStream (<5ms), PostgreSQL 15, Redis Cache |
| **L6** | Infrastruktur | Docker Compose, n8n Workflow Engine, Netdata |
| **L7** | Agen Endpoint | Windows Agent (Go), Linux Agent (Go), Idempotency Manager |
| **L8** | Integrasi Eksternal | LDAP/AD, Kafka, DNS, Kubernetes |
| **L9** | Analisis Dashboard | Semua panel monitoring dan analytics |

---

## 🌐 DASHBOARD n8n WORKFLOW AUTOMATION CANVAS

### Cara Membuka & Menggunakan Dashboard

1. Akses portal web di `http://[SERVER_IP]:8080`
2. Pilih menu **"Complete Enterprise AI Lifecycle — n8n Workflow Automation Canvas"** pada sidebar navigasi kiri (tab `AI Lifecycle & Live Topology Flow`).
3. Kanvas SVG interaktif otomatis render **26 node** yang saling terhubung dengan animasi partikel berwarna-warni.

### Kontrol Kanvas

| Tombol/Kontrol | Fungsi |
|---|---|
| **Scroll Mouse** | Zoom In/Out pada kanvas |
| **Drag Kanvas** | Pan (geser tampilan kanvas) |
| **Klik Node** | Buka Node Inspector (lihat payload real-time input/output) |
| **Execute Workflow Test** | Mensimulasikan run workflow end-to-end |
| **Live Stream Motion** | Mengaktifkan/menonaktifkan animasi partikel aliran data |
| **Simpan Tata Letak** | Menyimpan posisi node ke localStorage |
| **Tes Timeout/Crash** | Mensimulasikan node crash (node menyala MERAH dengan badge ⚠️ 504 SLA) |
| **Reset Posisi** | Mengembalikan layout ke posisi standar |
| **Fit** | Zoom-to-Fit seluruh kanvas dalam viewport |
| **Rapikan** | Auto-arrange node menggunakan algoritma hierarki level |

---

## 🔵 26 NODE LENGKAP: FUNGSI & ALUR DATA

### LEGEND WARNA NODE:

| Warna | Layer/Kategori |
|---|---|
| 🔵 Biru | Client Layer (L0) & Web/Gateway (L1) |
| 🟦 Cyan | Web / Gateway / Infrastruktur |
| 🟣 Ungu/Purple | AI Core & RAG Engine (L4) |
| 🟠 Oranye | NATS / Persistence (L5) |
| 🟢 Hijau | Agents & Recovery (L7) |
| 🔴 Merah | External Integrations / Security Guards |

---

### GRUP 1: TELEMETRI MASUK (Sumber Data Real-Time)

#### 🟦 `L1_Telem` — Real-Time Telemetry Stream Receiver
- **Apa yang dilakukan:** Menerima data telemetri real-time dari seluruh agen endpoint (CPU, RAM, Disk, Network, Process, GPU, Container metrics) melalui WebSocket 60 FPS.
- **Input:** Paket telemetri JSON dari `L7_WinAgent` dan `L7_LinuxAgent` via NATS JetStream.
- **Output:** Data terstruktur diteruskan ke `L4_FeatureStore`, `L4_Observability`, dan `L4_SymptomCluster`.
- **Frekuensi:** Setiap **500ms** (2x per detik per perangkat).

#### 🟢 `L7_WinAgent` — Windows Endpoint Agent
- **Apa yang dilakukan:** Agen Go yang berjalan di setiap PC Windows/Server, mengumpulkan 40+ metrik sistem, dan mengirimnya ke NATS JetStream.
- **Keamanan:** Menggunakan `TraceID`, `SpanID`, `CorrelationID`, dan `KeyVersion` (rotasi kunci 7 hari).
- **Failover:** Terhubung ke kluster 3-node NATS (`nats://127.0.0.1:4222,4223,4224`).
- **Idempotency:** Setiap perintah remediasi diperiksa UUID-nya untuk mencegah eksekusi ganda.

#### 🟢 `L7_LinuxAgent` — Linux Endpoint Agent
- **Apa yang dilakukan:** Sama dengan Windows Agent tetapi untuk server Linux (Ubuntu/Debian/CentOS).
- **Tambahan:** Mendukung metrik container Docker, systemd service status, dan cgroup resource monitoring.

---

### GRUP 2: KEAMANAN GERBANG PERTAMA (Security Input Gate)

#### 🔴 `L4_AdversarialGuard` — Adversarial Prompt Injection & Jailbreak Guard
- **Apa yang dilakukan:** Pertahanan lapis pertama sebelum prompt operator atau input otomatis dikirim ke LLM.
- **Mekanisme 3-Tahap Normalisasi:**
  1. `urllib.parse.unquote()` → Mendecode URL encoding (`%49%67%6e%6f%72%65...` → `Ignore...`)
  2. `base64.b64decode()` → Mendecode Base64 (`SWdub3Jl...` → `Ignore...`)
  3. `unicodedata.normalize('NFKC', text)` → Menyeragamkan Unicode Homoglyph (huruf Cyrillic `І` → Latin `I`)
- **Setelah normalisasi:** Regex `BLOCKED_PATTERNS` dijalankan melawan seluruh variant.
- **Input:** `L1_UI` (operator chat) & `L0_Telegram` (bot commands)
- **Output:** Prompt aman diteruskan ke `L4_PromptRegistry`. Serangan diblokir → alert Telegram SRA.

#### 🔴 `L4_OutputGuard` — LLM Response PII Redaction Guard *(embedded dalam AdversarialGuard module)*
- **Apa yang dilakukan:** Setelah LLM menghasilkan respons, **sebelum** respons dikirim ke Dashboard UI atau Telegram, `L4_OutputGuard` memindai output.
- **Redaksi Otomatis:**
  - IP Internal `192.168.x.x` / `10.x.x.x` → `[REDACTED_INTERNAL_IP]`
  - Password plaintext → `password=[REDACTED_SECRET_TOKEN]`
  - Nomor Kartu Kredit (PAN) → `[REDACTED_PCI_PAN]`
- **Audit:** Setiap redaksi dicatat ke `ai_audit_trail` dengan status `OUTPUT_PII_AUTO_REDACTED`.

---

### GRUP 3: KOGNISI AI & ANALISIS (AI Reasoning Engine)

#### 🟣 `L4_SymptomCluster` — Divergent Symptom Cluster & Novelty Engine
- **Apa yang dilakukan:** Mengelompokkan symptom anomali masuk dan menghitung **Novelty Distance Score** dibandingkan dengan histori insiden 30 hari terakhir.
- **Output Kritis:** Jika skor novelty > 0.85 → status `NOVEL_UNSEEN_ANOMALY` → AI mengaktifkan jalur analisis divergent (bukan mengandalkan histori).
- **Input:** `L1_Telem`
- **Output:** `L4_Router`

#### 🟣 `L4_Router` — 2-Step Hybrid Intent Classifier & Router
- **Apa yang dilakukan:** Mengklasifikasikan intent insiden menggunakan **2-langkah hibrida**: Rule-based cepat dulu, LLM hanya jika diperlukan (hemat 95% kuota LLM).
- **Routing:** Mengarahkan ke `L4_RemediationMatrix`, `L4_GoldenRules`, `L4_LocalRules`, atau `L4_ModelRegistry`.

#### 🟣 `L4_DAG` — Dynamic Causal Bayesian Network (DAG Engine)
- **Apa yang dilakukan:** Membangun graf kausalitas **(Causal Directed Acyclic Graph)** dari telemetri untuk menentukan akar masalah (Root Cause Analysis).
- **Contoh:** CPU Spike → Memory Pressure → Spooler Deadlock (bukan hanya symptom terakhir).
- **Drift Detector:** Jika **KL-Divergence** distribusi metrik hari ini vs 7 hari lalu > 0.30 → memicu **Emergency DAG Refresh** otomatis (di luar jadwal cron 02.00 WIB).

#### 🟣 `L4_HypothesisGenerator` — Alternative Bayesian Hypothesis Testing
- **Apa yang dilakukan:** Menghasilkan 3 hipotesis akar masalah alternatif (H1, H2, H3) berdasarkan probabilitas Bayesian.
- **Output:** Hipotesis diurutkan berdasarkan posterior probability ke `L4_EntropyUncertainty`.

#### 🟣 `L4_EntropyUncertainty` — Shannon Entropy Uncertainty Engine
- **Apa yang dilakukan:** Mengukur tingkat ketidakpastian AI menggunakan Shannon Entropy.
  - `U < 0.20` → **Single Confident Action** (AI sangat yakin, langsung eksekusi)
  - `U 0.20–0.45` → **Dual Alternative** (AI menawarkan 2 pilihan ke operator)
  - `U > 0.45` → **Multiple Options / Eskalasi ke HITL**

#### 🟣 `L4_TrustCalibrator` — Model Trust Calibration (ECE Evaluator)
- **Apa yang dilakukan:** Mengukur **Expected Calibration Error (ECE)** real-time dari histori `(Predicted_Confidence, Actual_Outcome)`.
- **Formula:** $ECE = \sum_{b=1}^{B} \frac{|Bin_b|}{N} |acc(Bin_b) - conf(Bin_b)|$
- **Alert:** Jika `ECE > 0.15` (AI terlalu percaya diri atau terlalu ragu) → alert ke SRA & rekomendasi **Platt Scaling** recalibration.
- **Input:** `L4_Reflector` (hasil retrospeksi pasca-insiden)
- **Output:** Sinyal kalibrasi ke `L4_Planner` untuk menyesuaikan threshold.

---

### GRUP 4: PERENCANAAN & KATALOG AKSI (Planning & Action Catalog)

#### 🟣 `L4_PromptRegistry` — AdaptPrompt Dynamic Prompt Engine
- **Apa yang dilakukan:** Menyuntikkan konteks dinamis ke dalam prompt LLM sebelum dikirim: `{jam_operasional}`, `{level_severity}`, `{histori_5_insiden_terakhir}`, `{topologi_jaringan}`.
- **Hasil:** Prompt AI jauh lebih kontekstual dan akurat dibandingkan prompt statis.

#### 🟢 `L4_GoldenRules` — 5 Golden Rules Enforcer (Prioritas #1 Katalog DB)
- **Apa yang dilakukan:** Mengunci 5 Aturan Emas Kelayakan Produksi sebelum LLM mengeksekusi apapun:
  1. **Rule #1 (PRIORITAS TERTINGGI):** LLM hanya boleh memilih Action ID dari `preapproved_action_catalog` database — TIDAK BOLEH mengirim raw shell command (`rm -rf`, `DROP TABLE`).
  2. **Rule #2:** Gerbang Ganda (Policy PDP + Verifier) wajib dilewati sebelum Executor.
  3. **Rule #3:** Setiap aksi harus punya Rollback Plan & Health Check Probe.
  4. **Rule #4:** Semua keputusan wajib bisa dijelaskan dan diaudit (Explainability + Audit Trail).
  5. **Rule #5:** Model AI baru hanya boleh deploy ke produksi jika akurasi replay > model lama.
- **Katalog Aksi yang Disetujui (Pre-Approved):**
  | Action ID | Nama Aksi | Kategori |
  |---|---|---|
  | `ACT_RESTART_SPOOLER` | Restart Windows Print Spooler Service | PRINT_SPOOLER |
  | `ACT_FLUSH_DNS` | Flush Local DNS Resolver Cache | NETWORK |
  | `ACT_DRAIN_REPLICA` | Graceful Read Replica Connection Drain | DATABASE |
  | `ACT_SCALE_POD` | Scale Out Microservice Pod Replicas | CONTAINER |
  | `ACT_RESTART_KASIR_SERVICE` | Restart POS Kasir Main Service | POS_HARDWARE |
  | *(Tambahan dari Dashboard)* | Tersimpan ke PostgreSQL `preapproved_action_catalog` | Custom |

#### 🟣 `L4_Planner` — AI Planning Engine (Otak Perencana)
- **Apa yang dilakukan:** Memformulasikan **3 Skenario Tindakan (Plan A, B, C)** lengkap dengan estimasi risiko, durasi, dan probabilitas sukses.
- **Input:** `L4_DAG`, `L4_Counterfactual`, `L4_BlastRadius`, `L4_GoldenRules`, `L4_PromptRegistry`
- **Output:** Rencana aksi multi-langkah dikirim ke `L4_PDP_Governance` untuk evaluasi kebijakan.

#### 🔴 `L4_PDP_Governance` — Policy Decision Point (PDP v2.1.0)
- **Apa yang dilakukan:** Mengevaluasi rencana aksi multi-langkah (*Multi-Step Workflow Plan*) melalui 7 sub-modul:
  1. **CommandNormalizer** — Normalisasi whitespace & casing
  2. **PolicyEvaluator** — Cocokkan dengan profil kebijakan industri
  3. **ContextEvaluator** — Evaluasi Maintenance Window, Asset Criticality (P0–P3), RBAC Role
  4. **RiskScorer** — Hitung skor risiko $R \in [0.0, 1.0]$
  5. **ComplianceEngine** — Evaluasi workflow end-to-end
  6. **AuditLogger** — Tulis metadata ke `pdp_audit_logs`
  7. **HITLRouter** — Route ke antrian persetujuan jika $R > Threshold$
- **Profil Kebijakan Industri (v2.1.0):**
  | Profil | HITL Risk Threshold | Aturan Khusus |
  |---|---|---|
  | **RETAIL (POS Kasir)** | R ≥ 0.30 | Larangan `FORCE_REBOOT_POS_KASIR_ACTIVE` |
  | **FINANCE (PCI-DSS)** | R ≥ 0.20 | Larangan `EXPORT_UNENCRYPTED_TRANSACTIONS` |
  | **HEALTHCARE (HIPAA)** | R ≥ 0.25 | Larangan `EXPORT_RAW_PATIENT_RECORDS` |
  | **MANUFACTURING (SCADA)** | R ≥ 0.15 | Larangan `PLC_FORCE_STOP`, `OVERRIDE_SAFETY_RELAY` |

---

### GRUP 5: VERIFIKASI GERBANG GANDA (Double-Gate Verification)

#### 🟦 `L4_Verifier` — Execution Verification Engine (Double-Gate Quality Check)
- **Apa yang dilakukan:** Memverifikasi rencana aksi dalam 2 tahap:
  - **Pre-Execution Gate:** Validasi kebijakan, batas risiko, dependensi, dan blast radius SEBELUM perintah dikirim ke agen.
  - **Post-Execution Gate:** Verifikasi bahwa metrik kesehatan pulih ke baseline normal SETELAH eksekusi.
- **Koneksi:** Menerima clearance dari `L4_PDP_Governance` dan `L4_GOV`.

#### 🟣 `L4_GOV` — AI Safety & Governance Layer
- **Apa yang dilakukan:** Lapisan keamanan AI yang menegakkan aturan eksplisit: tidak boleh eksekusi lebih dari 3 aksi remediasi bersamaan, tidak boleh restart service tier-1 saat jam peak-traffic.

#### 🟣 `L4_RegulatoryGuard` — Regulatory Compliance Guard
- **Apa yang dilakukan:** Memeriksa kepatuhan terhadap **ISO 27001**, **PCI-DSS POS v4**, dan **UU PDP Indonesia** sebelum data sensitif boleh diproses atau dikirim keluar.

---

### GRUP 6: EKSEKUSI & PEMULIHAN (Execution & Recovery)

#### 🟢 `L4_Executor` — AI Execution Engine (Pengawal Eksekusi Otonom)
- **Apa yang dilakukan:** Mengirimkan perintah remediasi yang sudah terverifikasi ke agen endpoint secara bertahap (*staged rollout*), memantau kesehatan real-time, dan memicu **auto-rollback** jika eksekusi gagal.
- **Input:** Wajib melewati `L4_GoldenRules` → `L4_Verifier` terlebih dahulu.
- **Output:** Perintah via `L3_Relay` → NATS → `L7_WinAgent` / `L7_LinuxAgent`.

#### 🟢 `L4_RollbackManager` — Automated Rollback Manager
- **Apa yang dilakukan:** Dipicu otomatis jika `L4_Executor` atau `L4_Verifier` melaporkan kegagalan. Mengeksekusi **Rollback Plan** yang telah dipasangkan oleh `ActionRollbackHealthChecker`.
- **Contoh Pasangan Rollback:**
  | Aksi Utama | Rollback Plan | Health Check Probe |
  |---|---|---|
  | `ACT_RESTART_SPOOLER` | `net start spooler` | `CHECK_WINDOWS_SERVICE_RUNNING(spooler)` — timeout 10s |
  | `ACT_FLUSH_DNS` | `ipconfig /registerdns` | `CHECK_DNS_RESOLVER_PING(8.8.8.8)` — timeout 5s |
  | `ACT_DRAIN_REPLICA` | `ALTER SYSTEM SET...` | `CHECK_POSTGRES_READ_REPLICA_SYNC()` — timeout 15s |
  | `ACT_SCALE_POD` | `kubectl scale --replicas=1` | `CHECK_K8S_POD_HEALTH_PROBE()` — timeout 20s |

---

### GRUP 7: PEMBELAJARAN & FEEDBACK (Learning & Feedback Loop)

#### 🟡 `L4_FeedbackCollector` — Feedback Collector & RLHF Loop
- **Apa yang dilakukan:** Mengumpulkan umpan balik Approve/Reject dari operator NOC melalui HITL, lalu menggunakannya sebagai dataset fine-tuning RLHF/DPO untuk meningkatkan model AI.

#### 🟡 `L4_ContinuousReinforcement` — Continuous Feedback Reinforcement Engine
- **Apa yang dilakukan:** Sliding window 10 insiden terakhir per agen. Jika *fail rate* tinggi → menerapkan **penalty decay** 0.5x pada bobot rekomendasi agen tersebut.
- **Input:** `L4_Reflector` (retrospeksi pasca-insiden)
- **Output:** Bobot terbarui ke `L4_Planner`.

#### 🟣 `L4_Reflector` — AI Reflector & Retrospection Engine
- **Apa yang dilakukan:** Setelah insiden selesai, `L4_Reflector` melakukan retrospeksi: *Mengapa berhasil/gagal? Apa yang bisa ditingkatkan?* Hasilnya disimpan ke Cognitive Memory DB (`L5_SQL_Cog`).

---

### GRUP 8: LAPISAN KEAMANAN (Security Layers)

#### 🔴 `L4_SecretManager` — Zero-Trust Secret Manager Vault
- **Apa yang dilakukan:** Menyimpan dan mendistribusikan secret (API key, DB password, NATS credentials) dengan rotasi kunci 7-hari (*Dual-Key Grace Period*). Tidak ada plain-text secret yang boleh ada di konfigurasi file.

#### 🔴 `L4_SafetyLayer` — Zero-Hallucination Safety Net
- **Apa yang dilakukan:** Lapisan akhir sebelum `L4_Executor` yang memastikan AI tidak pernah mengeksekusi perintah destruktif bahkan jika LLM "berhalusinasi" dan menghasilkan output tidak terduga.

---

### GRUP 9: INFRASTRUKTUR & BROKER (Infrastructure)

#### 🟠 `L5_NATS` — NATS JetStream Message Broker
- **Apa yang dilakukan:** Bus event pusat berperforma ultra-tinggi.
- **Latensi:** < 5ms per pesan
- **Kapasitas:** Mendukung jutaan pesan per detik
- **Fitur:** Persistent streams (replay setelah reconnect), consumer groups, dan dead-letter queue (DLQ).

#### 🟠 `L5_SQL_Inc` — PostgreSQL 15 (Incidents & Telemetry DB)
- **Apa yang dilakukan:** Menyimpan seluruh data insiden, telemetri terpartisi, approval logs, PDP audit logs, dan action catalog.
- **Tabel Kunci:**
  | Tabel | Isi |
  |---|---|
  | `incidents` | Data insiden lengkap |
  | `incident_states` | Status siklus hidup insiden |
  | `pdp_audit_logs` | Audit keputusan Policy Decision Point |
  | `preapproved_action_catalog` | Katalog aksi yang disetujui (editable dari Dashboard) |
  | `post_incident_debriefs` | Umpan balik operator NOC pasca-insiden |
  | `ai_audit_trail` | Seluruh keputusan AI dengan explainability |

#### 🟠 `L5_Redis` — Redis Hybrid Cache
- **Apa yang dilakukan:** Cache keputusan AI cepat (TTL 5 menit untuk idempotency check), context carry-forward ring buffer (5 insiden terakhir per perangkat), dan drift detection metric snapshots.

---

### GRUP 10: ANALISIS DASHBOARD (Dashboard Analytics)

#### 🟦 `L9_IncidentRCA` — Incident Triage & Causal RCA Panel (`#p-rca`)
- **Panel Dashboard:** Menampilkan hasil analisis **5 Why** dan **Evidence Chain** secara real-time.
- **Fitur Baru — Form Cognitive Debriefing (`#p-debrief`):**
  - Operator NOC mengisi umpan balik pasca-insiden: *"Apakah RCA AI Benar?"* + *"Faktor Eksternal/Kontekstual"*.
  - Data tersimpan ke `post_incident_debriefs` sebagai sinyal RLHF berkualitas tinggi.

#### 🟦 `L9_AICognition` — AI Panel (`#p-ai`)
- **Panel Dashboard:** Menampilkan KPI real-time AI: Jumlah AI aktif, rata-rata confidence, akurasi klasifikasi model lokal RF, dan riwayat prediksi.

---

## 🔄 ALUR DATA END-TO-END: DARI INSIDEN HINGGA RESOLUSI

### Skenario: PC Kasir-01 mengalami Printer Spooler Deadlock

```
[1] L7_WinAgent di PC-Kasir-01 mendeteksi:
    CPU: 87%, RAM: 94%, Spooler service: DEADLOCK
    → Kirim paket NATS dengan TraceID + SpanID + CorrelationID

[2] L5_NATS menerima dan mendistribusikan ke:
    → L1_Telem (Dashboard update real-time)
    → L3_GoCore (proses dan simpan ke L5_SQL_Inc)

[3] L4_AdversarialGuard:
    → Normalisasi input (URL Decode, Base64, NFKC Unicode)
    → Scan regex BLOCKED_PATTERNS → CLEARED_SAFE
    → Teruskan ke L4_PromptRegistry

[4] L4_SymptomCluster:
    → Bandingkan dengan 30 hari histori
    → Novelty Score: 0.32 (KNOWN_PATTERN)
    → Route ke L4_Router

[5] L4_Router (2-Step Hybrid Intent Classifier):
    → Step 1 (Rule-Based): Pattern = "spooler" + CPU > 80% → Intent = PRINTER_SPOOLER_DEADLOCK
    → Confidence 92.4% → Skip LLM, langsung route
    → Route ke L4_GoldenRules & L4_DAG

[6] L4_GoldenRules (Rule #1 Check):
    → Cek database preapproved_action_catalog
    → "ACT_RESTART_SPOOLER" → ADA & DISETUJUI ✓
    → Teruskan ke L4_Planner

[7] L4_DAG (Causal Root Cause):
    → Bangun causal path: Spooler Service → RPC Call → RAM Pressure → Deadlock
    → Drift Detector: KL-Divergence = 0.18 < 0.30 → Tidak perlu emergency refresh
    → Kirim ke L4_Planner

[8] L4_Planner (AI Planning Engine):
    → Formulasi 3 Plan:
      Plan A: ACT_RESTART_SPOOLER (Risk: LOW, Duration: 15s, Success: 94%)
      Plan B: ACT_FLUSH_DNS + ACT_RESTART_SPOOLER (Risk: MEDIUM, Duration: 45s)
      Plan C: Eskalasi Manual NOC (Risk: HIGH-bypass, Duration: Manual)
    → Kirim Plan A ke L4_PDP_Governance

[9] L4_PDP_Governance (Policy Decision Point):
    → CommandNormalizer: "ACT_RESTART_SPOOLER" → normalized ✓
    → ContextEvaluator: Maintenance Window = FALSE, Criticality = P1, Role = NOC_OPERATOR
    → RiskScorer: R = 0.15 (< RETAIL threshold 0.30) → AUTO-CLEAR
    → ComplianceEngine: Plan A = COMPLIANT ✓
    → Decision: AUTOMATIC_CLEARANCE_APPROVED
    → Audit log → L5_SQL_Inc (pdp_audit_logs)

[10] L4_Verifier (Pre-Execution Gate):
    → Cek blast radius: 1 perangkat, 1 service → LOW
    → Cek dependency: DB-Prod tidak terpengaruh ✓
    → Cek trust score: 0.92 (> 0.75 threshold) ✓
    → GATE CLEARED → Teruskan ke L4_Executor

[11] L4_Executor (Execution Engine):
    → Dispatch perintah ke L3_Relay → L5_NATS → L7_WinAgent (PC-Kasir-01)
    → Kirim: { action: "ACT_RESTART_SPOOLER", command: "net stop spooler && net start spooler" }
    → Monitor respons 10 detik

[12] L7_WinAgent (PC-Kasir-01) menerima & eksekusi:
    → net stop spooler → OK
    → net start spooler → OK
    → Health Check: CHECK_WINDOWS_SERVICE_RUNNING(spooler) → RUNNING ✓
    → Kirim ACK ke NATS: execution_status = "SUCCESS"

[13] L4_Verifier (Post-Execution Gate):
    → Konfirmasi: CPU turun dari 87% ke 23%
    → Konfirmasi: RAM turun dari 94% ke 61%
    → Konfirmasi: Spooler service = RUNNING
    → POST_EXECUTION_VERIFIED ✓

[14] L4_Closure:
    → Tutup insiden: status = RESOLVED, resolved_at = NOW()
    → Kirim notifikasi ke L0_Telegram: "✅ PC-Kasir-01 — Spooler Deadlock RESOLVED in 28 detik"

[15] L4_OutputGuard (Response Sanitization):
    → Scan respons LLM: tidak ada IP internal, tidak ada password bocor
    → Status: CLEARED_NO_LEAKS ✓
    → Tampilkan di Dashboard #p-chat dan Telegram

[16] L4_Reflector (Retrospeksi):
    → Simpan ke Cognitive Memory: { flag: PRINTER_SPOOLER_DEADLOCK, action: ACT_RESTART_SPOOLER, outcome: SUCCESS, duration: 28s }
    → Update L4_TrustCalibrator: record_prediction_outcome(confidence=0.924, correct=True)
    → Update L4_ContinuousReinforcement: sliding_window += 1, success

[17] L4_AdaptiveRAG (Ingest Snippet):
    → Simpan resolved case sebagai RAG snippet dengan bobot tinggi
    → Next insiden serupa: akurasi prediksi meningkat
```

**Total MTTR: < 30 Detik** ⚡

---

## 🔒 KEAMANAN & PERINTAH YANG DILARANG

### Perintah yang Dilarang Dikirim ke LLM atau Sistem

| Kategori | Contoh Perintah Terlarang | Alasan Larangan |
|---|---|---|
| **OS Destruction** | `rm -rf /`, `format c:`, `mkfs.ext4` | Penghapusan sistem masif |
| **Database Erasure** | `DROP DATABASE`, `DROP TABLE`, `TRUNCATE TABLE` tanpa WHERE | Kehilangan data permanen |
| **Shutdown Paksa** | `sudo shutdown`, `init 0`, `poweroff` | Matikan server tanpa graceful drain |
| **Script Injeksi** | `curl ... \| sh`, `wget ... \| bash` | Eksekusi kode tidak terverifikasi |
| **Audit Bypass** | `DISABLE_AUDIT_LOGGING`, `BYPASS_SSL_CERTIFICATE` | Pelanggaran ISO 27001 / PCI-DSS |
| **POS Berbahaya** | `FORCE_REBOOT_POS_KASIR_ACTIVE` | Mematikan kasir saat transaksi aktif |
| **Prompt Injection** | `"Ignore previous instructions"` (plaintext, Base64, URL, Unicode) | Upaya kontrol LLM oleh penyerang |

### Data Sensitif yang Tidak Boleh Masuk ke LLM

| Kategori | Contoh | Tindakan Otomatis |
|---|---|---|
| **PAN / Nomor Kartu** | 4111-1111-1111-1111 | → `[REDACTED_PCI_PAN]` |
| **Password Plaintext** | `password="Secret123"` | → `password=[REDACTED_SECRET_TOKEN]` |
| **JWT/Bearer Token** | `Bearer eyJhbGci...` | → `[REDACTED_SECRET_TOKEN]` |
| **IP Internal** | `192.168.1.100` | → `[REDACTED_INTERNAL_IP]` |
| **NIK / Data Pribadi** | No. KTP, No. HP | → `[REDACTED_PII_USER]` |

---

## 📊 DASHBOARD PANELS YANG TERHUBUNG

| Panel ID | Nama Panel | Data Source Real-Time |
|---|---|---|
| `#p-ai_lifecycle_topology` | **n8n Canvas (26 Node)** | `AiLiveFlow.nodes` + `AiLiveFlow.edges` + WebSocket particle animation |
| `#p-rca` | **Incident Triage & Causal RCA** | `/api/rca?incident_id=X` + Chain of Thought JSONB |
| `#p-debrief` | **Post-Incident Cognitive Debriefing** | Form → `POST /api/debrief` → `post_incident_debriefs` DB |
| `#modal-sop-viewer` | **SOP Protocol Viewer** | `/api/sop/detail?incident_id=X` → DOs/DONTs Matrix + Action Log |
| `#p-ai` | **AI Cognition Panel** | `/api/ai/stats` → Confidence, ECE, Model Performance |
| `#p-approval_queue` | **HITL Approval Queue** | WebSocket push → Approve/Reject 1-klik |
| `#p-fleet` | **Fleet Monitoring** | Netdata + Agent telemetry real-time |
| `#p-chat` | **AI Chat / NOC Relay** | Go Core ChatEngine → OutputGuard → UI |

---

## 🚀 CARA MEMULAI SISTEM (Quick Start)

```bash
# 1. Jalankan seluruh stack dengan Docker Compose
cd /home/it-itsm/AI/incident-analysis
docker compose up -d

# 2. Verifikasi Go Core Backend berjalan
curl http://localhost:8080/api/health

# 3. Verifikasi Python AI Core Engine
cd SERVER/python_ai_core
python3 -c "from governance.five_golden_rules_engine import golden_rules_engine; print('AI Engine: READY')"

# 4. Buka Dashboard
# Browser → http://[SERVER_IP]:8080
# → Menu: "AI Lifecycle & Live Topology Flow"
# → Kanvas n8n v3.0 akan otomatis load dengan 26 node dan live particle streaming
```

---

## ✅ CHECKLIST KELAYAKAN PRODUKSI (Production Readiness Checklist)

- [x] **Rule 1:** LLM tidak langsung eksekusi shell command → Pre-Approved Action Catalog DB ✓
- [x] **Rule 2:** Double-Gate Policy PDP + Verifier sebelum Executor ✓
- [x] **Rule 3:** Setiap aksi punya Rollback Plan + Health Check Probe ✓
- [x] **Rule 4:** Semua keputusan tersimpan di audit trail dengan explainability ✓
- [x] **Rule 5:** Model baru divalidasi historical replay sebelum deploy ✓
- [x] **Security:** Multi-stage input normalization (URL/Base64/Unicode) ✓
- [x] **Security:** LLM output PII redaction sebelum kirim ke UI/Telegram ✓
- [x] **Availability:** NATS 3-node cluster failover + Agent reconnect logic ✓
- [x] **Observability:** OpenTelemetry traces + Prometheus golden signals ✓
- [x] **HITL:** Approval timeout P0=120s / P1=300s → auto-escalate Telegram ✓

---

*Dokumen ini dibuat secara otomatis dari sesi arsitektur Enterprise AIOps Platform.*  
*Last Updated: 2026-07-27 | Version: 3.0.0-PRODUCTION-READY*
