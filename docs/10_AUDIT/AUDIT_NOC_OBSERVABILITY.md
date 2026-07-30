# NOC Observability Audit & Production Readiness Matrix
**Tanggal:** 20 Juli 2026
**Target Audit:** Server, Agent, Telemetry Pipeline, AI Engine, Database, Event Collector, Network Monitoring

Berdasarkan investigasi real-time terhadap arsitektur dan kapabilitas sistem, berikut adalah hasil audit menyeluruh (Zero Mock Policy Enforced):

## 1. Service yang Sudah Tersedia dan Aktif
*   **Docker Container Utama:** 19 kontainer berjalan secara stabil.
    *   `osi-dashboard-server` (Frontend/Backend API - Port 80/8099)
    *   `osi-ingestion-server` (Telemetry API)
    *   `osi-ai-core`, `osi-ai-rag`, `osi-ai-policy`, `osi-ai-daemons`, `osi-ai-critic`, `osi-ai-consensus` (AI Pipeline)
    *   `osi-postgres`, `osi-redis`, `osi-nats` (Data & Message Broker)
    *   `osi-telegram-bot`, `osi-scheduler-service`, dll.
*   **Database (PostgreSQL):** Tabel `telemetry_logs`, `incidents`, `incident_post_mortems`, `ai_audit_trail` telah disetup dan siap menerima data. Kolom `metadata` pada `telemetry_logs` dikonfigurasi menggunakan JSONB sehingga mendukung skema data apa pun secara *real-time*.

## 2. Service Tersedia Tetapi Belum Mengirim Data (Gaps)
*   **Browser Telemetry Agent:** Extension Chrome tersedia dan aktif, tetapi **hanya** mengirimkan `web_activity` dasar (URL, Title, Load Time, DNS Time). Extension ini belum memiliki kapabilitas untuk mengambil *Crash Dump*, *JavaScript Exception*, *Extension Crash*, atau *Browser PID/Renderer PID*.
*   **Windows Watchdog (agent/main.go):** Watchdog beroperasi dengan sangat sederhana, ia hanya me-monitor *internal thread* miliknya sendiri (seperti "AI Engine thread" atau "Telemetry thread" di dalam binary Go). **Belum** memonitor process Windows/Browser yang hang/crash secara spesifik, sehingga tidak ada pengiriman "PID", "Stack Trace", atau "Error Code".

## 3. Agent yang Belum Berjalan / Tidak Tersedia
Sistem *TIDAK MEMILIKI* implementasi Native Agent untuk komponen-komponen berikut:
*   **Crashpad / Breakpad Agent:** Tidak ada agent native yang melakukan ekstraksi file minidump (.dmp) saat Chrome/Edge crash.
*   **DevTools / Remote Debugging Agent:** Tidak ada implementasi CDP (Chrome DevTools Protocol) untuk menyedot *Console Errors*, *Memory Leaks*, atau *Unhandled Promises* dari V8 Engine.
*   **Screenshot Agent:** Tidak ada fungsi yang berjalan untuk mengambil "Screenshot Before Crash" atau "Screenshot After Recovery".

## 4. Telemetry yang Belum Dikumpulkan (Missing Data)
Dari daftar wajib yang diminta, data observabilitas berikut **kosong total** di seluruh pipeline:
*   **Browser:** Browser PID, Renderer PID, GPU PID, Extension Crash, JavaScript Exception, Unhandled Promise, Crash Dump.
*   **Process:** Parent PID, Child PID, Thread Count, Open File, Killed Process, Deadlock.
*   **Watchdog:** Reason, Timeout (ms), Failed Component Trace, Error Code, Stack Trace.

## 5. Log Source yang Belum Terhubung
*   **Windows Event Log:** `deep_telemetry.go` memiliki skrip PowerShell untuk menarik `EventLogs`, namun *event collector* untuk WER (Windows Error Reporting), Security Log, dan IIS Log belum terhubung ke pipeline realtime NATS.
*   **Linux /var/log:** `journalctl`, `dmesg`, `syslog` tidak terhubung karena *Linux Agent* masih dalam status pengembangan awal (ukuran binary besar, fitur minim).

## 6. Data Observability yang Masih Kosong di DB
Meskipun Dashboard UI sudah siap, data *raw* yang diharapkan masuk ke dalam `telemetry_logs` untuk bidang berikut belum di-inject oleh Agent mana pun:
*   `screenshot_url` (Before/After)
*   `javascript_console_error`
*   `stack_trace`
*   `gpu_crash_report`
*   `network_packet_loss`

## 7. API Backend yang Belum Menyediakan Endpoint
*   **Endpoint `/api/crash-dump`:** Belum ada endpoint khusus untuk menelan binary minidump (.dmp) atau log berukuran besar dari V8 Engine/Crashpad.
*   **Endpoint `/api/screenshot`:** Belum ada mekanisme unggah dan penyimpanan objek/blob image dari agent ke storage backend.

