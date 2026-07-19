# Panduan Verifikasi dan Pengujian Sistem NOC (Production-Ready)

Dokumen ini mendefinisikan standar pengujian, checklist verifikasi, dan matriks kualitas untuk memastikan sistem **OSI AI Incident Analysis System** siap digunakan di lingkungan produksi (production-ready). Pengujian ini mencakup aspek fungsionalitas, ketahanan kegagalan (fault tolerance), kinerja di bawah beban tinggi (load & stress), keamanan sistem, dan kemampuan pemulihan (recovery).

---

## 📋 Daftar Isi
1. [Verifikasi Startup (Startup Verification)](#1-verifikasi-startup-startup-verification)
2. [Verifikasi Fungsional (Functional Verification)](#2-verifikasi-fungsional-functional-verification)
3. [Verifikasi Fitur Chat (Chat Verification)](#3-verifikasi-fitur-chat-chat-verification)
4. [Verifikasi Mesin AI (AI Verification)](#4-verifikasi-mesin-ai-ai-verification)
5. [Verifikasi Kegagalan (Failure Verification)](#5-verifikasi-kegagalan-failure-verification)
6. [Uji Beban & Stres (Load & Stress Test)](#6-uji-beban--stres-load--stress-test)
7. [Verifikasi Keamanan (Security Verification)](#7-verifikasi-keamanan-security-verification)
8. [Verifikasi Pemulihan (Recovery Verification)](#8-verifikasi-pemulihan-recovery-verification)
9. [Matriks Verifikasi Bug (Bug Verification Matrix)](#9-matriks-verifikasi-bug-bug-verification-matrix)
10. [Uji Regresi (Regression Test)](#10-uji-regresi-regression-test)

---

## 1. Verifikasi Startup (Startup Verification)

Memastikan seluruh layanan pendukung (backend, frontend, database, broker, agen) berjalan sempurna sejak awal booting.

### Checklist Layanan:
- [ ] **PostgreSQL**: Berstatus `Healthy`, menerima koneksi baca/tulis pada port `5432` dari Ingestion Server dan Dashboard.
- [ ] **Redis**: Berstatus `Healthy`, menerima koneksi pub/sub dan caching pada port `6379`.
- [ ] **Dashboard Server**: Berstatus `Healthy`, dapat diakses pada port `9999` (diteruskan oleh Nginx ke `8099/9443`).
- [ ] **Go Ingestion Server**: Berstatus `Healthy`, mendengarkan telemetry log dan socket chat pada port `18800` & `18802`.
- [ ] **Mesin AI Engine (RAG & Cognitive)**: Berstatus `Healthy`, dapat memproses query klasifikasi masalah dan pencarian knowledge base.
- [ ] **Telegram Bot Listener**: Berstatus `Healthy`, terhubung ke API Telegram dan aktif melakukan polling update.
- [ ] **Nginx Reverse Proxy**: Berstatus `Healthy`, merutekan HTTPS (Port `9443`) dan HTTP (Port `8099`) ke upstream yang sesuai.
- [ ] **Windows Agent Service**: Berstatus `Running` di Windows Services (SCM) dengan status delayed-auto start.
- [ ] **System Tray App (`agent_tray.exe`)**: Berstatus `Active` di pojok kanan bawah desktop Windows, ikon menunjukkan status koneksi aktual.
- [ ] **Chrome Extension**: Terpasang di browser client, aktif mengirimkan metrik halaman ke `/browser-events`.

---

## 2. Verifikasi Fungsional (Functional Verification)

Menguji alur kerja end-to-end dari saat instalasi agen hingga proses backup dan restore data sistem.

```
Install Agent ➔ Register Device ➔ Heartbeat ➔ Telemetry ➔ Issue Detection ➔ Dashboard ➔ Chat ➔ Telegram ➔ Remote Action ➔ AI Diagnostics ➔ Backup ➔ Restore
```

### Checklist Pengujian Alur:
1. [ ] **Install Agent**: Skrip installer (`PC_HEALTH_AGENT_Setup.exe`) berhasil dipasang tanpa error, menulis IP Server ke `server_ip.txt`.
2. [ ] **Register Device**: Agen otomatis mendaftarkan UUID baru ke server saat pertama kali dijalankan.
3. [ ] **Heartbeat**: Agen mengirimkan sinyal detak jantung berkala dan server memperbarui kolom `last_active`.
4. [ ] **Telemetry**: Agen mengirimkan data performa (CPU, RAM, Disk) dan tersimpan di tabel partisi database.
5. [ ] **Issue Detection**: Simulasi pemicu masalah (misal: mematikan Print Spooler) terdeteksi oleh modul watchdog dan memicu alert.
6. [ ] **Dashboard Update**: Alert masalah muncul secara real-time di UI Dashboard melalui WebSocket tanpa refresh halaman.
7. [ ] **Chat Session**: Client membuka jendela chat kustom dari tray, memicu pengiriman diagnosis.
8. [ ] **Telegram Sync**: Pesan chat dari client diteruskan oleh Secure Relay ke grup Telegram operator.
9. [ ] **Remote Action**: Operator memicu aksi remote (misal: `RESTART_SPOOLER`) dari dashboard, agen mengeksekusi dan mengembalikan output.
10. [ ] **AI Diagnostics**: AI Engine memproses log diagnosis sistem dan memunculkan rekomendasi troubleshooting otomatis.
11. [ ] **Backup**: Skrip `backup_system.ps1` berhasil membuat file `.zip` terenkripsi AES-256 yang berisi manifest, dump database, dan volume.
12. [ ] **Restore**: Skrip `restore_system.ps1` berhasil memulihkan database dan volume ke kondisi awal setelah simulasi kerusakan.

---

## 3. Verifikasi Fitur Chat (Chat Verification)

Memastikan fitur chat kustom real-time antara client Windows dengan NOC Dashboard dan operator Telegram bekerja 100% tanpa hambatan.

### Checklist Fitur Chat:
- [ ] **Open Chat**: Klik dua kali pada ikon system tray membuka jendela chat dengan transisi cepat.
- [ ] **Close Chat**: Klik tombol close (`X`) menyembunyikan jendela chat ke tray (bukan menghentikan aplikasi tray).
- [ ] **Hide to Tray**: Klik tombol minimize (`—`) atau menutup jendela chat meminimalkannya dengan ikon tray tetap aktif.
- [ ] **Re-open**: Membuka kembali dari tray menampilkan riwayat percakapan sebelumnya tanpa memuat ulang koneksi dari nol.
- [ ] **Send Text**: Mengirim pesan teks biasa ke dashboard/Telegram secara instan (<0.2 detik).
- [ ] **Send Emoji**: Mendukung pengiriman dan rendering karakter Unicode/emoji.
- [ ] **Send Screenshot**: Klik tombol kamera meminimalkan jendela chat, mengambil screenshot layar utama, dan menambahkannya ke lampiran.
- [ ] **Send ZIP**: Mengirim file terkompresi `.zip` tanpa kompresi tambahan (disimpan sebagai file mentah di `/uploads/chat/`).
- [ ] **Send LOG**: Mengirim berkas `.log` atau `.txt` dan dapat diunduh oleh operator NOC dengan format yang tidak rusak.
- [ ] **Ctrl+V Support**: Menempel gambar langsung dari clipboard Windows ke area input chat otomatis membuat pratinjau gambar.
- [ ] **Drag & Drop**: Menyeret file dari Windows Explorer langsung ke jendela chat menambahkan file tersebut sebagai lampiran.
- [ ] **Multiple Upload**: Mendukung pengiriman hingga 5 file lampiran sekaligus dalam satu pesan.
- [ ] **Offline Queue**: Saat koneksi terputus, pesan yang dikirim ditandai status `⏳ Pending` di UI lokal dan otomatis terkirim saat online kembali.
- [ ] **Read Receipt**: Menampilkan tanda centang satu (`✓`) saat terkirim, centang dua abu-abu (`✓✓`) saat sampai di server, dan centang dua biru (`✓✓ Read`) saat dibaca operator.
- [ ] **Typing Indicator**: Menampilkan status "Operator is typing..." ketika operator sedang mengetik balasan di dashboard.
- [ ] **Search Chat**: Bilah pencarian lokal menyaring pesan yang cocok di layar chat secara instan.
- [ ] **AI Suggested Reply**: Munculnya 3 saran balasan otomatis di dashboard operator berdasarkan hasil analisis diagnosis masalah.
- [ ] **Telegram Reply**: Operator membalas pesan di grup Telegram menggunakan fitur swipe-reply, pesan masuk kembali ke window chat user Windows.
- [ ] **Dashboard Reply**: Operator membalas dari dashboard, pesan terkirim secara real-time ke jendela chat client.
- [ ] **Balloon Notification**: Memunculkan notifikasi balloon tip Windows di pojok kanan bawah saat ada pesan masuk saat jendela chat ditutup.
- [ ] **Auto Reconnect**: Koneksi chat otomatis tersambung kembali saat jaringan kembali aktif tanpa restart aplikasi.

---

## 4. Verifikasi Mesin AI (AI Verification)

Memastikan model penalaran kognitif AI memberikan hasil diagnosis yang akurat, konsisten, dan bebas dari error crash atau timeout.

### Skenario Uji AI:
1. **Beban CPU Tinggi**:
   - *Input Diagnosis*: CPU Load `98%` oleh proses `chrome.exe`.
   - *Target AI Output*: Klasifikasi anomaly `HIGH_CPU_LOAD` dengan tingkat keyakinan (Confidence) `>90%` dan saran untuk memeriksa tab browser.
2. **Kesehatan Harddisk Buruk**:
   - *Input Diagnosis*: SMART Status `PredictFailure = True` pada disk drive.
   - *Target AI Output*: Klasifikasi anomaly `CRITICAL_HARDWARE_FAILURE` dengan saran penggantian media penyimpanan segera.
3. **Printer Spooler Mati**:
   - *Input Diagnosis*: Status service `Spooler = Stopped`.
   - *Target AI Output*: Rekomendasi menjalankan perintah otomatis `CLEAR_SPOOLER` atau `RESTART_SPOOLER`.

### Target Kualitas AI:
- [ ] **Bebas Crash**: Model tidak boleh menyebabkan panic atau crash pada server Go Ingestion saat menerima payload besar.
- [ ] **Bebas Timeout**: Waktu pemrosesan diagnosis AI tidak boleh melebihi 3 detik.
- [ ] **Konsistensi**: Parameter input yang sama harus menghasilkan hipotesis diagnosis yang sama (deterministik).

---

## 5. Verifikasi Kegagalan (Failure Verification)

Simulasi kegagalan infrastruktur untuk menguji tingkat ketahanan sistem (*fault tolerance*).

### Skenario Kegagalan & Hasil yang Diharapkan:
1. **Cabut Kabel LAN**:
   - *Aksi*: Matikan koneksi jaringan pada PC client.
   - *Ekspektasi*: Agen tray beralih ke status `OFFLINE` (Merah). Log telemetri disimpan dalam antrean cache lokal. Jendela chat menampilkan status `Reconnecting...`.
2. **Sambungkan Kabel LAN Kembali**:
   - *Aksi*: Nyalakan kembali koneksi jaringan PC client.
   - *Ekspektasi*: Agen otomatis terhubung kembali, flush antrean cache telemetri lokal ke server, status chat kembali `CONNECTED` (Hijau), dan mengirim pesan pending.
3. **Matikan Redis Cache Server**:
   - *Aksi*: Hentikan container `osi-redis` (`docker stop osi-redis`).
   - *Ekspektasi*: Dashboard server tetap hidup, beralih menggunakan PostgreSQL sebagai fallback status sementara, dan otomatis terhubung kembali saat Redis dihidupkan.
4. **Matikan PostgreSQL Database**:
   - *Aksi*: Hentikan container `osi-postgres`.
   - *Ekspektasi*: Ingestion server dan Agen client tidak boleh crash. Agen harus menyimpan data telemetri di cache lokal sampai database menyala kembali.
5. **Restart Docker Engine**:
   - *Aksi*: Lakukan restart docker service pada WSL host.
   - *Ekspektasi*: Nginx, Dashboard, Ingestion, dan Relay otomatis menyala kembali. Agen client Windows mendeteksi koneksi putus dan melakukan reconnect otomatis.
6. **Telegram API Down / Bot Mati**:
   - *Aksi*: Hentikan container `osi-telegram-bot`.
   - *Ekspektasi*: Chat di Dashboard NOC tetap berjalan normal. Sistem antrean pengiriman alert mendeteksi kegagalan kirim ke Telegram tanpa memblokir database.

---

## 6. Uji Beban & Stres (Load & Stress Test)

Menguji performa sistem di bawah batas beban operasional maksimum untuk mendeteksi adanya bottleneck memori atau bottleneck koneksi.

### Skenario Uji Beban (Load Test):
- **Beban**: Simulasi 500 client mengirimkan telemetry detak jantung (heartbeat) secara bersamaan, melakukan chat real-time, dan mengunggah gambar screenshot.
- **Metrik Pemantauan**:
  - Penggunaan CPU & RAM pada Ingestion Server (Target: < 40% CPU, < 512MB RAM).
  - Beban koneksi aktif Redis & PostgreSQL (Target: Koneksi tidak drop atau ditolak).
  - Waktu respons WebSocket chat (Target: Latensi pesan tetap < 0.5 detik).

### Skenario Uji Stres (Stress Test):
- **Beban**: Operator menguji pengiriman 1.000 file screenshot secara serentak, atau 100 pesan chat dikirim dalam 1 detik.
- **Kriteria Kelulusan**:
  - Sistem tidak boleh mengalami Out Of Memory (OOM).
  - Sistem tidak boleh mengalami deadlock pada database (GORM connections pool terkonfigurasi dengan baik).
  - Tidak ada data chat yang hilang (semua tersimpan di DB secara asinkron/antrean).

---

## 7. Verifikasi Keamanan (Security Verification)

Aspek pengujian keamanan mutlak diperlukan untuk mencegah penyalahgunaan sistem NOC oleh pihak luar.

### Checklist Pengujian Keamanan:
- [ ] **Authentication**: Seluruh akses ke API dashboard wajib divalidasi dengan JWT token yang valid.
- [ ] **Authorization**: Hanya operator dengan role ADMIN/OPERATOR yang dapat mengeksekusi Remote Action di PC client.
- [ ] **JWT Session Validation**: Token JWT kedaluwarsa setelah waktu tertentu dan otomatis mengharuskan login ulang.
- [ ] **SQL Injection Protection**: Semua query database menggunakan GORM parameterized queries untuk mencegah injeksi SQL.
- [ ] **Cross-Site Scripting (XSS)**: Area input chat di dashboard dan client dibersihkan (sanitized) untuk mencegah injeksi tag `<script>` atau HTML berbahaya.
- [ ] **CSRF Protection**: Seluruh request state-changing dilindungi dengan token anti-CSRF atau CORS origin checks yang ketat.
- [ ] **Directory Traversal**: Handler unggahan chat memvalidasi ekstensi dan nama file, mencegah file path traversal (seperti `../../etc/passwd`).
- [ ] **Malware Upload Protection**: File exe atau berkas script yang diunggah divalidasi ekstensinya dan ditolak jika tidak masuk whitelist (.jpg, .png, .txt, .log, .zip, .pdf, .evtx, .csv).
- [ ] **Oversized File Filter**: Batas ukuran unggahan diatur maksimum 15MB. Request di atas batas langsung ditolak dengan status HTTP 413.
- [ ] **Rate Limiting**: Rate limiter berbasis Redis diaktifkan pada Ingestion endpoint untuk mencegah serangan DDoS atau spamming chat.
- [ ] **WebSocket Hijack**: Validasi `Origin` header dilakukan saat proses upgrade koneksi HTTP ke WebSocket.
- [ ] **Replay Attack**: Payload Relay Telegram menyertakan tanda tangan HMAC (`X-Signature`) dengan timestamp unik yang divalidasi agar request lama tidak bisa dikirim ulang.
- [ ] **Telegram Spoofing**: Operator Telegram divalidasi ID-nya (`AUTHORIZED_ADMINS`) untuk memastikan hanya staf NOC yang sah yang dapat membalas pesan chat ke client.

---

## 8. Verifikasi Pemulihan (Recovery Verification)

Menguji kemampuan sistem untuk pulih secara otomatis ke kondisi operasional normal setelah terjadi pemadaman listrik atau crash total pada server (*Cold Start Recovery*).

### Skenario Pemulihan:
1. **Server Mati Total (Power Off)**: Simulasikan server tiba-tiba kehilangan daya listrik (hard shutdown).
2. **Server Menyala Kembali (Power On)**: Nyalakan kembali server fisik/virtual.
3. **Ekspektasi Status Otomatis**:
   - [ ] Layanan Docker Compose menyala secara otomatis (restart policy: `always`).
   - [ ] Windows Agent Service otomatis berjalan kembali (Delayed Auto Start).
   - [ ] Ikon Tray client Windows mendeteksi server telah menyala dan menghubungkan kembali socket.
   - [ ] Heartbeat dan data telemetri mulai masuk kembali ke database secara normal.
   - [ ] Data Redis dipulihkan dari file `.rdb` dan dashboard menyajikan status sistem terupdate.

---

## 9. Matriks Verifikasi Bug (Bug Verification Matrix)

Format tabel berikut wajib digunakan untuk mendokumentasikan, memantau, dan melakukan pengujian ulang (*retesting*) terhadap bug yang ditemukan selama siklus hidup proyek.

| Modul | ID Case | Skenario Uji | Status Awal | Deskripsi Bug | Solusi / Fix | Status Retest | Penanggung Jawab |
| :--- | :--- | :--- | :---: | :--- | :--- | :---: | :--- |
| **Agent** | AG-01 | Instalasi Agen Baru | ❌ | IP Server tidak tertulis pada file `server_ip.txt` | Diperbaiki pada prosedur `CurStepChanged` installer | ✅ | Dev Agent |
| **Agent** | AG-02 | Pengiriman Heartbeat | ✅ | - | - | ✅ | Dev Agent |
| **Chat** | CH-01 | Pengiriman Screenshot | ❌ | Base64 gambar terlalu besar, PostgreSQL error | Gambar dikompresi ke JPEG 75% & disimpan di disk | ✅ | Dev Ingestion |
| **Chat** | CH-02 | Antrean Offline | ✅ | - | - | ✅ | Dev Agent |
| **AI** | AI-01 | Diagnosis Analisis | ❌ | Variabel `disk` tidak terpakai menyebabkan compiler crash | Memperbaiki referensi logika di `runAIDiagnosticAnalysis` | ✅ | Dev Ingestion |
| **Telegram**| TG-01 | Swipe-Reply Balasan | ❌ | ID Pesan Telegram tidak terpetakan ke Client UUID | Membuat tabel relasi `telegram_chat_mappings` | ✅ | Dev Bot |
| **Dashboard**| DB-01 | Pembaruan Live Chat | ❌ | Syntax error bracket `/api/auth/login` | Memperbaiki penutup kurung kurawal di router Gin | ✅ | Dev Portal |

---

## 10. Uji Regresi (Regression Test)

Setiap kali ada perubahan kode atau rilis versi baru (misalnya perbaikan modul atau penambahan fitur), seluruh rangkaian uji utama berikut **wajib dijalankan ulang** untuk menjamin tidak ada fitur lama yang rusak akibat kode baru.

```
Build All Components ➔ Install & Run ➔ Verify Heartbeat ➔ Verify Telemetry ➔ Test Live Chat ➔ Trigger AI Diagnostics ➔ Verify Remote Tools ➔ Execute Backup ➔ Verify Restore
```

### Prosedur Uji Regresi:
1. **Kompilasi Ulang**: Jalankan `compile_tray.bat` dan build Go services. Pastikan tidak ada kegagalan build.
2. **Instal Ulang Agen**: Jalankan setup wizard untuk menimpa instalasi lama. Pastikan konfigurasi tersimpan.
3. **Monitor Telemetri**: Buka dashboard dan pastikan metrik CPU/RAM dari PC target diperbarui secara real-time.
4. **Verifikasi Fitur Chat**: Kirim pesan teks, kirim lampiran gambar, lakukan paste gambar, dan uji balasan dari Telegram.
5. **Uji Remote Action**: Jalankan perintah `SHOW_ROUTE` dan `RESTART_SPOOLER` dari dashboard.
6. **Verifikasi Backup**: Buat arsip cadangan baru dan uji coba restorasi pada lab pengujian.
