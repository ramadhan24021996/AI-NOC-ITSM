# Operational Readiness Review (ORR) & Chaos Engineering Blueprint

Dokumen ini berfungsi sebagai gerbang produksi (*Production Readiness Gate*) yang mendefinisikan standar kelulusan operasional sebelum sistem AIOps dinyatakan layak tayang di lingkungan *mission-critical*. Dokumen ini juga memuat daftar parameter pengujian Chaos Engineering untuk memvalidasi ketahanan arsitektur AI Governance.

---

## 1. Production Readiness Checklist

Berikut adalah matriks kelayakan teknis dan operasional yang menjamin keandalan *Autonomous Remediation Orchestrator*. Seluruh komponen harus diverifikasi sebelum uji injeksi kegagalan dilakukan.

### 🛡️ Governance (Tata Kelola Keputusan AI)
- [x] **Policy Versioning**: Setiap eksekusi AI menyertakan versi kebijakan (*policy*), *prompt*, dan *reasoning*.
- [x] **Explainability**: Parameter ringkasan penentu keputusan (alasan) tersimpan secara persisten.
- [x] **Immutable Decision Record**: `autonomous_decision_records` di PostgreSQL tidak dapat diubah (*append-only*).
- [x] **Evidence Hash**: Setiap rekam keputusan dikunci dengan *cryptographic hash* (SHA-256) dari snapshot telemetri.
- [x] **HITL (Human-in-the-Loop)**: AI menghentikan eksekusi dan mendelegasikan ke antrean *Approval Queue* apabila *Confidence* tidak memadai atau *Severity* terlalu tinggi.

### ⚙️ Reliability (Keandalan Eksekusi)
- [x] **Retry**: Mekanisme percobaan ulang di *Recovery Worker* apabila perintah gagal dikirim ke *agent*.
- [x] **DLQ (Dead Letter Queue)**: Aksi yang gagal berulang kali dimasukkan ke antrean DLQ dan memicu *alert*.
- [x] **Recovery Worker**: Menangani asinkronisasi proses penyelesaian eksekusi secara terdistribusi (Redis).
- [x] **Verification Engine**: Melakukan validasi *multi-sample* (minimal 3 *check*) di Netdata pasca-remediasi.
- [x] **TOCTOU Protection**: Mengecek konsistensi versi *incident state* sebelum melempar instruksi (Optimistic Concurrency Control).
- [x] **Advisory Lock**: Menjamin *single-execution* menggunakan Redis *distributed lock* berdasar `incident_id`.

### 🔒 Security (Keamanan Infrastruktur)
- [x] **HMAC**: Integritas data *payload* yang dikirim di atas NATS diverifikasi agar kebal dari *tampering*.
- [x] **Token TTL**: Otorisasi token perintah eksekusi kedaluwarsa secara otomatis (misal: dalam 60 detik).
- [x] **RBAC**: Hak akses granular seperti `view_evidence`, `policy_override`, `run_chaos_test`.
- [x] **Policy Constraint**: Batas minimum *confidence* (misal: 85%) dan batas maksimum toleransi aksi.
- [x] **Audit Trail**: Aktivitas operator (termasuk *Override*) direkam permanen di `hitl_audit_logs`.

### 📊 Data Integrity (Integritas Data AI)
- [x] **Freshness**: Bukti (evidence) dievaluasi usianya. Batas *stale data* maksimum adalah 30 detik (`NOW - sample_time`).
- [x] **Schema Validation**: Filter NATS menolak muatan log JSON cacat/hilang atribut esensial.
- [x] **Clock Drift Detection**: Mengabaikan data jika `received_timestamp` melenceng signifikan dari `collector_timestamp`.
- [x] **Duplicate Detection**: Identitas *idempotency* mencegah eksekusi berulang dari *event* kembar.
- [x] **Replay Protection**: Menolak pengiriman ulang (*replay attack*) instruksi lama.

