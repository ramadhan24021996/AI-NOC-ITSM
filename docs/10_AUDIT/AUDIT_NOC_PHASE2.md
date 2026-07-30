# NOC & AI Observability - Phase 2 Audit Matrix
**Tanggal Audit:** 20 Juli 2026

Berdasarkan audit mendalam (*deep code & runtime inspection*) terhadap seluruh pipeline tanpa *mock* atau simulasi, berikut adalah hasil temuan Phase 2 yang merinci *blind spots* pada performa, arsitektur, dan keamanan.

---

### 1. Komponen Production Ready (✅)
*   **AI Engine (RAG & Consensus):** Modul Python (`active_cognitive_engine.py`, `ai_supervisor.py`) telah berjalan menggunakan NATS JetStream dan dapat memproses korelasi insiden secara paralel.
*   **Database Schema:** Tabel operasional (`telemetry_logs`, `incidents`, `ai_audit_trail`) telah mendukung JSONB dan pemartisian (*partitioning*), sehingga siap menelan volume data yang tinggi.
*   **Dashboard Frontend:** Refactor UI pada modul "Issue Detail" sudah *production-ready* dengan visualisasi data hingga 70 field.

### 2. Komponen Partial (⚠️)
*   **Message Broker (NATS):** *Python AI Core* sudah menggunakan `JetStream` (persisten), namun **Golang Ingestion Server** masih menggunakan NATS standar (`natsConn.Publish()`) tanpa jaminan pengiriman pesan (*at-least-once delivery*).
*   **Database Indexes:** Tabel `telemetry_logs` sudah memiliki B-Tree index untuk `timestamp` dan `device_name`, tetapi **TIDAK ADA GIN Index** pada kolom `metadata (JSONB)`. Pencarian berdasar URL atau tipe metrik dari AI akan sangat lambat saat data mencapai jutaan baris.
*   **Browser Telemetry:** Ekstensi Chrome hanya membaca performa halaman standar (*Navigation Timing API*). *Crash Dump*, *JS Exceptions*, dan intervensi OS tidak tersedia.

### 3. Komponen Missing (❌)
*   **OS-Level Process Monitor:** Tidak ada modul yang membaca hierarki parent-child PID, deadlock thread, zombie process, atau Open Files di tingkat OS.
*   **Evidence Collection Engine:** Tidak ada fungsi untuk mengekstrak PCAP, HAR, atau *Crashpad Minidumps (.dmp)*. Tidak ada *Screenshot Agent* yang berjalan.
*   **Advanced AI Causal DAG:** AI saat ini masih bergantung pada kesamaan (*semantic search*) dan *prompting*, bukan graf kausalitas deterministik (DAG) yang menghubungkan *Registry/Network/Process* secara graf.

### 4. Komponen Broken (💥)
*   **Data Integrity (Dropped Events):** Penggunaan `natsConn.Publish` (tanpa ack) pada `ingestion_server.go` berpotensi *drop message* 100% jika NATS broker restart sepersekian detik. Harus menggunakan `js.Publish`.

---

### Analisis Risiko
*   **5. Risiko Operasional:** *Blind spot* pada event *Crash* internal Chrome menyebabkan operator hanya melihat tulisan "Browser Crash" tanpa bisa tahu *script* atau *extension* mana yang memicunya. MTTR menjadi lama.
*   **6. Risiko Security:** Ekstensi Chrome saat ini mengirim data POST HTTP ke `localhost:9999` tanpa *Authentication/Token*. Bisa dieksploitasi oleh website jahat untuk membanjiri (*DDoS*) Ingestion Server.
*   **7. Risiko Performance:** *Full table scan* di PostgreSQL untuk kueri AI yang mencari pola `metadata->>'url'` karena ketiadaan GIN index.
*   **8. Risiko Observability:** AI menghasilkan "Root Cause" berdasarkan asumsi metrik, bukan bukti forensik keras seperti *Minidump* atau *Stack Trace V8 Engine*.

---