## 8. Perubahan Backend yang Diperlukan
*   **Upload Handler:** Buat multipart/form-data handler di `ingestion-server` untuk menerima file minidump dan screenshot (simpan ke *disk/S3/MinIO* dan buat reference URL ke PostgreSQL).
*   **Minidump Parser:** Implementasikan *parser* (seperti `minidump-stackwalk`) di backend untuk mengubah *binary dump* dari browser menjadi Stack Trace yang bisa dibaca manusia dan diproses AI.

## 9. Perubahan Agent yang Diperlukan
*   **Implementasi CDP (Chrome DevTools Protocol):** Ekstensi Chrome biasa *tidak cukup* untuk level investigasi ini. Agent Golang di sisi OS (`main.go`) harus diluncurkan dengan flag `--remote-debugging-port=9222` pada Chrome/Edge pengguna agar dapat memanen *Console Error*, RAM V8, dan DOM state.
*   **Crashpad Integration:** Agent OS harus memiliki *hook* ke direktori `%LOCALAPPDATA%\Google\Chrome\User Data\Crashpad\reports` untuk mencegat dan mengirim `.dmp` file setiap ada crash.
*   **Screenshot Module:** Integrasikan library Golang (mis: `kbinani/screenshot`) untuk di-trigger secara otomatis saat anomali resource terdeteksi.

## 10. Perubahan Database yang Diperlukan
Database secara arsitektur sudah *capable* karena menggunakan `JSONB` pada `telemetry_logs.metadata`. Namun perlu penambahan tabel/skema khusus:
*   `CREATE TABLE crash_dumps (id SERIAL, log_id INT, s3_path TEXT, raw_stack_trace TEXT, parsed_by_ai BOOLEAN);`
*   `CREATE TABLE visual_evidence (id SERIAL, log_id INT, type TEXT, url TEXT);` (Tipe: Before, After, Alert).

## 11. Perubahan Dashboard yang Diperlukan
Dashboard sudah 95% siap dan bersifat adaptif (*Production-Ready* berkat implementasi 70+ field dinamis). Perubahan minor yang diperlukan hanyalah:
*   Menghubungkan *URL Image Placeholder* (Screenshot) di UI Evidence Modal langsung dengan link statis S3/MinIO yang baru dibuat di tahap 10.

## 12. Prioritas Implementasi
| Komponen / Task | Prioritas | Dampak pada Observability |
| :--- | :---: | :--- |
| **Agent: CDP Integration (Browser PID, RAM, JS Error)** | **CRITICAL** | Merupakan nyawa dari Browser Crash Log agar AI punya data aktual. |
| **Agent: Crashpad Monitor (.dmp file intercept)** | **CRITICAL** | Wajib untuk mengetahui alasan spesifik *Renderer Crash* (STATUS_BREAKPOINT dll). |
| **Backend: Endpoint Screenshot & Dump Upload** | **HIGH** | Tanpa ini, agent tidak bisa mengirim visual evidence. |
| **Agent: Watchdog Windows Process Hook** | **HIGH** | Mengubah Watchdog internal go-routine menjadi OS-level Watchdog (bisa deteksi aplikasi hang). |
| **Agent: Golang Screenshot trigger** | **MEDIUM** | Melengkapi bukti visual saat RCA dilakukan. |
| **Backend: Minidump-stackwalk Parser** | **LOW** | Berguna untuk debugging tingkat C++, jika tidak AI hanya akan membaca error code dasar. |

## 13. Rekomendasi Implementasi (Roadmap Real-Time & Audit-Ready)
Untuk mencapai 100% visibilitas observabilitas yang Anda harapkan (Tanpa Mock):
1.  **Tinggalkan Pendekatan WebExtension:** Ekstensi Chrome memiliki *sandbox* yang tidak bisa membaca Crashpad atau V8 Memory Heap. Pindahkan tugas pemantauan utama ke *Go Agent* yang berbicara langsung ke Chrome via *CDP Protocol*.
2.  **OS-Level Hooking:** Gunakan `WMI` dan `psutil` di Golang Agent untuk memantau semua Child PID dari `chrome.exe` atau `msedge.exe`. Jika salah satu PID mati mendadak (Exit Code != 0), tembak trigger "Browser Crash" secara instan.
3.  **Visual Evidence Buffer:** Buat buffer FIFO di RAM (misal menyimpan layar 5 detik terakhir di local memory agent). Begitu crash terjadi, flush 5 frame terakhir ke server sebagai bukti "Before Crash".
4.  **Causal AI RAG Upgrades:** Begitu metrik dari CDP (JS Exception) masuk, umpankan langsung ke *RAG Engine* di `incident_post_mortems` agar RCA bisa memberikan rekomendasi akurat (misal: "Infinite Loop di script.js baris 42").

---
**Kesimpulan Audit:** Sistem secara infrastruktur dan *frontend orchestration* sudah *Production-Ready*. Namun, sistem **buta secara diagnostik (blind-spot)** di area *Browser Internal Telemetry* dan *OS-level Crash Handling* karena implementasi Agent di sisi klien (*Client Agent*) belum memiliki integrasi CDP dan Crashpad yang dibutuhkan.
