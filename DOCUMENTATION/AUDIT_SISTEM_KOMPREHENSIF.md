# Laporan Audit Sistem Komprehensif (Server, Client & Alur Integrasi Dua Arah)

Laporan audit ini menyajikan analisis mendalam, struktur, dan pemetaan arsitektur lengkap dari **OSI AI Incident Analysis System**. Laporan ini disusun secara terstruktur untuk mencakup seluruh komponen server, sistem client (Agen), serta alur komunikasi dua arah (*uplink* dan *downlink*).

---

## 📋 Daftar Isi
- [1. Audit Arsitektur Sistem Server (Control Plane)](#1-audit-arsitektur-sistem-server-control-plane)
  - [1.1. Nginx Reverse Proxy (osi-nginx)](#11-nginx-reverse-proxy-osi-nginx)
  - [1.2. Go Ingestion Server (osi-ingestion-server)](#12-go-ingestion-server-osi-ingestion-server)
  - [1.3. Dashboard Server (osi-dashboard-server)](#13-dashboard-server-osi-dashboard-server)
  - [1.4. Secure Relay (osi-secure-relay)](#14-secure-relay-osi-secure-relay)
  - [1.5. Telegram Bot Listener (osi-telegram-bot)](#15-telegram-bot-listener-osi-telegram-bot)
  - [1.6. Database & Broker Layer](#16-database--broker-layer)
- [2. Audit Arsitektur Sistem Client (Agent 05 - Siap Distribusi)](#2-audit-arsitektur-sistem-client-agent-05---siap-distribusi)
  - [2.1. Windows Service (agent.exe)](#21-windows-service-agentexe)
  - [2.2. Watchdog Supervisor Internal (Go Agent Core)](#22-watchdog-supervisor-internal-go-agent-core)
  - [2.3. Aplikasi System Tray (agent_tray.exe)](#23-aplikasi-system-tray-agent_trayexe)
  - [2.4. Jendela Chat Dukungan (ChatForm.cs)](#24-jendela-chat-dukungan-chatformcs)
  - [2.5. Chrome Extension (Level 2 Web Tracking)](#25-chrome-extension-level-2-web-tracking)
- [3. Audit Alur Komunikasi Client-ke-Server (Uplink)](#3-audit-alur-komunikasi-client-ke-server-uplink)
  - [3.1. Aliran Data Telemetri & Aktivitas](#31-aliran-data-telemetri--aktivitas)
  - [3.2. Alur Inisiasi Chat & Kirim Diagnosis AI](#32-alur-inisiasi-chat--kirim-diagnosis-ai)
  - [3.3. Alur Unggah Berkas Lampiran Chat](#33-alur-unggah-berkas-lampiran-chat)
- [4. Audit Alur Komunikasi Server-ke-Client (Downlink)](#4-audit-alur-komunikasi-server-ke-client-downlink)
  - [4.1. Alur Eksekusi Perintah Remote (Remote Action)](#41-alur-eksekusi-perintah-remote-remote-action)
  - [4.2. Alur Balasan Chat Operator](#42-alur-balasan-chat-operator)
- [5. Evaluasi Ketahanan, Kinerja & Rekomendasi Keamanan](#5-evaluasi-ketahanan-kinerja--rekomendasi-keamanan)
  - [5.1. Mekanisme Ketahanan Jaringan (Fault Tolerance)](#51-mekanisme-ketahanan-jaringan-fault-tolerance)
  - [5.2. Evaluasi Kinerja (Performance Benchmarks)](#52-evaluasi-kinerja-performance-benchmarks)
  - [5.3. Peta Pengamanan & Rekomendasi Produksi](#53-peta-pengamanan--rekomendasi-produksi)
- [6. Peta Struktur Direktori Proyek (Workspace Directory Layout)](#6-peta-struktur-direktori-proyek-workspace-directory-layout)

---

## 1. Audit Arsitektur Sistem Server (Control Plane)

Control Plane berjalan di dalam ekosistem container Docker (WSL 2 Ubuntu) yang diatur menggunakan `docker-compose.yml`. Sistem ini melayani data NOC, pemrosesan telemetri, serta koordinasi chat.

```
                  [ Nginx Reverse Proxy (8099/9443) ]
                                   │
         ┌─────────────────────────┼─────────────────────────┐
         ▼                         ▼                         ▼
  [ Dashboard (9999) ]   [ Ingestion (18800) ]     [ Secure Relay (9998) ]
         │                         │                         │
         └───────────┬─────────────┴────────────┬────────────┘
                     ▼                          ▼
               [ Redis (6379) ]        [ PostgreSQL (5432) ]
                     ▲                          ▲
                     │                          │
                     └───────── [ Bot (Bot) ] ──┘
```

### 1.1. Nginx Reverse Proxy (`osi-nginx`)
- **Port Terbuka**: HTTP `8099`, HTTPS `9443`.
- **Fungsi**: Bertindak sebagai pintu gerbang utama (SSL termination). Merutekan permintaan web ke Dashboard Server, API Ingestion, dan static files.
- **Konfigurasi Keamanan**: Menggunakan sertifikat SSL TLSv1.2/TLSv1.3 lokal untuk mengenkripsi lalu lintas HTTP.

### 1.2. Go Ingestion Server (`osi-ingestion-server`)
- **Port Terbuka**: `18800` (API & WebSockets), `18802` (TCP Data Collector).
- **Teknologi**: Net HTTP Multiplexer (Go).
- **Fungsi**: 
  - Menerima log telemetri di endpoint `/telemetry`.
  - Menerima koneksi WebSocket chat client di `/api/chat/ws`.
  - Mengelola unggahan berkas chat di `/api/chat/upload` (melakukan kompresi otomatis gambar JPEG sebesar 75% kualitas, dan menyimpan berkas mentah untuk berkas `.zip`, `.pdf`, `.evtx`, `.log`, `.txt`, `.csv` pada `/app/uploads/chat/`).
  - Menyediakan layanan static file server untuk direktori `/uploads/` secara langsung di port `18800`.
  - Memicu analisis AI diagnosis anomali ketika payload diagnosis diterima dari client.

### 1.3. Dashboard Server (`osi-dashboard-server`)
- **Port Internal**: `9999`.
- **Teknologi**: Gin Web Framework (Go) + GORM.
- **Fungsi**: 
  - Menyajikan antarmuka NOC Frontend (HTML/CSS/JS) melalui rute HTTP.
  - Menyediakan gateway WebSocket `/ws/chat` untuk operator NOC.
  - Melayani query riwayat chat (`/api/chat/sessions`, `/api/chat/history`).
  - Menyediakan endpoint rekomendasi jawaban otomatis berbasis AI (`/api/chat/suggest`).
  - Menghubungkan visualisasi data telemetri, incident triage feed, causal DAG, dan analisis akar masalah (RCA).

### 1.4. Secure Relay (`osi-secure-relay`)
- **Port Terbuka**: `9998`.
- **Fungsi**: Bertindak sebagai jembatan isolasi untuk API Telegram. Menerima request payload pengiriman alert dari server, membuat tanda tangan digital HMAC SHA-256 menggunakan secret key, menambahkan timestamp, lalu mengirimkannya ke Telegram API. Hal ini mengisolasi token bot agar tidak terekspos langsung di server utama.

### 1.5. Telegram Bot Listener (`osi-telegram-bot`)
- **Fungsi**: Berjalan sebagai daemon yang memantau update dari Telegram Bot API. Jika mendeteksi operator melakukan swipe-reply di grup Telegram NOC, bot listener akan mengurai relasi pesan menggunakan tabel pemetaan (`telegram_chat_mappings`), menyimpan pesan balasan operator ke PostgreSQL, dan menyebarkannya kembali ke saluran Redis `chat_channel`.

### 1.6. Database & Broker Layer
- **PostgreSQL (`osi-postgres`)**: PostgreSQL 15. Menyimpan konfigurasi, data perangkat, log telemetri (terpartisi bulanan: `telemetry_logs_y2026mXX`), status insiden, data chat (`chat_sessions` dan `chat_messages`), serta pemetaan pesan Telegram (`telegram_chat_mappings`).
- **Redis (`osi-redis`)**: Redis 7. Bertindak sebagai broker pub/sub utama melalui saluran `chat_channel` untuk sinkronisasi pesan chat secara real-time antara Ingestion, Dashboard, dan Bot Listener. Juga menyimpan status kehadiran operator (`presence:operator`).
- **NATS (`osi-nats`)**: NATS 2.9. Menyediakan antrean pesan dengan latensi ultra-rendah untuk pemrosesan telemetri asinkron sebelum masuk ke database.

---

## 2. Audit Arsitektur Sistem Client (Agent 05 - Siap Distribusi)

Sistem client berjalan di platform Windows host sebagai agen service background dan aplikasi GUI system tray.

```
                             [ Windows SCM ]
                                    │
                                    ▼
                          [ OSI AI Agent Service ] (Command Port 10000)
                                    │
           ┌────────────────────────┼────────────────────────┐
           ▼                        ▼                        ▼
  [ Watchdog Loop ]       [ C# Tray App (10000) ]     [ Chrome Extension ]
  - AI Engine             - GDI+ Status Icon          - Level 2 Web Metrics
  - Telemetry             - Context Menu              - Direct API POST
  - Heartbeat             - Open ChatForm (ws)
```

### 2.1. Windows Service (`agent.exe`)
- **Nama Layanan**: `OSI AI Agent` (Display Name: `OSI AI Incident Analysis Agent`).
- **Tipe Start**: Delayed Automatic Start (mencegah kelebihan beban saat boot sistem).
- **Hak Akses**: Berjalan di bawah akun `LocalSystem` untuk akses hardware penuh.
- **Port Kontrol Lokal**: Membuka TCP listener di port `10000` localhost untuk menerima perintah kontrol dari aplikasi tray atau server.
- **Kebijakan Pemulihan SCM**: Jika service crash, Windows SCM dikonfigurasi untuk melakukan restart otomatis setelah **30 detik** (tanpa batasan limit restart di level SCM, diatur di registry failure counter).

### 2.2. Watchdog Supervisor Internal (Go Agent Core)
- **Tugas**: Memantau 8 modul runtime internal:
  1. `AI Engine` (inference lokal & RAG caching)
  2. `Scheduler` (penjadwal tugas diagnostik)
  3. `Telemetry Collector` (pengumpul data metrik)
  4. `Heartbeat` (sistem detak jantung berkala)
  5. `Remote Launcher` (pemanggil aplikasi remote access)
  6. `Remote Detection` (pendeteksi tool terpasang)
  7. `Auto Update` (sistem pembaruan versi)
  8. `Policy Engine` (pemberlaku batasan akses keamanan)
- **Mekanisme**: Setiap modul wajib memperbarui timestamp statusnya melalui metode `Touch()`. Watchdog berputar setiap 10 detik.
- **Safeguards Produksi**:
  - **Cooldown Restart**: Ada jeda cooldown selama 15 detik sebelum watchdog mencoba menghidupkan kembali modul yang mati.
  - **Eskalasi Limit**: Jika modul yang sama gagal/restart sebanyak 3 kali berturut-turut, watchdog menghentikan proses restart, menandai modul sebagai `Unhealthy` (`IsRunning = false`), dan langsung mengirimkan log alert error `FAILED` ke server.

### 2.3. Aplikasi System Tray (`agent_tray.exe`)
- **Teknologi**: C# WinForms & GDI+ (.NET Framework 4.5+).
- **Fungsi**: 
  - Berjalan sebagai antarmuka pengguna di taskbar pojok kanan bawah.
  - Melakukan polling perintah status `"GET_STATUS"` via TCP localhost ke port `10000` setiap 2 detik.
  - Menggambar ikon status secara dinamis menggunakan GDI+ (Hijau = Online, Merah = Offline, Kuning = Connecting, dll.) untuk menghemat resource memori.
  - Menyediakan menu klik kanan untuk meluncurkan dashboard NOC, menjeda monitoring, mengetes koneksi, dan membuka jendela chat.

### 2.4. Jendela Chat Dukungan (`ChatForm.cs`)
- **Tampilan**: Ukuran tetap 360px × 520px, tema gelap, tanpa bingkai, mendukung pemindahan jendela dengan drag-header.
- **WebSocket Socket**: Membuka WebSocket ke `ws://<SERVER_IP>:18800/api/chat/ws?client_id=<UUID>`.
- **Status Koneksi**: Menampilkan banner dinamis (`Connected` - Hijau, `Connecting...` - Oranye, `Reconnecting...` - Merah/Kuning).
- **Antrean Offline**: Pesan yang diketik saat offline disimpan di memori ram lokal, ditandai `⏳ Pending` pada UI, dan langsung di-flush otomatis berurutan saat status berubah menjadi `Connected`.
- **Clipboard & Drag-Drop**: Interseptor tombol `Ctrl+V` menyimpan gambar clipboard menjadi file png temporer dan menambahkannya ke lampiran. Input drag-drop file Windows Explorer langsung dikonfigurasi masuk sebagai lampiran baru.
- **Tangkapan Layar Global**: Menekan `Ctrl + Shift + S` memicu minimalisasi form otomatis, mengambil screenshot layar Windows utama, memulihkan form, dan menambahkannya ke bar lampiran.

### 2.5. Chrome Extension (Level 2 Web Tracking)
- **Fungsi**: Mengumpulkan metrik pemuatan halaman web (Timing API, latency, memory consumption) dan mendeteksi masalah konektivitas web (DNS failure, Timeout) secara independen.
- **Transmisi**: Mengirim data performa langsung melalui POST request ke port `8099/9443` (Dashboard API).

---

## 3. Audit Alur Komunikasi Client-ke-Server (Uplink)

Uplink adalah lalu lintas data dari client (Agen Windows / Browser) menuju ke Central Server untuk pemrosesan telemetri dan koordinasi support.

```
[ Client Agent ] ──( Port 18800 Telemetry )──▶ [ Go Ingestion Server ]
       │                                                 │
       ▼                                                 ▼
[ WMI Diagnostics ] ──( WebSocket Chat )──────▶ [ Redis / Postgres DB ]
                                                         │
                                                         ▼
                                               [ Mesin AI Diagnostics ]
```

### 3.1. Aliran Data Telemetri & Aktivitas
1. Modul pengumpul telemetri pada `agent.exe` mengumpulkan data performa hardware (CPU, memori, kapasitas disk drive).
2. Agen mengirimkan data JSON tersebut melalui HTTP POST ke endpoint `/telemetry` di Ingestion Server (Port `18800`).
3. Ingestion Server mengurai JSON, menormalisasi metrik melalui pipeline `normalization.go`, lalu mengirimkannya ke antrean broker Redis/NATS.
4. Pekerja database (worker database) membaca dari antrean asinkron dan memasukkan data tersebut ke dalam tabel partisi PostgreSQL bulanan.
5. Pembaruan telemetri dipublikasikan oleh Ingestion ke Redis `chat_channel` agar Dashboard NOC dapat menampilkan grafik secara real-time.

### 3.2. Alur Inisiasi Chat & Kirim Diagnosis AI
1. Pengguna membuka jendela chat dari system tray. Aplikasi C# membaca UUID dari `C:\ProgramData\Company\PC Health Agent\client_uuid.txt` dan menguji koneksi WS.
2. Pengguna mengklik tombol **"Start Chat"** pada welcome panel:
   - Jendela chat mengaktifkan modul pengumpul diagnosis sistem (WMI).
   - Agen mengumpulkan data beban CPU, penggunaan memori RAM, ruang disk kosong, status kesehatan SMART, status service spooler, nama-nama proses aktif, dan 5 baris error Event Viewer terbaru.
   - Agen mengirimkan payload diagnosis ini melalui WebSocket (tipe event: `"diagnostic"`).
3. Ingestion Server menerima event `"diagnostic"`, menyimpan log audit tersebut ke PostgreSQL sebagai chat sistem, dan memicu thread analisis AI secara paralel (`runAIDiagnosticAnalysis`).
4. Mesin AI mengevaluasi payload:
   - Jika mendeteksi kata kunci `"fail"` atau `"bad"` di log SMART: menandai masalah kritis hardware disk.
   - Jika mendeteksi status `Spooler = Stopped`: mendeteksi kerusakan service print spooler.
   - Jika mendeteksi penggunaan CPU >90%: merekomendasikan pemeriksaan aktivitas proses hogging.
5. Hasil diagnosis hipotesis AI disimpan sebagai pesan chat dengan tipe pengirim `AI_HYPOTHESIS` dan dipublikasikan ke Redis `chat_channel` agar operator NOC langsung melihat hipotesis troubleshooting sebelum membalas chat.
6. Notifikasi alert juga dikirim ke Secure Relay (Port `9998`) yang menandatangani payload dengan kode rahasia HMAC, lalu meneruskannya ke Telegram operator.

### 3.3. Alur Unggah Berkas Lampiran Chat
1. User melampirkan berkas (misal: log error atau tangkapan layar `Ctrl+Shift+S`).
2. Jendela chat melakukan HTTP POST multipart form data ke `http://<SERVER_IP>:18800/api/chat/upload`.
3. Ingestion Server menerima unggahan:
   - Jika ekstensi file adalah `.jpg`, `.jpeg`, atau `.png`, server melakukan kompresi kualitas gambar menjadi JPEG 75% untuk menghemat penyimpanan server.
   - Jika ekstensi adalah `.log`, `.zip`, `.pdf`, `.evtx`, atau `.csv`, server menyimpan file mentah tersebut ke direktori `/app/uploads/chat/` tanpa kompresi untuk menghindari kerusakan data log.
4. Server mengembalikan JSON respons berisi jalur relatif berkas (`uploads/chat/<unique_filename>`).
5. Jendela chat mengirim pesan chat melalui WebSocket dengan menyertakan jalur relatif tersebut di kolom `attachment_path`.

---

## 4. Audit Alur Komunikasi Server-ke-Client (Downlink)

Downlink adalah perintah atau balasan pesan dari NOC Dashboard / Telegram operator yang dikirimkan menuju ke client Windows untuk dieksekusi atau ditampilkan.

```
[ Operator Telegram ] ──( Swipe Reply )──────────▶ [ Secure Relay (9998) ]
                                                         │
                                                         ▼
[ Dashboard NOC ] ──( WS/REST Send Chat )──▶ [ Go Ingestion Server ]
                                                         │
                                                         ▼
[ Windows Client ] ◀──( TCP Port 10000 )───── [ Local Agent Control ]
```

### 4.1. Alur Eksekusi Perintah Remote (Remote Action)
1. Operator NOC memilih perintah aksi jarak jauh (misal: `RESTART_SPOOLER` atau `SHOW_ROUTE`) untuk perangkat tertentu di Dashboard UI.
2. Dashboard mengirim request HTTP POST ke `/api/remote/launch/:tool` atau `/api/orchestrator/command`.
3. Dashboard meneruskan request ke Ingestion Server (Port `18800`).
4. Ingestion Server mencari alamat IP aktif client di database, lalu membuat koneksi soket TCP langsung ke port `10000` (port kontrol lokal agen) pada PC client target.
5. Layanan agen Windows (`agent.exe`) menerima perintah JSON di port `10000`:
   - Mengevaluasi tipe perintah terhadap kebijakan keamanan (`Policy Engine`). Perintah berbahaya seperti `SHUTDOWN` langsung ditolak dengan status `FAILED: Shutdown command is disabled by local system policy`.
   - Mengeksekusi perintah sistem yang diizinkan (misal: menghentikan spooler, membersihkan direktori `PRINTERS\*`, dan menyalakan kembali spooler untuk perintah `CLEAR_SPOOLER`).
6. Agen mengembalikan respons stdout/stderr melalui soket TCP kembali ke Ingestion Server.
7. Ingestion Server mengembalikan output tersebut ke Dashboard NOC untuk dirender di panel log remote operator. Agen juga menampilkan notifikasi balloon tip Windows secara lokal untuk memberitahu user Windows bahwa perbaikan sistem sedang dilakukan.

### 4.2. Alur Balasan Chat Operator
- **Dari Dashboard**:
  1. Operator mengetik balasan di chat feed dan mengirimkannya via WebSocket ke `/ws/chat`.
  2. Dashboard Server menyimpan pesan tersebut ke database dengan pengirim `"OPERATOR"`, mengubah status sesi menjadi `"ACTIVE"`, lalu mempublikasikannya ke Redis `chat_channel`.
  3. Ingestion Server mendeteksi pesan baru di Redis, mencari koneksi WebSocket aktif client yang dituju di memori RAM, lalu mengirimkan data pesan tersebut ke client C#.
  4. Aplikasi client C# menerima pesan, memperbarui gelembung pesan di UI, memicu notifikasi desktop, dan membalas dengan status `"read_receipt"` ke WebSocket jika jendela chat sedang aktif fokus.
- **Dari Telegram**:
  1. Operator melakukan swipe-reply pada pesan alert di grup Telegram NOC.
  2. Telegram Bot Listener menerima event webhook, memanggil database untuk mencari client UUID yang terasosiasi dengan ID pesan Telegram tersebut di tabel `telegram_chat_mappings`.
  3. Bot Listener menyimpan pesan balasan ke database dengan pengirim `"OPERATOR"` dan mempublikasikannya ke Redis `chat_channel`.
  4. Ingestion Server mendeteksi pesan di Redis dan meneruskannya ke WebSocket client Windows yang sesuai.

---

## 5. Evaluasi Ketahanan, Kinerja & Rekomendasi Keamanan

### 5.1. Mekanisme Ketahanan Jaringan (Fault Tolerance)
- **Exponential Backoff**: Jaringan heartbeat client menggunakan jeda dinamis yang meningkat (5 detik ➔ 10 detik ➔ 30 detik ➔ 60 detik ➔ maksimum 120 detik) ketika mendeteksi koneksi ke central server gagal. Hal ini menghindari penumpukan request (DDoS internal) saat server baru saja pulih. Jeda kembali ke 5 detik saat terhubung normal.
- **Local Telemetry Cache**: Telemetry log yang gagal dikirim selama status offline disimpan ke dalam file cache lokal di `%ProgramData%\Company\PC Health Agent\cache\`. Begitu server online, data dikirim secara bertahap untuk mencegah lonjakan beban database.

### 5.2. Evaluasi Kinerja (Performance Benchmarks)
- **Asynchronous DB Writes**: Ingestion server tidak langsung menulis data telemetri ke PostgreSQL. Data dialirkan ke antrean Redis/NATS terlebih dahulu, kemudian ditulis secara massal (batch insert) oleh processor worker untuk meminimalkan beban I/O PostgreSQL.
- **GDI+ UI Lightweight**: Penggunaan rendering manual GDI+ pada `agent_tray.exe` memastikan footprint memori tray sangat kecil (<15MB RAM) dan tidak membebani performa komputer client.

### 5.3. Peta Pengamanan & Rekomendasi Produksi
- Peta Pengamanan & Rekomendasi Produksi:
  - **Firewall Isolation**: Pastikan port `5432` (PostgreSQL) dan port `6379` (Redis) terisolasi dan tidak dibuka untuk jaringan luar (hanya diakses via internal docker network). Port yang boleh diekspos ke publik hanyalah Port `8099`/`9443` (Nginx) dan Port `18800` (Ingestion Server).
  - **HMAC Verification**: Relay pesan Telegram dilindungi oleh verifikasi tanda tangan digital HMAC. Setiap request wajib divalidasi timestamp-nya (toleransi perbedaan waktu maksimum 5 menit) untuk mencegah serangan *Replay Attack*.
  - **Rate Limiting**: Direkomendasikan untuk mengaktifkan batas rate-limiting pada endpoint `/api/chat/upload` di Nginx (maksimum 10 unggahan per menit per IP) untuk mencegah kehabisan kapasitas penyimpanan server akibat spamming file sampah.

---

## 6. Peta Struktur Direktori Proyek (Workspace Directory Layout)

Berikut adalah peta struktur folder dan berkas repositori **OSI AI Incident Analysis System** secara komprehensif:

- `d:\AI-AGEN DRIVEN INTELLIGENT INCIDENT ANALIS\`
  - `CLIENT_DISTRIBUSI_GO/` (Modul Agen C# & Go Client)
    - `05_SIAP_DISTRIBUSI/` (Berisi installer siap pakai `PC_HEALTH_AGENT_Setup.exe`)
    - `agent/` (Source Code Aplikasi System Tray C# & Go Service)
      - `ChatForm.cs` (Jendela Chat Kustom Windows Forms)
      - `tray.cs` (Aplikasi Menu System Tray Windows)
      - `main.go` (Kode Utama Windows Service & Watchdog)
      - `compile_tray.bat` (Skrip Compiler C# csc.exe)
    - `installer/` (Prosedur Pembuatan Setup Wizard Inno Setup)
      - `setup.iss` (Skrip Compiler Inno Setup)
      - `main.go` (Skrip Registrasi Windows Service & Firewall)
    - `updater/` (Layanan Pembaruan Otomatis Client)
  - `SERVER/` (Source Code Go Core Server & Telemetry pipelines)
    - `go_core/` (Layanan Inti Go Ingestion)
      - `ingestion/` (Server WebSocket Chat & APIs Telemetry)
      - `telegram_bot/` (Bot Telegram Listener & Responder)
      - `database/` (Inisialisasi Database GORM & Migrasi Skema)
      - `ai/` (Mesin Evaluasi AI & Klasifikasi Masalah)
  - `portal/` (NOC Dashboard Web Portal)
    - `dashboard_server.go` (Dashboard Server Gin Web Framework)
    - `templates/` (Berkas Presentasi Web HTML, termasuk `index.html`)
    - `static/` (Layanan Aset CSS, JS, dan Media)
    - `relay/` (Source Code Secure Relay API)
  - `chrome_extension/` (Ekstensi Chrome untuk Pelacakan Web Level 2)
  - `DOCUMENTATION/` (Laporan Audit, Manual, & Dokumen Arsitektur Proyek)
    - `AUDIT_SISTEM_KOMPREHENSIF.md` (Berkas Laporan Audit Ini)
    - `PANDUAN_VERIFIKASI_DAN_PENGUJIAN_SISTEM.md` (Dokumen Panduan Pengujian)
  - `docker/` (Konfigurasi Image Nginx, Redis, dan PostgreSQL)
  - `docker-compose.yml` (Manajer Ekosistem Container Docker)
  - `START_SYSTEM_VERIFIED.bat` (Skrip Starter Gateway & PortProxy Windows)