### 9. Prioritas Implementasi
1.  **[CRITICAL]** Refaktor Golang Ingestion Server agar menggunakan **NATS JetStream (Publish)** untuk `telemetry_stream`.
2.  **[CRITICAL]** Tambahkan **GIN Index** pada kolom `metadata` di PostgreSQL.
3.  **[HIGH]** Amankan Ingestion API `localhost:9999` dengan *HMAC/Token*.
4.  **[HIGH]** Kembangkan Native Go Agent CDP (*Chrome DevTools Protocol*) pengganti/pendamping Chrome Extension.

### 10. Estimasi Tingkat Kesiapan Sistem (%)
**75% (Menuju Enterprise-Grade)**
Infrastruktur inti kuat, namun belum cukup detail (*granular*) untuk menyajikan RCA otomatis secara meyakinkan tanpa *hallucination*.

### 11. Roadmap Menuju Enterprise Grade Observability
1.  **Q3 2026:** Migrasi penuh ke NATS JetStream & Penambahan GIN Indexing.
2.  **Q3 2026:** Rilis Native Browser OS-Hook (CDP & Crashpad).
3.  **Q4 2026:** Otomasi ekstraksi forensik (Memory Heap Dump, HAR, Screenshot 5-detik sebelum *crash*).
4.  **Q4 2026:** Graph-based Causal AI (bukan sebatas LLM Prompt, melainkan deterministik DAG).

---

### Daftar Perbaikan Source Code & Arsitektur
**12. File Source Code yang Harus Dimodifikasi:**
*   `SERVER/go_core/ingestion/ingestion_server.go`: Ubah semua pemanggilan `natsConn.Publish` menjadi `js.Publish` agar *backpressure* dan ACK JetStream aktif, mencegah insiden hilang.
*   `SERVER/go_core/database/schema.go`: Tambahkan sintaks pembuatan GIN Index pada saat migrasi.
*   `chrome_extension/background.js`: Tambahkan token otorisasi statis/dinamis dalam request header agar tidak menerima HTTP request liar.

**13. API Baru yang Harus Dibuat:**
*   `/api/ingest/forensic/dump`: Menerima *Minidump/Crashpad* (Binary).
*   `/api/ingest/forensic/visual`: Menerima blob gambar *Screenshot Before/After*.
*   `/api/ingest/forensic/network`: Menerima file `HAR` atau PCAP.

**14. Tabel Database Baru yang Harus Dibuat:**
*   `forensic_dumps` (id, incident_id, s3_blob_path, parsed_stack_trace, engine_type).
*   `causal_graphs` (menyimpan DAG relasi *Root Cause* yang bisa digambar oleh UI).

**15. Agent Baru yang Harus Dibuat:**
*   **V8 Forensics Agent:** Proses Golang lokal di OS yang attach ke port Chrome DevTools (9222) untuk menarik JS Error, Heap size, dan Network Waterfall (tanpa batas *sandbox* ekstensi).
*   **OS Crashpad Listener:** *FileSystem Watcher* untuk direktori minidump Chrome/Edge (mengirim file `.dmp` sesaat setelah aplikasi tertutup mendadak).

**16. Telemetry Baru yang Harus Dikumpulkan:**
*   JS Stack Trace asli dari DOM.
*   OOM (Out Of Memory) event dari V8.
*   Windows Wait Chain Traversal (WCT) untuk mendeteksi *deadlock* aplikasi.

**17. Dashboard Panel Baru yang Harus Ditambahkan:**
*   **Forensic Evidence Viewer:** Penampil struktur Crash Dump dan Stack Trace yang bisa diekspansi.
*   **Dependency/Topology Graph:** Diagram *node-link* (Mermaid/D3) yang menunjukkan hubungan *Browser* → *Renderer PID* → *OS Process* → *Network Port*.

**18. Metrik yang Harus Dimonitor (Syarat Mutlak RCA AI Real-Time):**
*   *Event Drop Rate* (dari NATS JetStream).
*   *Memory Heap Allocation Rate* (Mb/s pada tab Browser aktif).
*   *Renderer Thread Responsiveness* (Waktu yang dibutuhkan Main Thread untuk merespons ping OS).
*   *PostgreSQL JSONB Scan Latency* (Pastikan kueri RCA tidak menyebabkan *database throttling*).