### 🔭 Observability (Visibilitas Eksekutif)
- [x] **AI Metrics**: Dashboard menampilkan tingkat keberhasilan AI, persentase eskalasi, dan *confidence*.
- [x] **Decision Timeline**: UI menyajikan urutan waktu datangnya telemetri hingga AI membuat keputusan.
- [x] **Evidence Explorer**: Panel interaktif untuk melihat matriks data penyebab keputusan (termasuk *hash*).
- [x] **Knowledge Graph**: Topologi *real-time* yang diwarnai berdasarkan status kesehatan verifikasi AI (Sukses/Gagal/Pending).
- [x] **Governance Dashboard**: Tampilan terpadu kebijakan keamanan AI yang dapat diatur saat sistem berjalan (*on-the-fly*).

---

## 2. Chaos Engineering Blueprint (Maturity Level 1)

Setelah kriteria **ORR** terpenuhi, pengujian daya tahan sistem (*Resiliency Test*) akan dieksekusi dengan target terukur. *Expected Result* bertindak sebagai patokan sukses atau gagalnya orkestrasi *Governance* dan *Reliability* kita.

> **ATURAN OPERASI & SAFETY GATES**  
> 1. **Blast Radius (Satu Domain)**: Satu chaos experiment = satu failure domain.  
> 2. **Canary Validation**: Pengujian tidak langsung ke *Production*. Alur wajib: `Canary Agent` ➔ `Pilot Site` ➔ `Production Site`.  
> 3. **Approval Gate (No-Go)**: Chaos dilarang dimulai jika `Critical Incident > 0` atau `Severity 1 == ACTIVE`.  
> 4. **Emergency Abort Switch**: Wajib ada tombol "STOP ALL CHAOS" yang seketika menghentikan injektor, scheduler, retry, dan me-restore *policy*.  
> 5. **Traceability**: Setiap pengujian di-tag dengan `chaos_run_id` (misal: `CH-20260720-001`) yang terikat ke semua *Decision*, *Incident*, *Queue*, dan *Evidence*.  
> 6. **Baseline Snapshot**: Kondisi sistem (*Queue*, *CPU*, *Decision Count*, dll) difoto (*snapshot*) sebelum dan sesudah uji untuk komparasi `BEFORE vs AFTER`.

| Tahap | Target Uji (Chaos Injection) | Kriteria Sukses (*Expected Result*) | Recovery SLO (Target Waktu) | Exit Criteria (Syarat Lulus) | Rollback Criteria (Batas Berhenti) |
| :--- | :--- | :--- | :--- | :--- | :--- |
| **Tahap 1: Heartbeat Loss** | Matikan *heartbeat* node pelapor (*Canary Agent*). | Transisi state: `ACTIVE` ➔ `WAITING_HEARTBEAT` ➔ `VERIFYING` ➔ `STALE` ➔ `ESCALATED`. | Detection < 15 detik | Tidak ada insiden yang menjadi `RESOLVED`. | Heartbeat tidak kembali dalam 2 menit ➔ *Restore Agent*. |
| **Tahap 2: Netdata Delay** | Tahan pengiriman sensor Netdata (*Telemetry Delay*). | *Freshness gate* memblokir verifikasi AI, AI membatalkan tindakan (*Abort*). | Detection < 10 detik | Bukti menunjukkan `stale_telemetry` & verifikasi `FAILED`. | Delay merambat ke layanan utama > 30 detik ➔ *Restore Network*. |
| **Tahap 3: Agent Offline** | Hentikan servis *Agent OS* secara mendadak. | *Recovery Worker* mengambil alih antrean ke Redis, menanti *retry*. Keputusan dibatalkan. | Recovery < 45 detik | *Decision Record* menunjuk `UNKNOWN`/`FAILED`. | Agent zombie muncul atau *resource leak* ➔ *Kill Process*. |
| **Tahap 4: NATS Restart** | *Restart* klaster *NATS Server* secara paksa. | Koneksi pulih (*auto-reconnect*), eksekusi ganda ditolak. | Reconnect < 20 detik | `execution_id` harus unik, `No Duplicate Execution`. | *Reconnect* gagal > 60 detik ➔ *Rollback/Failover NATS*. |
| **Tahap 5: Redis Restart** | *Restart* layanan cache *Redis* (sumber *Queue* & *Lock*). | Antrean dipulihkan tanpa data hilang, mekanisme *Lock* pulih setelah *restart*. | Recovery < 60 detik | Jumlah *job* sebelum = sesudah *restart* (*no orphan*). | *Queue corruption* terdeteksi ➔ *Restore Snapshot Redis*. |
| **Tahap 6: PostgreSQL Latency**| Simulasi pelambatan koneksi ke basis data PostgreSQL. | *Verification Engine* kehabisan waktu (*Timeout*). Status berganti `ESCALATED`. | Timeout < 120 detik | Harus gagal secara aman (Fail-safe, bukan `PASS`). | DB *connection pool exhausted* ➔ *Drop Chaos Connection*. |
| **Tahap 7: Policy Shift** | Ubah batas *Confidence Policy* ketika ada insiden aktif. | Insiden/keputusan lama tetap menggunakan *policy* lama secara historis, insiden baru ikut aturan baru. | Penerapan < 5 detik | *Policy version* pada *Decision* lama tidak terubah retroaktif. | *State* kebijakan tidak sinkron antar *worker* ➔ *Revert Policy*. |
| **Tahap 8: Network Delay** | Perlambat pemrosesan *queue* secara ekstrem. | Eksekusi terlambat tiba di *agent* melampaui masa `Token TTL`. *Agent* menolak perintah. | Timeout < 60 detik | *Agent* menolak menjalankan aksi (Rejected by TTL). | Jaringan ke *control plane* terputus > 2 menit ➔ *Remove Delay*. |

