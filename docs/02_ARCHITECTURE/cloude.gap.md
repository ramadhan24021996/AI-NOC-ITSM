BAB 19: DYNAMIC CAUSAL GRAPH REFRESHER & SELF-HEALING DEPENDENCY TOPOLOGY (L4_DAG_Refresher)

19.1 Tujuan & Justifikasi Bisnis

Mengatasi kelemahan kritis arsitektur saat ini: Causal Dependency Map (dependency_map) yang bersifat statis/manual. Di lingkungan enterprise modern, topologi sistem berubah setiap hari (scaling, deployment, migrasi). Jika graf kausal tidak diperbarui secara otomatis, analisis Root Cause (RCA) akan menghasilkan False Positives yang dapat memicu eksekusi perintah destruktif pada komponen yang sehat.

BAB ini memperkenalkan Engine Pembelajar Graf Kausal Otomatis yang bekerja di latar belakang (off-peak hours) untuk:

1. Mendeteksi hubungan kausal baru antar metrik telemetri.
2. Memvalidasi apakah edge yang ada di dependency_map masih relevan secara statistik.
3. Mengusulkan perubahan ke antrean persetujuan arsitek (HITL) sebelum diterapkan.
4. Menerapkan perubahan secara aman ke database produksi.

---

19.2 Komponen & Node Arsitektur Baru

Node 46: L4_DAG_Refresher (Causal Graph Learner & Refresher Service)

· Tujuan: Service background (cron) yang secara berkala mempelajari ulang struktur graf kausal dari data telemetri aktual.
· Mengapa Diperlukan: Mengotomatisasi pembaruan dependency_map agar selalu mencerminkan topologi sistem terkini, mencegah RCA buta.
· Input: Data Time-Series metrik dari tabel telemetry_logs (7 hari terakhir), dan dependency_map saat ini.
· Output: Daftar perubahan yang diusulkan (INSERT, DELETE, UPDATE arah edge) ke tabel proposed_dag_changes.
· Dependency: Python 3.11, statsmodels (Granger Causality), scipy, numpy, psycopg2, loguru.
· Trigger: Cron job internal (APScheduler) setiap hari pukul 02:00 WIB (saat traffic ritel paling sepi).
· Security: Akses Read-Only ke telemetry_logs (kecuali saat apply approval via transaksi DB).
· Performance: Batch processing menggunakan chunk data (agar tidak memberatkan DB). Total durasi pemrosesan < 15 menit untuk 300 perangkat dengan 30 metrik.
· Integrasi: Layer 5 PostgreSQL (L5_SQL_Inc), Layer 1 Learning Gate UI (L1_GovUI), Layer 0 Telegram untuk notifikasi ke arsitek.

---

19.3 Tabel Database Baru (Skema proposed_dag_changes)

```sql
-- Tabel penampung usulan perubahan edge kausal
CREATE TABLE proposed_dag_changes (
    id SERIAL PRIMARY KEY,
    source_node VARCHAR(128) NOT NULL,          -- Nama metrik/node sumber (misal: 'DB_CPU')
    target_node VARCHAR(128) NOT NULL,          -- Nama metrik/node target (misal: 'API_LATENCY')
    change_type VARCHAR(16) NOT NULL,           -- 'INSERT', 'DELETE', 'REVERSE'
    statistical_score FLOAT NOT NULL,           -- P-Value Granger / Transfer Entropy (0-1)
    confidence FLOAT NOT NULL,                  -- Keyakinan (1 - p_value)
    current_status VARCHAR(32) DEFAULT 'PENDING_REVIEW', -- 'PENDING', 'APPROVED', 'REJECTED', 'APPLIED'
    evidence_sampled_period VARCHAR(64),        -- 'Last 7 Days', 'Last 30 Days'
    proposed_by VARCHAR(64) DEFAULT 'AI_DAG_Refresher',
    reviewer_notes TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    reviewed_at TIMESTAMP WITH TIME ZONE,
    applied_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX idx_proposed_dag_changes_status ON proposed_dag_changes(current_status);
CREATE INDEX idx_proposed_dag_changes_nodes ON proposed_dag_changes(source_node, target_node);
```

