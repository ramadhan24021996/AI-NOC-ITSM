# Laporan Kesiapan Produksi (Production Readiness Report)

Laporan ini menyajikan evaluasi akhir, penilaian arsitektur, analisis risiko, serta kesimpulan kesiapan rilis dari **OSI AI Incident Analysis System** untuk di-deploy pada lingkungan produksi berskala *Enterprise-grade NOC*.

---

## 🚦 Status Kesiapan Sistem (Readiness Status)

Status Kesiapan Produksi: **🔴 NOT READY (BELUM SIAP PRODUKSI)**

> [!WARNING]
> Meskipun arsitektur dasar terdistribusi (Go + Redis + NATS + PostgreSQL) telah dirancang dengan alur integrasi dua arah yang sangat baik, sistem saat ini masih memiliki celah keamanan kritis (*critical vulnerabilities*) dan kelemahan stabilitas di bawah kondisi beban tinggi (*load stability issue*) yang harus diperbaiki terlebih dahulu sebelum rilis produksi dilakukan. Status "READY" hanya dapat diberikan setelah rekomendasi pengerasan (*hardening*) di laporan ini selesai diimplementasikan secara menyeluruh.

---

## ⚠️ Risiko Utama Sistem (Core Risks)

1. **Remote Execution Tanpa Otentikasi (Port 10000 Bypass)**:
   Layanan Windows Agent `agent.exe` mendengarkan perintah kontrol pada TCP Port `10000` tanpa adanya mekanisme otentikasi (token handshake). Walaupun port ini dirancang hanya melayani koneksi lokal, apabila terjadi kesalahan konfigurasi Windows Firewall di sisi client, penyerang di jaringan LAN yang sama dapat mengirimkan payload JSON langsung ke port `10000` untuk memicu aksi perbaikan sistem dengan hak akses *SYSTEM* tanpa otentikasi admin.
2. **Cross-Site Scripting (XSS) di Dashboard NOC**:
   Data telemetri (misalnya nama proses Windows) atau pesan chat yang mengandung karakter tag HTML tidak disanitasi sebelum dirender menggunakan properti `.innerHTML` di Javascript dashboard. Penyerang dapat menyuntikkan script jahat untuk mencuri JWT token session operator NOC (*session hijacking*).
3. **Kebocoran Memori (Memory Leak) di Terminal Pengguna**:
   Aplikasi tray C# `agent_tray.exe` mengalami kebocoran resource handle grafis GDI+ secara konstan. Layanan ini akan mengalami crash otomatis setelah 3-5 hari berjalan terus-menerus di komputer pengguna, menghilangkan kemampuan interaksi chat bantuan bagi pengguna.

---

## ⚙️ Bottleneck Utama (Core Bottlenecks)

1. **Lock Contention PostgreSQL pada Operasi Telemetri**:
   Ketika jumlah client aktif mencapai >1.000, proses update status online perangkat (`devices` table status updates) memicu tabrakan lock indeks database. PostgreSQL terpaksa melakukan antrean penulisan sequential, meningkatkan latensi baca-tulis, dan dapat memicu kegagalan database connection pool starvation.
2. **Kompresi Gambar Sinkron pada Thread Upload**:
   Proses resize dan kompresi JPEG 75% untuk berkas tangkapan layar chat diproses secara synchronous langsung di thread Ingestion server saat request HTTP POST upload diterima. Hal ini menghabiskan resource CPU server dengan cepat ketika ratusan pengguna mengunggah screenshot secara bersamaan.

---

## ☠️ Skenario Kegagalan Paling Berbahaya (High-Risk Failure Scenarios)

### Skenario 1: Cascade Disconnect akibat Thundering Herd
Apabila terjadi gangguan jaringan pusat sesaat, seluruh client Windows (misalnya 3.000 client) akan terputus dari server. Saat koneksi pulih, mekanisme reconnect client yang agresif tanpa jeda acak (jitter) akan membanjiri server dengan request handshake HTTP WebSocket secara serentak. Beban CPU server melonjak hingga 100%, file descriptor OS terlampaui, dan server menolak koneksi baru, memicu loop pemutusan koneksi massal yang tidak dapat pulih dengan sendirinya (*persistent outage*).

### Skenario 2: Remote command Hang pada Client Offline
Apabila operator memicu perintah remote perbaikan sistem ke komputer client yang status jaringannya tiba-tiba terputus tepat setelah perintah dikirim, ketiadaan socket timeout di sisi Ingestion server akan menahan thread socket dalam kondisi `ESTABLISHED` (TCP half-open socket). Jika operator mencoba memicu perintah remote ke puluhan client lain yang juga offline, seluruh connection pool TCP server akan habis terkunci, membekukan modul remote control untuk seluruh operator dashboard.

