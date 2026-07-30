# OSI Enterprise AIOps Platform - Final Blueprint v1.0

## 1. Executive Summary
Sistem OSI AIOps telah berevolusi dari sekadar jembatan *telemetry* reaktif menjadi sebuah **Enterprise Cognitive Reliability Platform** berstandar industri (setara Dynatrace/Datadog Watchdog). Sistem ini bertindak murni sebagai **Diagnostic & Recommendation Engine** dengan batasan otonomi ketat (Level 0 - Observe Only), menempatkan *Engineer* manusia sebagai pemegang kendali mutlak (Human-In-The-Loop).

---

## 2. Arsitektur Ingestion & Telemetry (Lapisan Go Backend)
Berjalan sebagai benteng pertama yang mengamankan, membersihkan, dan menstandarisasi data sebelum diserahkan ke mesin AI.

*   **Agent 05 (v2.1.0):** Terpasang di Node Linux dan Windows. Membaca *Resource* (CPU/Memory) dan *Network Hooks* (Port 10000) dengan verifikasi HMAC.
*   **Netdata Machine Learning (Anomaly Webhook):** Integrasi kecerdasan *Time-Series*. Netdata memantau metrik secara *sub-second* dan mendeteksi anomali mikroskopis. Hasil deteksi dikirim ke *endpoint* khusus `http://<SERVER>:18800/api/v1/netdata` untuk diparsing oleh `netdata_parser.go`.
*   **Dynamic Topology Discovery (eBPF/netstat):** Agen mengirimkan peta konektivitas (*established connections*) ke `http://<SERVER>:18800/api/v1/topology` untuk diparsing oleh `topology_parser.go`. Ini memungkinkan AI mengenali perubahan infrastruktur secara otomatis.
*   **Syslog & UDP Aggregator (`syslog_aggregator.go`):** Listener UDP (Port 1514) yang secara proaktif menangkap log _enterprise_ (Mikrotik, Nginx, Kubernetes, AD) tanpa mengganggu *traffic HTTP* utama.
*   **Enterprise Log Parser (`enterprise_log_parser.go`):** Secara pintar mendeteksi sumber *log* dan memberikannya OSI Layer Tag (Contoh: `PostgreSQL` = Layer 6, `Nginx` = Layer 7).
*   **OpenTelemetry Injection (`telemetry_trace.go`):** Setiap sinyal (log/metric/event/netdata) kini dibubuhi 16-byte `TraceID` dan 8-byte `SpanID` berstandar W3C agar dapat dilacak murni secara *end-to-end*.

---

## 3. Cognitive Pipeline (Lapisan Python AI Core)
Mesin utama pemrosesan analitik menggunakan konsep **Cognitive Pipeline** bertahap (Sprints G, H, I, J). AI tidak lagi meraba, melainkan menghitung menggunakan matematika *graph*.

### A. Sprint G1 - Correlation Engine
*   **Fungsi:** Menghentikan banjir peringatan (*Alert Fatigue*).
*   **Logika:** Mengelompokkan semua pesan dari Ingestion Server dalam jendela waktu (Time Window ±60 detik) dan Service Dependency Map, menyatukannya ke dalam satu `Correlated Incident ID`.

### B. Sprint G2 & G3 - Service Dependency Map (SDM)
*   **Fungsi:** Melacak topologi infrastruktur perusahaan secara *Self-Healing*.
*   **Logika:** Menyusun *Directed Acyclic Graph* (NetworkX). Menggunakan *update_dynamic_topology* untuk memasukkan penemuan koneksi dari Netstat/eBPF. Digunakan AI untuk mencari `Sink Node` terdalam sebagai *Root Cause* sejati (Misal: PostgreSQL tumbang menyebabkan Nginx ikut melapor *error*).

### C. Sprint H - Playbook Intelligence & Bayesian Confidence
*   **Fungsi:** Menyeleksi strategi *recovery* (Playbook) secara probabilitas matematika.
*   **Logika (`bayesian_network.py`):** Menggantikan tebakan statis LLM. Memakai teorema Naive Bayes ($P(Cause | Evidence)$) berdasarkan kekuatan *Evidence* vs *Historical Success Rate*. Playbook yang memiliki skor probabilitas tertinggi dan *downtime* terendah akan direkomendasikan.