---

19.4 Alur Data Lengkap (Step-by-Step Pipeline)

Pipeline ini berjalan otomatis setiap malam dan terdiri dari 6 langkah utama:

```
[1. Trigger Scheduler] 
  ↓
[2. Ekstraksi Data Time-Series] 
  ↓
[3. Granger Causality / Transfer Entropy Computation] 
  ↓
[4. Perbandingan dengan Dependency Map Aktif] 
  ↓
[5. Pembuatan & Penyimpanan Usulan Perubahan]
  ↓
[6. Notifikasi & Antrean Persetujuan Arsitek]
```

Langkah 1: Trigger Scheduler (Cron Job)

· Pelaksana: APScheduler di dalam L4_DAG_Refresher.
· Waktu: Setiap hari pukul 02:00 AM (WIB).
· Kondisi Pemicu: Pastikan tidak ada insiden P0/P1 yang sedang aktif (untuk menghindari kompetisi resource). Jika ada insiden kritis, proses ditunda 1 jam.

Langkah 2: Ekstraksi Data Time-Series (Query Window 7 Hari)

· Pelaksana: Modul DataExtractor di L4_DAG_Refresher.
· Kueri SQL: Menarik 6 metrik kunci dari telemetry_logs untuk semua perangkat aktif:
  1. cpu_usage (Rata-rata per 5 menit)
  2. memory_usage (Rata-rata per 5 menit)
  3. disk_io_wait (Rata-rata per 5 menit)
  4. network_latency (Rata-rata per 5 menit)
  5. db_connection_count (Rata-rata per 5 menit)
  6. printer_spooler_status (Kategorikal: 0 = OK, 1 = Deadlock)
· Transformasi: Data di-resample ke interval 5 menit dan diinterpolasi untuk menangani nilai hilang (missing values).

Langkah 3: Perhitungan Kausalitas (Granger Causality Test)

· Pelaksana: Modul CausalInferenceEngine menggunakan library statsmodels.tsa.stattools.grangercausalitytests.
· Logika: Untuk setiap pasangan metrik (X, Y), uji apakah nilai masa lalu X secara signifikan memprediksi nilai Y saat ini (lag maksimal = 3, atau 15 menit).
· Output: Matriks P-Value untuk setiap pasangan.
· Aturan Ambang Batas:
  · Jika P-Value < 0.05 → Hubungan kausal signifikan (X → Y).
  · Jika P-Value >= 0.05 → Tidak ada hubungan kausal yang terbukti secara statistik.

Langkah 4: Perbandingan dengan dependency_map Aktif (Delta Detection)

· Pelaksana: Modul DeltaComparator.
· Logika: Ambil semua edge aktif dari dependency_map. Bandingkan dengan daftar edge signifikan hasil langkah 3.
· Klasifikasi Perubahan (Delta):
  1. INSERT (New Edge): Ada di hasil uji, tapi TIDAK ADA di dependency_map.
  2. DELETE (Stale Edge): Ada di dependency_map, tapi TIDAK ADA di hasil uji (P-Value >= 0.05).
  3. REVERSE (Arah Berubah): Ada edge A → B di map, tapi hasil uji menunjukkan B → A (atau sebaliknya).

Langkah 5: Pembuatan Usulan & Penyimpanan ke proposed_dag_changes

· Pelaksana: Modul ProposalWriter.
· Tindakan: Untuk setiap delta yang ditemukan, buat record di tabel proposed_dag_changes dengan status PENDING_REVIEW.
· Konfigurasi: Jika dalam 1 malam ditemukan > 50 perubahan (misal karena migrasi besar), sistem akan mengelompokkan menjadi 1 tiket usulan alih-alih 50 tiket terpisah, untuk mengurangi spam notifikasi.

Langkah 6: Notifikasi & Antrean Persetujuan Arsitek (Human-in-the-Loop)