---

## 🛡️ Rekomendasi Hardening (Security & Stability Hardening)

1. **Otentikasi Handshake Port 10000**:
   Implementasikan enkripsi TLS lokal atau minimal mekanisme otentikasi token rahasia bersama (Pre-Shared Key) pada port `10000`. Windows Service harus menolak setiap request JSON yang tidak menyertakan HMAC signature yang divalidasi menggunakan token rahasia lokal yang disimpan secara aman di folder `%ProgramData%` yang dilindungi ACL ketat.
2. **Strict Loopback Binding**:
   Pastikan kode program Go agen secara eksplisit membatasi socket binding port `10000` **HANYA** pada alamat localhost `127.0.0.1` (bukan wildcard `0.0.0.0`):
   ```go
   listener, err := net.Listen("tcp", "127.0.0.1:10000")
   ```
3. **Escaping Output UI di Dashboard**:
   Ganti seluruh manipulasi DOM Javascript di file `templates/index.html` dari `.innerHTML` menjadi `.textContent` atau gunakan library sanitasi HTML seperti DOMPurify sebelum merender payload chat client ke dashboard.
4. **Implementasi Anti-CSRF & JWT di Remote Endpoint**:
   Tambahkan middleware otentikasi token JWT yang ketat dan verifikasi CORS origin pada Nginx reverse proxy untuk seluruh rute API `/api/remote/*` dan `/api/orchestrator/*`.

---

## 📈 Rekomendasi Scaling (Scaling Plan)

1. **Asynchronous Batch DB Writer**:
   Jangan biarkan server Ingestion menulis telemetri langsung ke PostgreSQL. Ubah arsitektur agar telemetri ditulis ke Redis List/NATS JetStream. Buat worker service terpisah yang melakukan penarikan pesan (*pull queue*) dan melakukan penulisan massal (*bulk insert*) ke PostgreSQL setiap 10 detik atau setiap 500 records.
2. **WebSocket Load Balancer**:
   Terapkan horizontal scaling untuk Go Ingestion Server dengan menjalankan minimal 3 replica container di belakang Nginx/HAProxy. Gunakan algoritma *Least Connections* dengan konfigurasi *Session Sticky (ip_hash)* untuk membagi rata ribuan koneksi WebSocket client secara merata.
3. **Asynchronous Image Processing**:
   Ubah pemrosesan unggahan file. Ingestion server harus segera menyimpan file mentah ke folder temporary disk dan langsung mengembalikan respons HTTP 200 OK dengan path file. Tugas pemrosesan/kompresi gambar harus dialihkan ke worker background terpisah menggunakan Redis Queue (antrean asinkron) agar tidak memblokir server utama.

---

## 📊 Penilaian Skor Arsitektur (Architecture Score Card)

| Kategori | Skor | Catatan Evaluasi |
| :--- | :---: | :--- |
| **Architecture** | **7 / 10** | Desain distributed (Go + NATS + Redis + Postgres) sangat modular dan decoupling component berjalan baik. Namun, logika komunikasi downlink TCP direct connection masih memiliki dependency langsung. |
| **Stability** | **6 / 10** | Ketahanan local caching telemetry dan watchdog internal bekerja dengan baik. Nilai dikurangi karena kerentanan thundering herd reconnection dan crash memory leak pada tray UI. |
| **Security** | **5 / 10** | Nilai terendah karena tidak adanya otentikasi token pada port perintah agen lokal `10000`, ketiadaan sanitasi input XSS di dashboard, dan kerentanan CSRF pada rute remote action. |
| **Performance** | **6 / 10** | Throughput pub/sub Redis stabil. Bottleneck terjadi pada synchronous JPEG image compression dan PostgreSQL lock contention di bawah beban 5.000 client. |
| **Observability** | **6 / 10** | Telemetri hardware client terpantau secara real-time. Perlu ditambahkan sistem tracing (seperti OpenTelemetry) dan visualisasi log tersentralisasi untuk mempermudah audit incident distributed. |

**Rekomendasi Akhir**:
Prioritaskan perbaikan celah keamanan kritis (Otentikasi Port 10000 + Sanitasi XSS Dashboard) dan perbaikan Memory Leak Tray UI terlebih dahulu. Setelah 3 masalah utama ini diperbaiki, sistem dapat dinyatakan **SIAP PRODUKSI** (status berubah menjadi **READY** dengan target skor keamanan naik menjadi **9/10**).