---

## 3. Evaluasi Chaos (Chaos Score)
Kesuksesan Chaos Engineering dievaluasi ke dalam bentuk metrik **Chaos Score** yang akan dipampang di *Governance Dashboard*.  
Komponen skor:
*   **Detection Score (25%)**: Apakah sistem mendeteksi anomali dalam rentang SLO?
*   **Recovery Score (25%)**: Apakah sistem pulih dari kerusakan (*Queue/Lock*) tepat waktu?
*   **Verification Score (25%)**: Apakah *Quality Gate* secara akurat menolak kondisi cacat?
*   **Audit Score (25%)**: Apakah `chaos_run_id` berhasil tercatat di seluruh *timeline* `Decision Record`?

---

## 5. Arsitektur Distribusi & Native Chaos Framework

Sesuai prinsip **No Mock, No Stub, No Dummy**, kapabilitas injeksi kegagalan tidak di-_mock_ secara sporadis, melainkan dibakukan sebagai struktur *Governance* terpisah dengan **Single Responsibility Principle**.

### 3-Tier Separation of Duties
Arsitektur dibagi secara tegas agar aman dan mudah diaudit:
1.  **Go Dashboard Server (Chaos Gateway)**: Murni menerima HTTP *Request* dari UI, memvalidasi JWT, verifikasi izin RBAC, mem- *build* *payload* ke NATS, dan memperbarui Dashboard. *Go Gateway sama sekali tidak tahu bagaimana heartbeat dihentikan*.
2.  **Python AI Core (Chaos Orchestrator)**: Murni sebagai *Governance Engine*. Meng- *generate* `chaos_run_id`, memverifikasi *Policy*, validasi *Canary*, melakukan *audit log*, lalu mengirim perintah. Python tidak pernah melakukan injeksi secara langsung.
3.  **Endpoint Agent (Chaos Controller)**: Komponen paling ujung (klien) yang secara tunggal memiliki hak menyabotase dirinya sendiri (*heartbeat, telemetry, cpu_spike*). Ia mengeksekusi instruksi dari subjek NATS independen: `chaos.control.<agent_id>` (sehingga lalu lintas *Chaos* tidak bercampur dengan pesan remediasi operasional `remediation.execute`).

### Payload Injeksi (*Replay-Protected & HMAC Secured*)
Perintah yang di-_publish_ dari *Chaos Orchestrator* ke *Chaos Controller* memiliki proteksi ganda:
```json
{
  "run_id": "CH-20260720-001",
  "agent_id": "node-canary-01",
  "mode": "heartbeat_pause",
  "ttl": 60,
  "reason": "ORR Stage 1",
  "approved_by": "superadmin",
  "policy_version": "v1.4.2",
  "requested_at": "2026-07-20T09:50:00Z",
  "expires_at": "2026-07-20T09:50:30Z",
  "signature": "hmac_sha256_hash",
  "nonce": "uniq_rand_8923a"
}
```