### D. Sprint I - Predictive Operations & Digital Twin
*   **Fungsi:** Simulasi pra-eksekusi (*Dry-Run*).
*   **Logika (`digital_twin.py`):** Sebelum AI memberikan rekomendasi (contoh: *Restart Core Switch*), ia akan mensimulasikannya ke atas SDM. *Digital Twin* secara otomatis menghitung *Blast Radius* ("30 Services akan terputus") dan memperingatkan Engineer akan `risk_of_failure = CRITICAL`.

### E. Sprint J - Recommendation Quality Scoring
*   **Fungsi:** Sistem grading (*scorecard*) bagi hasil kerja AI.
*   **Logika (`recommendation_scoring.py`):** Menampilkan skor kepercayaan gabungan (dari *Evidence, SDM, Knowledge, Playbook*) agar Engineer langsung paham apakah rekomendasi ini patut dipercaya (Skor 96%) atau butuh investigasi lanjut (Skor 40%).

---

## 4. Keamanan & Evaluasi (Human-In-The-Loop)
Keseluruhan sistem ini terikat mutlak pada doktrin "Safety First".

1.  **Zero Autonomy Enforcement:** Segala sinyal telemetri disuntikkan parameter `requires_hitl: true`.
2.  **Schema Enforcement (`incident_schema.py`):** Output LLM dikunci mutlak menggunakan format 25-Point Pydantic Schema. Format salah = *Pipeline Rejection*.
3.  **Continuous Evaluation (`cognitive_kpi_engine.py`):** AI yang mengaudit dirinya sendiri. *Daemon* ini secara rutin menghitung `Mean Time To Detect (MTTD)`, `Mean Time To Resolve (MTTR)`, `False Positive Rate`, dan persentase AI di-*Approve* oleh manusia. Digunakan untuk perhitungan ROI investasi AIOps.

---

## 5. End-to-End Server Flow (Alur Kerja Keseluruhan)

Untuk memahami operasi OSI AIOps secara utuh, berikut adalah alur kronologis sejak masalah muncul hingga diselesaikan:

1.  **Sensory Layer (Data Generation):** Agen 05 mendeteksi anomali pada koneksi `netstat`, atau *Netdata ML* membangkitkan `Anomaly Rate` yang tinggi akibat *I/O disk spike*. Data ditembakkan via JSON Webhook ke Port 18800.
2.  **Ingestion Layer (Data Standarization):** Go Server menerima JSON. File `netdata_parser.go` dan `topology_parser.go` mengubah data tersebut menjadi `TelemetryItem` berstandar OSI. `TraceID` ditambahkan, status ditetapkan menjadi `"requires_hitl": true`. Sinyal dilempar ke antrean NATS.
3.  **Cognitive Layer (Reasoning):** Python AI Core mendengarkan NATS. `Correlation Engine` menggabungkan *alert* Netdata dengan *alert* log aplikasi (Nginx). `Service Dependency Map` memvalidasi hubungan keduanya. Model `Bayesian` menghasilkan prediksi *Root Cause* dengan *Confidence Score* 98%. AI memilih solusi perbaikan dari repositori pengetahuan.
4.  **Simulation Layer (Safety):** Solusi disimulasikan oleh `Digital Twin`. Ia memproyeksikan *Blast Radius* apabila solusi tersebut dijalankan.
5.  **Approval Layer (HITL):** Paket rekomendasi lengkap dikirim ke NOC Dashboard / ChatOps (Telegram/Slack). Manusia (*Engineer*) memvalidasi simulasi AI. Jika logis dan aman, *Engineer* menekan tombol **[APPROVE]**.
6.  **Execution & Evaluation Layer:** Sinyal validasi kembali ke Go Server. Go mengirim instruksi eksekusi jarak jauh melalui *Port* 10000 ke Agen 05 (terenkripsi HMAC). Masalah teratasi, dan `KPI Engine` mencatat penurunan durasi MTTR untuk bulan ini.

---

## Kesimpulan
OSI AIOps bukan lagi sekadar pemantau log. Ini adalah sistem pengenalan masalah prediktif, dengan arsitektur penalaran kasual (*Causal Reasoning*) dan evaluasi keamanan terintegrasi yang sepenuhnya menyatu dengan ekosistem enterprise. Status sistem saat ini **STABIL** dan **SIAP SKALA**.
