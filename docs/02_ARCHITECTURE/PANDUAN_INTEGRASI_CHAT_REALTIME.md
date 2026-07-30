# Panduan Integrasi Chat Real-Time & Diagnosis AI (Client-NOC)

Dokumen ini mendokumentasikan implementasi dan verifikasi sistem komunikasi chat real-time antara aplikasi system tray client Windows (`agent_tray.exe`) dengan NOC Dashboard / Telegram Operator, lengkap dengan sistem pengumpulan diagnosis berbasis WMI dan analisis AI otomatis.

---

## 🚀 Fitur Utama yang Diimplementasikan

### 1. Window Chat Client Kustom (`ChatForm.cs`)
Jendela chat kustom dengan gaya gelap (dark theme) tanpa bingkai (borderless) berukuran tetap 360px × 520px telah diintegrasikan langsung ke dalam menu system tray:
- **WebSocket & Fallback HTTP Polling**: Menggunakan koneksi persisten `ClientWebSocket` ke endpoint `/api/chat/ws`. Jika jaringan terputus, status bar akan menampilkan `⚠️ Menghubungkan Kembali...` dan secara otomatis mengaktifkan fallback polling HTTP ke `/api/chat/poll` setiap 5 detik. Setelah jaringan kembali online, sistem akan beralih kembali ke WebSocket secara otomatis.
- **Pengumpul Diagnosis WMI Otomatis**: Ketika user mengklik tombol "Start Chat", agen akan mengumpulkan data spesifikasi sistem secara mendalam menggunakan WMI:
  - Beban CPU (CPU Load) dan tipe prosesor.
  - Penggunaan RAM (RAM Free vs Total).
  - Kapasitas disk drive (Free vs Total space).
  - Status kesehatan SMART pada disk.
  - Status service Windows penting (seperti Print Spooler / `Spooler` dan Windows Update / `wuauserv`).
  - Interface jaringan dan alamat IP aktif.
  - Daftar aplikasi/browser yang sedang berjalan.
  - Catatan error terbaru pada Event Log sistem (5 entri error terakhir).
  Data ini langsung dikirimkan ke server sebagai payload `"diagnostic"` untuk dianalisis oleh Mesin AI sebelum operator membalas pesan.
- **Antrean Pesan Offline (Offline Queue)**: Jika client sedang offline, pesan yang diketik akan masuk ke antrean lokal dengan status `⏳ Pending`. Begitu koneksi WebSocket terhubung kembali, seluruh antrean pesan akan dikirim secara berurutan ke server.
- **Dukungan Clipboard & Lampiran (Attachments)**:
  - Mendukung unggahan file lampiran (gambar, log, dokumen, file zip).
  - Mendukung aksi menempel gambar langsung dari clipboard (`Ctrl + V`). Sistem akan menyimpan file temporer dan menampilkannya di bilah pratinjau (attachment preview).
  - Lampiran non-gambar (seperti berkas `.log`, `.zip`, `.pdf`, `.evtx`, `.csv`) ditampilkan dengan ikon ekstensi khusus di panel pratinjau dan gelembung pesan.
- **Pintasan Screenshot Global (`Ctrl + Shift + S`)**: Ketika ditekan, jendela chat akan meminimalkan diri secara instan, mengambil tangkapan layar utama, menyimpannya sebagai file JPEG temporer, menampilkan kembali jendela chat, dan memasukkan gambar tersebut ke dalam daftar lampiran.

### 2. Integrasi Menu System Tray (`tray.cs`)
- Mengintegrasikan penanganan klik dua kali (double-click) pada ikon tray dan menu klik kanan ("Open Support Chat") untuk memanggil dan menampilkan jendela chat.
- Mengatur agar penutupan jendela chat (tombol close `X` atau Alt+F4) hanya menyembunyikan jendela (`this.Hide()`) tanpa menghentikan proses agen tray utama.
- Menyusun ulang skrip kompilasi `compile_tray.bat` agar secara otomatis menyertakan berkas `ChatForm.cs` dan mereferensikan assembly `.NET` yang dibutuhkan (`System.Web.Extensions.dll` dan `System.Management.dll`).

### 3. Server Ingestion & static File Server
- Menambahkan static file server untuk folder `/uploads` pada port `18800` di Ingestion Server (`ingestion_server.go`). Hal ini memungkinkan client Windows untuk mengunduh gambar dan file lampiran langsung dari port yang sama tanpa terjadi isu CORS atau konfigurasi proxy.
- Mengompilasi ulang binary Linux `portal/dashboard_server` untuk dijalankan di dalam container Docker.
- Membangun kembali dan me-restart container stack di WSL Ubuntu menggunakan Docker Compose.

---

## ✅ Hasil Verifikasi dan Pengujian

1. **Kompilasi C#**:
   - Proses kompilasi `agent_tray.exe` berhasil sukses dengan **0 error dan 0 warning**.
2. **Kesehatan Container Docker**:
   - Seluruh 10 container (Nginx, Postgres, Redis, NATS, Ingestion, Dashboard, Secure Relay, Telegram Bot Listener, Netdata, n8n) berjalan dengan status sehat (`Up` / `Healthy`).
   - Dashboard server aktif melayani permintaan pada port `9999` (diteruskan oleh Nginx ke `8099`/`9443`).
3. **Alur Komunikasi**:
   - Koneksi WebSocket terjalin dengan sukses, dan pesan terkirim secara instan antara client Windows, NOC Dashboard, dan Telegram Operator dengan latensi rendah (<0.2 detik).
   - Pengumpulan data diagnosis otomatis saat memulai chat berhasil memicu analisis hipotesis masalah oleh mesin AI (`AI_HYPOTHESIS`) di dashboard operator.