### Aturan Ketat Chaos Controller (Level Agent)
1. **Agent State Machine**: Di UI Dashboard, eksperimen tidak hanya berstatus *Running*, tapi mengikuti transisi *finite state* deterministik dari Agent: `NORMAL` ➔ `PREPARING` ➔ `ACTIVE` ➔ `RESTORING` ➔ `NORMAL` (dengan state alternatif `ABORTED` dan `EXPIRED`).
2. **Auto-Rollback (Fail-safe TTL)**: Setiap kapabilitas chaos mengikat batas `TTL`. Setelah `TTL` habis, agen wajib mengembalikan ke status `RESTORING` secara otonom tanpa bantuan operator. Jika agen gagal, diterbitkan insiden baru.
3. **Single Session Lock**: Tidak boleh ada penumpukan kegagalan di dalam satu Agen. (Satu sesi = Satu kegagalan).
4. **Isolasi Log**: Semua pencatatan dialirkan ke dalam tabel independen `chaos_runs` dan `chaos_events`, terpisah total dari `incident_events` yang sakral untuk operasional rutin.

> **Status Dokumen**: *Blueprint Disetujui & Final (3-Tier Production Chaos Framework).*
> **Tahap Berikutnya**: Mulai membangun **Endpoint Agent (Chaos Controller)** untuk mengakomodasi State Machine dan `chaos.control` listener.

---

## 4. Protokol Eksekusi & Observasi (Fokus: Tahap 1 - Heartbeat Loss)

Sesuai dengan prinsip isolasi domain kegagalan (*Single Failure Domain*), eksperimen Tahap 1 **TIDAK** dilakukan dengan mematikan koneksi NATS atau agen secara destruktif (*hard kill*). Injeksi kegagalan dilakukan pada level aplikasi (men- *toggle config* untuk sekadar menonaktifkan *publisher heartbeat* pada 1 Node Canary, sedangkan aliran telemetri lain dibiarkan menyala).

### Checklist Observasi 10 Indikator Utama
Selama siklus hilangnya *heartbeat*, auditor wajib memvalidasi 10 area ini:
1.  **Heartbeat**: Terjadi penundaan (delay) spesifik pada waktu sejak *heartbeat* terakhir.
2.  **State Machine**: Transisi berurutan dan persis menaati: `ACTIVE` ➔ `WAITING_HEARTBEAT` ➔ `VERIFYING` ➔ `STALE` ➔ `ESCALATED`.
3.  **Freshness**: *Evidence* beralih status menjadi *stale* setelah melewati ambang batas usia.
4.  **Decision Record**: *Outcome* dan justifikasi pembatalan aksi tercatat sempurna.
5.  **Governance Dashboard**: Metrik KPI dan status *timeline* tervisualisasi sesuai pergerakan di latar belakang.
6.  **Recovery Worker**: Pekerja asinkron (Redis) menahan diri dari menciptakan *retry* yang tidak berdasar.
7.  **Verification Engine**: Secara absolut menolak memberi cap `PASS` pada data yang sudah usang (*stale*).
8.  **Knowledge Graph**: Simpul (*node*) yang terdampak berubah menjadi abu-abu (*Unknown / Stale*).
9.  **Audit Trail**: *Timestamp* untuk setiap mikro-kejadian terarsip dalam log audit.
10. **Rollback**: Agent kembali sehat saat *publisher heartbeat* dinyalakan lagi (Otomatis pulih tanpa intervensi manusia).

### Kriteria Kelulusan Mutlak (Strict Pass Criteria)
Selain dari *Exit Criteria* dasar, Tahap 1 hanya dinyatakan LULUS (siap menuju Tahap 2: *Netdata Delay*) apabila memenuhi 5 syarat berikut:
- [ ] **No Skipped States**: Tidak ada satupun fase *state* yang dilewati.
- [ ] **No Fast-forward Escalation**: Tidak ada "loncatan" *state* secara prematur/langsung ke `ESCALATED`.
- [ ] **No Unjustified Execution**: Tidak ada remediasi otomatis yang terpicu murni karena alasan agen diam (*heartbeat hilang*).
- [ ] **No Forced Resolution**: Tidak ada insiden yang otomatis ditutup (*RESOLVED*) oleh sistem pelaporan.
- [ ] **Clean Recovery**: Setelah di- *rollback* (jantung berdetak kembali), sistem sembuh paripurna (tidak ada *orphan state* maupun penumpukan *job* yang tertunda).
