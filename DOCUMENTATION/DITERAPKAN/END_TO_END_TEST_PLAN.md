# End-to-End Test Plan & Verification Flow

Dokumen ini mendefinisikan skenario pengujian end-to-end lengkap dari fase instalasi agen client hingga pemulihan kegagalan total sistem.

---

## 📋 Alur Verifikasi End-to-End (E2E)

```
[Langkah 1: Instalasi] ➔ [Langkah 2: Registrasi] ➔ [Langkah 3: Telemetri] ➔ [Langkah 4: Chat Sesi]
                                                                                │
[Langkah 8: Pemulihan] ◀ [Langkah 7: Gangguan] ◀ [Langkah 6: Remote] ◀ [Langkah 5: Telegram]
      │
      ▼
[Langkah 9: Backup & Restore] ➔ [Langkah 10: Pengujian Selesai]
```

---

## 🛠️ Detail Langkah demi Langkah (Step-by-Step Flow)

### Langkah 1: Instalasi Agen Baru (Client Installation)
- **Aksi**: Operator menjalankan file setup wizard `PC_HEALTH_AGENT_Setup.exe` pada mesin Windows client target.
- **Prosedur Manual**:
  1. Jalankan installer dengan hak akses administrator.
  2. Pada halaman konfigurasi server, masukkan IP central orchestrator (default: `10.20.0.163`).
  3. Selesaikan proses setup.