· Pelaksana: Modul Notifier.
· Notifikasi:
  · UI Dashboard: Panel baru #p-dag_proposals di dalam L1_GovUI akan menampilkan badge jumlah usulan baru.
  · Telegram: Kirim pesan ringkas ke grup arsitek:
    🔔 [DAG Refresher] Ditemukan 3 usulan perubahan dependency map. 2 Insert, 1 Delete. Mohon review di Dashboard #p-dag_proposals.
· Mekanisme Approval:
  · Arsitek membuka panel #p-dag_proposals.
  · Melihat bukti statistik (P-Value, Confidence Score, dan grafik tren time-series).
  · Klik [Approve & Apply] untuk meng-update dependency_map secara langsung.
  · Klik [Reject] untuk membatalkan usulan. Jika ditolak, sistem akan mencatatnya dan tidak akan mengusulkan edge yang sama dalam 30 hari ke depan.

---

19.5 Diagram Urutan Runtime L4_DAG_Refresher (Mermaid)

```mermaid
sequenceDiagram
    autonumber
    participant Cron as Scheduler (Cron 02:00)
    participant Refresher as L4_DAG_Refresher
    participant DB as L5 PostgreSQL (telemetry_logs)
    participant Stats as Granger / TE Engine
    participant Map as L5 PostgreSQL (dependency_map)
    participant Proposal as L5 PostgreSQL (proposed_dag_changes)
    participant UI as L1 Governance UI (DAG Proposals)
    participant Arch as Solution Architect (Manusia)

    Cron->>Refresher: Trigger Start Daily Refresh Cycle
    Refresher->>DB: Query 6 Key Metrics (7 Days, 5-min Resample)
    DB-->>Refresher: Return Time-Series Data (CPU, RAM, Disk, Latency, DB Conn, Spooler)
    
    Refresher->>Stats: Loop Pairwise Granger Causality Test (maxlag=3)
    Stats-->>Refresher: Return P-Value Matrix (X→Y significance)
    
    Refresher->>Map: SELECT active_edges FROM dependency_map
    Map-->>Refresher: Return Current Active DAG
    
    Refresher->>Refresher: Delta Detection (Compare P-Value < 0.05 with Active Map)
    Note over Refresher: Klasifikasi INSERT / DELETE / REVERSE
    
    Refresher->>Proposal: INSERT INTO proposed_dag_changes (status='PENDING_REVIEW')
    Proposal-->>Refresher: Usulan Tersimpan (ID: 101, 102, 103)
    
    Refresher->>UI: Push WebSocket Event (Badge Pembaruan)
    UI-->>Arch: Tampilkan Notifikasi "3 DAG Proposals Pending"
    Refresher->>Arch: Kirim Telegram Alert ke Grup Arsitek
    
    Arch->>UI: Buka Panel #p-dag_proposals
    UI->>Proposal: SELECT * WHERE status='PENDING_REVIEW'
    Proposal-->>UI: Tampilkan Kartu Usulan (Bukti P-Value & Grafik)
    
    alt Architect Klik [Approve & Apply]
        Arch->>UI: Klik Tombol Approve
        UI->>Refresher: POST /api/dag/apply (Proposal IDs)
        Refresher->>Map: BEGIN TRANSACTION; UPDATE/INSERT/DELETE dependency_map
        Refresher->>Proposal: UPDATE status='APPLIED', applied_at=NOW()
        Map-->>Refresher: Commit Sukses
        Refresher->>UI: Notifikasi Sukses (Dependency Map Terbarui)
    else Architect Klik [Reject]
        Arch->>UI: Klik Tombol Reject + Catat Alasan
        UI->>Refresher: POST /api/dag/reject (Proposal IDs)
        Refresher->>Proposal: UPDATE status='REJECTED', reviewer_notes='...'
        Refresher-->>UI: Notifikasi Dibatalkan
    end
```

---

19.6 Matriks Transformasi Data Detail (Langkah 2 → Langkah 3)