- **Validasi Kunci**:
  - Berkas `server_ip.txt` di `%ProgramData%\Company\PC Health Agent\config\` berhasil ditulis berisi alamat IP yang dimasukkan.
  - Windows Service `OSI AI Agent` terdaftar dengan delayed start, dan status berjalan (`Running`).
  - Aplikasi `agent_tray.exe` otomatis menyala, menampilkan ikon warna kuning (Connecting) lalu hijau (Online).

### Langkah 2: Registrasi Perangkat (Device Registration)
- **Aksi**: Agen service baru menghubungi server untuk pertama kali.
- **Prosedur**:
  1. Modul registrasi agen membaca berkas `client_uuid.txt` di `%ProgramData%\Company\PC Health Agent\`.
  2. Jika berkas kosong atau tidak ada, agen membuat UUID baru berbasis RFC 4122 dan menyimpannya ke berkas tersebut.
  3. Agen mengirim payload pendaftaran perangkat berisi UUID dan metadata sistem ke server.
- **Validasi Kunci**:
  - UUID baru terbuat di `client_uuid.txt`.
  - Tabel `devices` di database PostgreSQL memuat entri UUID baru tersebut beserta data hostname, IP LAN, dan versi agen.

### Langkah 3: Aliran Data Telemetri (Telemetry Streaming)
- **Aksi**: Mengamati kelancaran transmisi metrik performa client.
- **Prosedur**:
  1. Agen mulai mengirimkan payload telemetri (penggunaan CPU, RAM, detail disk) setiap 60 detik (konfigurasi `TelemetryInterval`).
  2. Dashboard NOC membuka dashboard visualisasi perangkat.
- **Validasi Kunci**:
  - Ingestion Server (Port 18800) menerima payload tanpa error (HTTP 200).
  - Data masuk secara teratur di tabel partisi database `telemetry_logs_y2026mXX`.
  - Grafik visualisasi performa perangkat di dashboard NOC terupdate secara real-time melalui event WebSocket.

### Langkah 4: Membuka Sesi Chat & Diagnostik AI (Live Chat Initiation)
- **Aksi**: Pengguna client memicu obrolan bantuan dan pelaporan kondisi sistem.
- **Prosedur**:
  1. Pengguna klik ganda ikon tray `agent_tray.exe`, memunculkan window chat kustom.
  2. Pengguna klik tombol **"Start Chat"** pada welcome panel chat.
- **Validasi Kunci**:
  - Jendela chat berhasil melakukan handshake WebSocket ke `/api/chat/ws`. Banner status berubah menjadi `🟢 Connected to Support Engine`.
  - Agen diam-diam menjalankan query WMI untuk mengumpulkan performa real-time, status SMART disk, daftar service windows, daftar proses browser aktif, dan baris error Event Viewer teranyar.
  - Payload diagnosis terkirim ke WebSocket. Ingestion Server langsung mengevaluasi data, memanggil AI Engine, dan menampilkan rekomendasi klasifikasi masalah (`AI_HYPOTHESIS`) di dashboard operator.
  - Sesi chat baru berstatus `WAITING_OPERATOR` tercatat di PostgreSQL.

### Langkah 5: Sinkronisasi Telegram & Balasan Operator (Telegram Integration)
- **Aksi**: Menguji alur komunikasi operator Telegram NOC.
- **Prosedur**:
  1. Secure Relay server mengirimkan alert chat sistem ke grup Telegram operator.
  2. Operator melakukan swipe-reply di Telegram, mengetik: `"Kami sedang mengecek sistem Anda, harap tunggu."`.
- **Validasi Kunci**:
  - Alert terkirim di grup Telegram. ID pesan Telegram tercatat di tabel `telegram_chat_mappings` berpasangan dengan Client UUID.
  - Pesan balasan Telegram operator berhasil diintersepsi oleh Bot Listener, disimpan di database PostgreSQL dengan tipe `OPERATOR`, dan dikirim ke Redis.
  - Jendela chat client Windows menerima balasan operator secara real-time dan menampilkan balon notifikasi tray jika form sedang ditutup.

### Langkah 6: Eksekusi Remote Action & Balloon Tip (Downlink Control)
- **Aksi**: Operator memicu perintah perbaikan sistem dari dashboard NOC.
- **Prosedur**:
  1. Operator mengklik tombol perbaikan remote (misal: **"Restart Spooler"** / `RESTART_SPOOLER`) di Dashboard UI.
- **Validasi Kunci**:
  - Dashboard mengirim perintah ke Ingestion Server, lalu Ingestion Server menyambungkan soket TCP ke port `10000` localhost client.
  - Agen Windows Service menerima perintah di port `10000`, memverifikasi kebijakan lokal, lalu menghentikan dan menyalakan kembali service spooler cetak secara lokal.
  - Agen mengembalikan status respons `SUCCESS` ke server, memunculkan notifikasi desktop balloon tip lokal pada komputer user, dan log eksekusi tampil di Dashboard NOC.

### Langkah 7: Simulasi Gangguan Jaringan (Offline Mode & Queue)
- **Aksi**: Memutus jaringan client untuk menguji antrean offline.
- **Prosedur**:
  1. Matikan interface jaringan PC client Windows.
  2. Pengguna mengetik pesan chat: `"Printer saya masih bermasalah!"` dan melampirkan log error.
- **Validasi Kunci**:
  - Jendela chat mendeteksi WebSocket terputus, menampilkan banner merah `⚠️ Reconnecting...`, dan mengaktifkan fallback polling timer HTTP.
  - Pesan chat dan file log yang diunggah disimpan di antrean memori lokal C# dan dirender dengan status `⏳ Pending` di layar chat.
  - Agen mendeteksi kegagalan kirim telemetri dan mulai mencadangkan telemetry log ke folder cache lokal di `%ProgramData%\Company\PC Health Agent\cache\`.

### Langkah 8: Pemulihan Jaringan & Sinkronisasi Ulang (Auto Reconnection)
- **Aksi**: Menyalakan kembali interface jaringan PC client.
- **Prosedur**:
  1. Hidupkan kembali koneksi internet/jaringan PC client Windows.
- **Validasi Kunci**:
  - Jendela chat mendeteksi sinyal pulih, melakukan handshake WebSocket sukses, banner berubah kembali menjadi hijau `🟢 Connected`.
  - Pesan antrean offline yang berstatus `⏳ Pending` otomatis dikirim berurutan ke WebSocket server dan statusnya di layar berubah menjadi `✓ Sent` atau `✓✓ Read`.
  - Telemetry log yang ter-caching lokal di-upload secara bertahap ke server Ingestion hingga folder cache kosong kembali.

### Langkah 9: Crash Recovery & Pemeliharaan (Restart & Recovery)
- **Aksi**: Uji pemulihan jika salah satu container server mati atau service Windows mati paksa.
- **Prosedur**:
  1. Matikan service Windows `OSI AI Agent` secara paksa dari Task Manager (End Process).
  2. Matikan container PostgreSQL dan Redis di server.
  3. Hidupkan kembali semua layanan.
- **Validasi Kunci**:
  - Windows SCM secara otomatis menghidupkan kembali service `OSI AI Agent` setelah 30 detik.
  - Container Docker otomatis menyala kembali (restart policy: `always`).
  - Setelah server pulih, agen tray client Windows otomatis melakukan reconnect ke database dan broker tanpa membutuhkan intervensi manual atau restart aplikasi.

### Langkah 10: Backup & Restore (Disaster Recovery Verification)
- **Aksi**: Memverifikasi pemulihan data pasca bencana sistem.
- **Prosedur**:
  1. Jalankan `backup_system.ps1` untuk membuat file backup `.zip` terenkripsi.
  2. Hapus tabel chat dan telemetri di PostgreSQL secara paksa untuk mensimulasikan kerusakan database.
  3. Jalankan `restore_system.ps1` menggunakan file backup tersebut.
- **Validasi Kunci**:
  - Proses pencadangan membuat file backup utuh beserta SHA256 checksum yang valid.
  - Proses restorasi berjalan lancar, memulihkan seluruh riwayat chat, konfigurasi router, dan data telemetri historis perangkat. Dashboard NOC kembali menyajikan data yang lengkap.