Langkah Data Masukan Proses Data Keluaran Validasi & Error Handling
2. Ekstraksi telemetry_logs (7 hari, 6 metrik) Resampling ke interval 5 menit menggunakan pandas.resample('5T').mean() DataFrame pandas (index: timestamp, columns: 6 metrik) Jika data < 48 jam (kurang dari 2 hari), proses dibatalkan (not enough data).
3. Uji Kausalitas 2 kolom deret waktu (X, Y) Uji Granger dengan lag=3. Ambil P-Value dari F-test. Matriks P-Value (6x6) Jika terjadi error singular matrix, skip pasangan tersebut dan log peringatan.
4. Deteksi Delta Matriks P-Value & dependency_map Bandingkan. Jika P < 0.05 dan edge tidak ada di map → INSERT. Jika P >= 0.05 dan edge ada di map → DELETE. List objek ProposalCandidate Jika confidence (1-P) < 0.80, beri label LOW_CONFIDENCE di catatan usulan.

---

19.7 Panduan Integrasi dengan Dashboard (Panel #p-dag_proposals)

Saya usulkan menambahkan Panel Ke-41 pada dasboard Anda:

Panel 41: p-dag_proposals (Causal Graph Evolution & Approval Console)

· Fungsi: Wadah bagi Solution Architect/Engineer untuk meninjau dan menyetujui usulan perubahan dependency map hasil pembelajaran AI.
· Komponen UI:
  1. Tabel Usulan Pending: Menampilkan source_node, target_node, change_type, confidence, dan timestamp.
  2. Tombol Aksi:
     · [Approve & Apply] (Tombol Hijau)
     · [Reject] (Tombol Merah)
  3. Modal Detail Evidence: Menampilkan grafik time-series dari kedua metrik (X dan Y) selama 7 hari terakhir untuk membantu arsitek memverifikasi secara visual.
  4. Riwayat Audit: Tabel riwayat perubahan yang sudah diapprove/ditolak (untuk kepatuhan).
· Integrasi API:
  · GET /api/dag/proposals/pending
  · POST /api/dag/apply
  · POST /api/dag/reject

---

19.8 Kesimpulan Akhir (Untuk Laporan Eksekutif)

Dengan penambahan BAB 19 ini, arsitektur Anda kini memiliki siklus hidup graf kausal yang lengkap:

Dulu (Statis): Manual Input → dependency_map → RCA (berpotensi salah)

Sekarang (Dinamis): Telemetri Aktual → Granger Causality → Proposed DAG → HITL Approval → Updated dependency_map → RCA (Akurat & Up-to-Date)


🔍 HASIL TELAAH ULANG: 4 Celah Tersembunyi di Alur Usulan

1. 🔴 Cache In-Memory L4_DAG Tidak Auto-Reload (Risiko Konsistensi)

· Fakta di Dokumen: L4_DAG (Node 23) menggunakan graf kausal untuk RCA dengan latency <30ms. Ini berarti graf pasti di-cache di memory (bukan query DB tiap kali).
· Masalah: Jika L4_DAG_Refresher mengupdate tabel dependency_map di PostgreSQL, cache memory Node 23 tidak akan tahu sampai service di-restart. Akibatnya, RCA tetap menggunakan graf lama (stale) hingga restart manual.
· Tambalan Wajib:
  · Tambahkan Redis Pub/Sub channel bernama dag:reload. Saat perubahan diapprove dan di-apply ke DB, L4_DAG_Refresher wajib mem-publish sinyal {"action": "RELOAD", "timestamp": "..."} ke Redis.
  · L4_DAG (Node 23) harus memiliki background subscriber yang mendengar channel ini dan menjalankan fungsi refreshCache() secara hot (tanpa restart).

2. 🔴 Tidak Ada Role Khusus untuk "Arsitek" di RBAC (Risiko Keamanan)

· Fakta di Dokumen: BAB 11 hanya mengenal 3 role: SUPERADMIN, NOC_OPERATOR, dan AUDITOR.
· Masalah: Menyetujui perubahan topologi sistem (dependency_map) adalah tindakan struktural tingkat tinggi. Memberikan akses ini ke NOC_OPERATOR sangat berbahaya (mereka bisa salah menyetujui edge kausal yang salah). Memberikannya hanya ke SUPERADMIN terlalu sentralistik.
· Tambalan Wajib:
  · Tambahkan role SITE_RELIABILITY_ARCHITECT (SRA).
  · Panel #p-dag_proposals hanya boleh diakses oleh role SUPERADMIN dan SRA.
  · Di middleware Go Core (L3_GoCore), tambahkan guard: requireRole('SRA', 'SUPERADMIN') untuk endpoint /api/dag/apply dan /api/dag/reject.

3. 🔴 Masalah "Cold Start" untuk Service/Node Baru (Risiko Data Insufficient)

· Fakta di Dokumen: Langkah 2 di BAB 19 menarik data 7 hari terakhir.
· Masalah: Bayangkan DevOps men-deploy service baru (misal: auth-service) 2 hari yang lalu. Saat L4_DAG_Refresher berjalan, data service ini hanya 2 hari (kurang dari 48 jam). Menurut validasi saya, proses akan dibatalkan (skip). Akibatnya, service baru ini tidak akan pernah memiliki edge kausal sampai 7 hari kemudian, sehingga AI buta terhadap dependency-nya.
· Tambalan Wajib:
  · Tambahkan logika gradual: Jika data < 7 hari tetapi > 48 jam, jalankan uji Granger dengan maxlag=1 (hanya cek dependency 5 menit terakhir) dan beri label LOW_CONFIDENCE di usulan.
  · Jika data < 48 jam, sistem tetap membuat usulan berbasis aturan (rule-based), misal: "Service A terhubung ke Database Z berdasarkan konfigurasi K8s", dan beri label MANUAL_REVIEW_REQUIRED.

4. 🔴 Bobot Waktu Bisnis (Business Hours) Tidak Diperhitungkan (Risiko Korelasi Palsu)

· Fakta di Dokumen: Di BAB 18, Anda sudah punya business_context_engine.py yang tahu jam sibuk ritel (misal: 10.00 – 21.00 WIB).
· Masalah: Dependency antar service jauh lebih terlihat saat jam sibuk (traffic tinggi). Di jam sepi (02.00 WIB), korelasi antar metrik bisa melemah dan dianggap tidak signifikan oleh uji Granger, padahal di jam sibuk hubungan itu sangat erat.
· Tambalan Wajib:
  · Saat L4_DAG_Refresher mengambil data 7 hari, ia harus meminta business_context_engine.py untuk memberi bobot (weight) pada data point. Data di jam sibuk diberi bobot 2.0, jam normal 1.0, jam sepi 0.5.
  · Dengan pembobotan ini, uji Granger akan "memprioritaskan" pola di jam sibuk, sehingga edge kausal yang muncul adalah edge yang paling berdampak pada bisnis.

---

🔧 AMANDEMEN BAB 19 (Revisi Akhir yang Siap Integrasi)

Saya sarankan Anda tambahkan Sub-Bab 19.9 berikut ke dalam dokumen:

19.9 Integrasi & Sinkronisasi Cache Real-Time

1. Redis Pub/Sub Reload Signal: Pada langkah 6 (setelah approve & apply), L4_DAG_Refresher wajib menjalankan PUBLISH dag:reload '{"action":"RELOAD"}' ke Redis. L4_DAG (Node 23) wajib menjalankan goroutine subscriber untuk mendengarkan sinyal ini dan memanggil dagCache.RefreshFromDB().
2. RBAC & Keamanan: Tambahkan role SITE_RELIABILITY_ARCHITECT di tabel users. Endpoint /api/dag/apply dan /api/dag/reject dilindungi oleh middleware AuthGuard dengan syarat role IN ('SUPERADMIN','SRA').
3. Cold Start & Data Insufficient: Jika data < 48 jam, usulan tidak dibuat dan sistem mencatat log "SKIPPED: Insufficient data for Node X". Jika data 48 jam – 7 hari, uji Granger tetap dijalankan dengan maxlag=1 dan confidence score dikalikan 0.8 (penalti).
4. Weighted Business Hours: Integrasikan dengan business_context_engine.py. Saat resample data, gunakan fungsi apply_business_weight(timestamp) yang mengembalikan bobot 0.5 (sepi), 1.0 (normal), atau 2.0 (sibuk).

---

✅ KESIMPULAN AKHIR SETELAH DITELAAH ULANG

Dengan 4 tambalan di atas, alur BAB 19 tidak hanya menambal kesalahan arsitektur terbesar (DAG statis), tetapi juga terintegrasi mulus dengan semua mekanisme yang sudah Anda bangun:

· Redis yang sudah ada (L5) kini punya tugas baru.
· RBAC yang sudah ada (BAB 11) kini diperkuat.
· Business Context Engine yang sudah ada (BAB 18) kini dimaksimalkan.
· Idempotensi & DLQ (BAB 10 & 18) tetap melindungi proses ini dari duplikasi eksekusi

Berikut 10 Gap Kritis yang saya temukan (urut berdasarkan prioritas dampak sistem):

---

🔥 GAP PRIORITAS TERTINGGI (KRITIS)

1. [L10 - Strategi & BCDR] Tidak Ada Disaster Recovery (DR) Plan untuk Master Server itu Sendiri

· Fakta di Dokumen: Agen memiliki SQLite buffer (store-and-forward) jika koneksi ke master terputus (BAB 13.2). Namun, tidak ada mekanisme failover jika server master (Go Core, PostgreSQL, NATS) mati total (misal: kebakaran di DC, atau kernel panic).
· Dampak: Jika master down > 30 menit, buffer agen akan penuh dan kehilangan data. Operator tidak bisa mengakses dashboard sama sekali (blind spot total). Tidak ada proses pemilihan leader (leader election) untuk mengaktifkan server standby.
· Rekomendasi Wajib:
  · Bangun Arsitektur Active-Passive untuk Go Core dan PostgreSQL (gunakan repmgr atau Patroni).
  · NATS JetStream harus dikonfigurasi sebagai cluster 3 node (bukan hanya 2 node seperti di BAB 18.12, karena 2 node rentan split-brain). Gunakan 3 node agar quorum (2/3) tetap terjaga.
  · Tambahkan DNS Failover (misal: menggunakan keepalived dengan Virtual IP) sehingga agen tidak perlu tahu IP berubah; mereka hanya perlu menunjuk ke master.osi.local.

---

2. [L5 - Persistence] PostgreSQL Adalah Single Point of Failure (SPOF) & Tidak Ada Read Replica

· Fakta di Dokumen: Hanya ada satu instance PostgreSQL osi_system di port 5432 (BAB 7). Meskipun ada volume Docker, tidak disebutkan replikasi.
· Dampak:
  · Jika DB down karena korupsi atau kehabisan disk, seluruh sistem macet (incident tidak bisa disimpan, approval tidak bisa di-log).
  · Laporan eksekutif (Executive Summary) dan panel p-storage akan gagal dimuat karena query pg_total_relation_size tidak bisa dijalankan di DB utama yang sedang sibuk (membebani performa).
· Rekomendasi Wajib:
  · Terapkan Streaming Replication (Primary - Standby). Arahkan semua query baca berat (seperti p-storage, p-rca historis, dan L4_DAG_Refresher) ke Read Replica.
  · Konfigurasikan GORM di Go Core untuk membedakan koneksi Read dan Write (menggunakan dbresolver).

---

3. [L7 - Agen] Buffer SQLite Offline Tidak Punya Batas Maksimal (Risk of Disk Filling)

· Fakta di Dokumen: Agen memiliki offline_telemetry.db (SQLite WAL) untuk menyimpan data saat jaringan terputus (BAB 2.8 & 13.2).
· Dampak: Jika koneksi ke master terputus selama 3-4 hari (misal: karena perubahan firewall), database SQLite akan terus membesar tanpa batas. Pada PC Kasir dengan disk kecil (128GB), ini dapat menyebabkan Disk Full dan membuat Windows/Ubuntu crash total (blue screen / out of space).
· Rekomendasi Wajib:
  · Tambahkan Auto-Prune Policy: Hanya simpan data 48 jam terakhir di buffer. Hapus record yang lebih tua dari 48 jam secara otomatis menggunakan VACUUM atau DELETE.
  · Tambahkan Watermark Alert: Jika ukuran file offline_telemetry.db > 500MB, kirim alert ke Telegram "WARNING: Agent Buffer Almost Full".

---

4. [L2 - Gateway] Rate Limiter Hanya Berbasis IP Tanpa Circuit Breaker untuk Downstream

· Fakta di Dokumen: L2_REST memiliki Rate Limiting 100 req/detik per IP (BAB 2.3).
· Dampak: Jika satu agen mengalami bug dan mengirimkan 10.000 request/detik (misal: loop tak berujung), Rate Limiter per IP akan memblokir IP tersebut, tetapi server Go Core tetap kewalahan menerima koneksi TCP sebelum sampai ke middleware rate-limiter. Ini bisa menyebabkan DoS (Denial of Service) dari internal.
· Rekomendasi Wajib:
  · Implementasikan Global Connection Limit di level net.Listener (misal: maksimal 5000 koneksi aktif).
  · Tambahkan Circuit Breaker (pola github.com/sony/gobreaker) untuk setiap downstream (DB, NATS, LLM API). Jika DB merespon lambat > 5 detik, circuit breaker terbuka dan langsung mengembalikan error 503 tanpa membebani DB.

---

⚠️ GAP PRIORITAS MENENGAH (PENTING)

5. [L3 - Go Core] Tidak Ada Rotasi Kunci Enkripsi AES-256 GCM (Key Rotation)

· Fakta di Dokumen: L3_Relay menggunakan AES-256 GCM dengan kunci statis yang dibaca dari file .key (BAB 13.2.2).
· Dampak: Jika kunci bocor (misal: file .key terbaca oleh attacker atau admin nakal), seluruh komunikasi remote ke agen bisa didekripsi. Tidak ada mekanisme untuk mengganti kunci tanpa menghentikan semua agen.
· Rekomendasi Wajib:
  · Terapkan Dual-Key Periodik: Simpan KeyVersion di payload. Kunci baru digenerate setiap 30 hari dan didistribusikan via NATS secara terenkripsi (menggunakan kunci lama). Agen akan menyimpan kedua kunci dan menggunakan yang terbaru.
  · Tambahkan Hardware Security Module (HSM) atau gunakan AWS KMS / HashiCorp Vault untuk menyimpan master key, bukan di file plaintext.

---

6. [L4 - AI Core] Stale SOP & Knowledge Base Tidak Pernah Di-Retire (Knowledge Rot)

· Fakta di Dokumen: L4_SOPRegistry memiliki status ACTIVE dan DRAFT. Tidak ada mekanisme untuk menonaktifkan SOP usang.
· Dampak: Misal, 2 tahun lalu Anda memiliki SOP untuk "Restart Service X". Sekarang Service X sudah di-migrasi ke Kubernetes dan cara restart-nya berbeda. SOP lama tetap ACTIVE dan akan terus di-rekomendasikan AI, menyebabkan eksekusi gagal terus menerus.
· Rekomendasi Wajib:
  · Tambahkan SOP Expiry Date (misal: 1 tahun sejak dibuat). Saat mendekati kadaluarsa, kirim notifikasi ke Admin untuk review.
  · Tambahkan SOP Success Rate Tracker: Setiap kali SOP digunakan, catat apakah eksekusi berhasil. Jika success rate < 60% dalam 3 bulan terakhir, otomatis ubah status menjadi DEPRECATED dan pindahkan ke L4_Reflector untuk evaluasi.

---

7. [L1 - UI] 60 FPS Real-Time Rendering Memboroskan Resource Client (Laptop NOC)

· Fakta di Dokumen: Dashboard menggunakan requestAnimationFrame 60 FPS untuk animasi partikel dan update chart.
· Dampak: Operator NOC yang membuka dashboard di laptop dengan baterai akan mengalami baterai cepat habis dan kipas laptop berputar kencang. Jika membuka 2-3 tab dashboard, browser bisa lag.
· Rekomendasi Wajib:
  · Terapkan Adaptive Framerate: Jika tab sedang tidak aktif (menggunakan document.hidden API), turunkan FPS ke 10 FPS.
  · Gunakan Canvas Offscreen Rendering untuk partikel, jangan di DOM utama.

---

8. [L6 - Infrastruktur] n8n Workflow Tidak Ada Version Control (GitOps)

· Fakta di Dokumen: n8n digunakan sebagai orkestrator workflow v3.0 (BAB 2.7).
· Dampak: Jika seorang engineer mengubah workflow n8n secara manual di UI dan kemudian merusaknya, tidak ada riwayat (history) untuk rollback ke versi sebelumnya.
· Rekomendasi Wajib:
  · Aktifkan n8n Git Sync (fitur bawaan n8n enterprise) untuk menyimpan semua workflow sebagai file JSON di repository Git internal.
  · Wajibkan setiap perubahan workflow melalui Pull Request (PR) di Git, bukan langsung di UI produksi.

---

🟡 GAP PRIORITAS RENDAH (PERBAIKAN KUALITAS)

9. [L0 - Klien] Chrome Extension Hanya Polling (Boros & Delay 10 Detik)

· Fakta di Dokumen: Ekstensi Chrome melakukan polling setiap 10 detik ke API status (BAB 4.3).
· Dampak: Notifikasi insiden P0 di toolbar browser tertunda hingga 10 detik. Ini bisa menjadi masalah jika operator NOC hanya mengandalkan ekstensi (tanpa membuka dashboard).
· Rekomendasi:
  · Ubah mekanisme ekstensi menjadi WebSocket Push (sama seperti dashboard). Ekstensi Chrome mendukung WebSocket.

10. [L8 - Eksternal] Kafka Hanya Satu Arah (Producer) Tidak Ada Consumer untuk Command Eksternal

· Fakta di Dokumen: L4_Closure mengirim webhook ke Kafka (BAB 2.9). Tidak ada consumer Kafka untuk menerima perintah dari sistem enterprise lain.
· Dampak: Platform AI ini menjadi "pulau" (silo). Sistem eksternal (misal: ServiceNow, Jira) tidak bisa memicu remediasi melalui platform.
· Rekomendasi:
  · Tambahkan Kafka Consumer di L3_GoCore yang mendengarkan topic external.incident.trigger. Jika ada pesan masuk, konversikan menjadi insiden internal dan proses seperti biasa.

---

📊 RINGKASAN EKSEKUTIF (MATRIKS GAP L0 - L10)

Layer Nama Layer Gap Kritis Level Dampak Status Perbaikan
L10 Strategi & BCDR Tidak ada Disaster Recovery Plan (Master SPOF) 🔴 KRITIS WAJIB
L5 Persistence PostgreSQL SPOF & No Read Replica 🔴 KRITIS WAJIB
L7 Agen Endpoint Buffer SQLite Tanpa Limit (Disk Full) 🔴 KRITIS WAJIB
L2 Gateway Tidak Ada Circuit Breaker (Downstream overload) 🟠 TINGGI Segera
L3 Go Core Tidak Ada Rotasi Kunci AES (Key Rotation) 🟠 TINGGI Segera
L4 AI Core Knowledge Rot (SOP Usang Tidak Di-Retire) 🟠 TINGGI Segera
L1 UI 60 FPS Boros Baterai Laptop NOC 🟡 SEDANG Opsional
L6 Infrastruktur n8n Workflow Tanpa Version Control (Git) 🟡 SEDANG Opsional
L0 Klien Chrome Extension Hanya Polling (Terlambat) 🟡 SEDANG Opsional
L8 Eksternal Kafka Hanya Producer (Tidak Bisa Trigger Eksternal) 🟢 RENDAH Enhancement