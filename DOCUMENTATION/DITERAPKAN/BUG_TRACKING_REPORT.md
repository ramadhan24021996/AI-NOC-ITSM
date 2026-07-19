# Laporan Pelacakan & Analisis Bug Sistem (Bug Tracking Report)

Laporan ini mendokumentasikan analisis bug realistis pada lingkungan terdistribusi **OSI AI Incident Analysis System**. Laporan ini memetakan identifikasi bug, modul terdampak, hipotesis penyebab utama (*root cause hypothesis*), tingkat keparahan (*severity*), rekomendasi perbaikan (*fix recommendation*), dan analisis risiko regresi (*regression risk*) pasca perbaikan.

---

## 🐜 Bug-01: WebSocket Disconnection & Reconnection Failure

- **BUG-ID**: `BUG-01`
- **Module Affected**: Client Chat Form (`ChatForm.cs`) & Server Ingestion WebSocket Gateway (`/api/chat/ws`)
- **Description**: 
  Ketika PC client Windows kembali aktif dari status sleep/hibernation, atau ketika koneksi jaringan mengalami gangguan sesaat (micro-disconnection), jendela chat client terjebak dalam status `Connecting...` (Oranye) atau `Reconnecting...` (Kuning) secara permanen. Pengguna tidak dapat mengirim atau menerima pesan baru tanpa harus menutup paksa dan membuka ulang jendela chat (restart runtime UI).
- **Root Cause Hypothesis**:
  1. **TCP Half-Open Connections**: Ketika client kehilangan koneksi tanpa mengirimkan sinyal penutupan TCP (misalnya kabel LAN dicabut), server Ingestion menganggap koneksi WebSocket masih aktif (status `ESTABLISHED` di OS). Client yang terhubung kembali menggunakan socket baru dengan UUID yang sama ditolak oleh server karena server masih menahan socket lama.
  2. **Reconnection Loop Resource Lock**: Pada kode C# `ChatForm.cs`, event handler `OnClose` WebSocket memicu fungsi inisiasi ulang koneksi secara synchronous langsung di thread UI, menyebabkan window membeku (*freeze*) dan gagal merestart handshake WebSocket.
- **Severity**: `High`
- **Fix Recommendation**:
  1. **Ping-Pong Keepalive**: Aktifkan detak jantung ping-pong tingkat aplikasi (di level WebSocket payload) setiap 10 detik. Jika server tidak menerima pong dalam 20 detik, server wajib menganggap socket terputus dan membebaskan resource.
  2. **Single Connection Session Enforcement**: Di sisi Ingestion server, jika mendeteksi koneksi WebSocket masuk baru dengan UUID client yang sama dengan yang sudah terdaftar aktif, server harus menutup koneksi socket lama secara eksplisit sebelum menyetujui koneksi baru.
  3. **Asynchronous Exponential Backoff**: Implementasikan mekanisme reconnection asinkron menggunakan thread terpisah (Task background) dengan jeda waktu yang terus bertambah secara eksponensial (misalnya: 3s ➔ 6s ➔ 12s ➔ 30s ➔ 60s) untuk menghindari pembebanan server saat terjadi reconnection massal.
- **Regression Risk**: 
  Thundering Herd Problem: Jika ribuan client mengalami pemutusan jaringan massal secara simultan (misalnya gangguan router core), proses reconnection serentak tanpa jitter waktu dapat menyebabkan lonjakan beban CPU dan kegagalan handshake HTTP pada Ingestion server. Jitter acak (jeda acak ±1-2 detik) wajib ditambahkan pada interval backoff.

---

## 🐜 Bug-02: Memory Leak pada Aplikasi System Tray

- **BUG-ID**: `BUG-02`
- **Module Affected**: Windows System Tray App (`agent_tray.exe`)
- **Description**:
  Setelah berjalan terus-menerus selama lebih dari 72 jam di komputer client, konsumsi memori RAM dari aplikasi `agent_tray.exe` meningkat secara linear dari semula hanya **12 MB** pada saat boot awal menjadi **180 MB - 350 MB**. Kinerja sistem operasi Windows terganggu karena kebocoran resource handle memori grafis.
- **Root Cause Hypothesis**:
  1. **GDI+ Handle Leak**: Aplikasi tray melakukan request polling status `"GET_STATUS"` via TCP localhost ke service agen setiap 2 detik. Setiap menerima respons status, kode tray menggambar ulang ikon status warna dinamis (Hijau, Kuning, Merah) secara manual di memory bitmap menggunakan pustaka `System.Drawing.Graphics` dan `System.Drawing.Bitmap`.
  2. **Missing Dispose Calls**: Objek grafis `Bitmap`, `Icon`, dan `Graphics` di-instantiate di dalam loop polling tanpa menggunakan blok `using` statement atau tanpa pemanggilan metode `.Dispose()` secara manual. Hal ini menyebabkan runtime .NET Framework tidak dapat langsung membebaskan handle grafis Windows GDI+ ke sistem operasi, menghasilkan memory leak handle.
- **Severity**: `Medium`
- **Fix Recommendation**:
  1. Bungkus seluruh kode pembuatan visual grafis dengan blok `using` untuk menjamin pembebanan resource handle secara otomatis ketika keluar dari scope:
     ```csharp
     using (Bitmap bmp = new Bitmap(16, 16))
     using (Graphics g = Graphics.FromImage(bmp))
     {
         // Proses menggambar ikon status
         IntPtr hIcon = bmp.GetHicon();
         using (Icon tempIcon = Icon.FromHandle(hIcon))
         {
             this.notifyIcon.Icon = (Icon)tempIcon.Clone();
         }
         DestroyIcon(hIcon); // Bebaskan handle grafis Windows API
     }
     ```
  2. Panggil fungsi eksternal Windows API `DestroyIcon` menggunakan P/Invoke untuk membebaskan memory handle yang dialokasikan oleh `.GetHicon()`.
- **Regression Risk**:
  Sangat rendah. Perbaikan ini murni menangani dealokasi resource handle memori grafis lokal Windows dan tidak mengubah logika bisnis atau fungsionalitas utama komunikasi jaringan.

---

## 🐜 Bug-03: Race Condition Watchdog Supervisor Internal

- **BUG-ID**: `BUG-03`
- **Module Affected**: Go Agent Core Service Watchdog (`agent.exe`)
- **Description**:
  Watchdog supervisor mendeteksi modul runtime internal (misalnya `Telemetry Collector` atau `Heartbeat`) berstatus mati secara acak (false positive) dan memicu pemulihan restart modul. Hal ini menyebabkan terjadinya flicker status pada dashboard NOC dan pengiriman alert peringatan palsu ke Telegram bot secara berkala.
- **Root Cause Hypothesis**:
  Watchdog berjalan di goroutine terpisah yang berputar setiap 10 detik untuk mengecek status seluruh modul di dalam map `modules`. Sementara itu, modul-modul berjalan di goroutine-nya masing-masing dan secara berkala memperbarui timestamp statusnya melalui pemanggilan method `Touch()`. Terjadi persaingan akses data (Race Condition) pada penulisan dan pembacaan map `modules` dan struct status di memori tanpa adanya sinkronisasi (locking mechanism).
- **Severity**: `High`
- **Fix Recommendation**:
  1. Modifikasi struktur data pelacakan modul dengan mengimplementasikan penguncian thread-safe menggunakan `sync.RWMutex`:
     ```go
     type ModuleStatus struct {
         mu          sync.RWMutex
         IsRunning   bool
         LastTouch   time.Time
     }

     func (m *ModuleStatus) Touch() {
         m.mu.Lock()
         defer m.mu.Unlock()
         m.LastTouch = time.Now()
         m.IsRunning = true
     }

     func (m *ModuleStatus) CheckHealth() bool {
         m.mu.RLock()
         defer m.mu.RUnlock()
         // logika pemeriksaan status...
         return m.IsRunning && time.Since(m.LastTouch) < 30*time.Second
     }
     ```
  2. Jalankan perintah kompilasi go dengan opsi deteksi race `go build -race` untuk memverifikasi kepatuhan thread-safety sebelum distribusi biner.
- **Regression Risk**:
  Deadlock Risk: Implementasi locking yang tidak terstruktur dengan baik (misalnya nested locking di mana modul mencoba mengunci mutex milik watchdog saat watchdog sedang mengunci mutex milik modul) dapat menyebabkan deadlock total layanan agen. Pastikan scope locking sekecil mungkin dan tidak ada lock bertumpuk.

---

## 🐜 Bug-04: Redis Message Duplication pada WebSocket Client

- **BUG-ID**: `BUG-04`
- **Module Affected**: Go Ingestion Server (Broker Pub/Sub Connection Pool)
- **Description**:
  Pesan chat balasan dari operator NOC atau grup Telegram operator yang dikirimkan ke client Windows terkadang muncul terduplikasi sebanyak 2 hingga 3 kali di jendela chat pengguna, meskipun operator hanya mengetik satu pesan.
- **Root Cause Hypothesis**:
  Ketika koneksi WebSocket client terputus dan terhubung kembali dengan cepat (status reconnect), Ingestion server mendaftarkan Client UUID tersebut ke saluran langganan Redis `chat_channel` (Redis Pub/Sub Subscription) tanpa membatalkan langganan (unsubscribe) koneksi lama yang terputus. Hal ini mengakibatkan Ingestion server menampung beberapa objek subscriber Redis untuk Client UUID yang sama. Ketika Redis menerima publikasi pesan dari broker, ia mendistribusikan pesan ke semua objek subscriber aktif, menyebabkan server mengirim pesan terduplikasi ke WebSocket client.
- **Severity**: `High`
- **Fix Recommendation**:
  1. **Singleton Redis Connection**: Ubah arsitektur Pub/Sub di Ingestion Server. Jangan membuat satu Redis subscription per koneksi WebSocket client. Sebaliknya, gunakan satu koneksi Redis subscriber global untuk seluruh server.
  2. **Internal Dispatcher**: Ketika pesan diterima dari saluran Redis global `chat_channel`, uraikan pesan tersebut, baca target Client UUID, lalu teruskan ke koneksi WebSocket client yang aktif yang tersimpan di dalam thread-safe map internal server (misalnya `sync.Map` berisi pointer koneksi WebSocket).
- **Regression Risk**:
  Jika dispatcher internal server memicu error saat memproses payload, maka seluruh penyebaran pesan ke semua WebSocket client yang terhubung di instance server tersebut dapat terhenti. Perlu penanganan error (*panic recovery*) yang kokoh di dalam loop dispatcher utama.

---

## 🐜 Bug-05: Upload Corruption Edge Case pada Koneksi Lambat

- **BUG-ID**: `BUG-05`
- **Module Affected**: File Ingestion Gateway `/api/chat/upload` (Go Ingestion Server)
- **Description**:
  Berkas gambar screenshot (`Ctrl+Shift+S`) atau berkas log zip yang diunggah oleh client Windows yang berada di bawah koneksi seluler lambat (jaringan 3G/Edge) terkadang tersimpan rusak di server. Gambar tampak abu-abu setengah bagian (grey block) dan berkas zip tidak dapat diekstrak karena error checksum CRC.
- **Root Cause Hypothesis**:
  1. **Unchecked Stream Copy**: Ingestion server memproses unggahan file menggunakan metode `io.Copy(destinationFile, multipartFileStream)`. Jika koneksi jaringan client terputus di tengah jalan sebelum seluruh byte terkirim, `io.Copy` akan berhenti menulis tanpa membandingkan jumlah byte yang berhasil ditulis dengan header HTTP `Content-Length`.
  2. **Premature JPEG Compression**: Untuk gambar, server langsung memicu kompresi JPEG 75% sesegera mungkin pada file yang belum selesai diunggah seutuhnya di memori stream, menghasilkan file JPEG korup yang disimpan ke disk.
- **Severity**: `Medium`
- **Fix Recommendation**:
  1. Verifikasi kecocokan byte hasil tulis dengan byte asli yang tertera di form metadata:
     ```go
     bytesWritten, err := io.Copy(tempFile, fileStream)
     if err != nil {
         // Hapus file parsial
         os.Remove(tempFilePath)
         return fmt.Errorf("upload stream interrupted: %w", err)
     }
     if bytesWritten != fileHeader.Size {
         os.Remove(tempFilePath)
         return fmt.Errorf("file size mismatch: expected %d bytes, got %d bytes", fileHeader.Size, bytesWritten)
     }
     ```
  2. Pastikan file tersimpan utuh di direktori temporer terlebih dahulu sebelum melakukan optimasi kompresi gambar JPEG.
- **Regression Risk**:
  Menyimpan file ke direktori temporer terlebih dahulu meningkatkan kebutuhan ruang penyimpanan (disk I/O) server. Sistem harus dilengkapi dengan skrip cron/worker otomatis untuk membersihkan file temporer sampah yang gagal diunggah setelah 1 jam.

---

## 🐜 Bug-06: Remote Command Timeout Hang

- **BUG-ID**: `BUG-06`
- **Module Affected**: Ingestion Server Downlink Control Layer & Agent TCP Listener Port `10000`
- **Description**:
  Ketika operator NOC memicu aksi remote (seperti `CLEAR_SPOOLER`) ke komputer client yang status jaringannya tiba-tiba mati (misalnya kabel LAN dilepas) tepat setelah tombol ditekan, Dashboard NOC dan Ingestion server menjadi hang/membeku selama 15-20 menit. Selama waktu beku ini, operator lain tidak dapat memicu perintah remote ke client mana pun.
- **Root Cause Hypothesis**:
  1. **Missing Socket Timeouts**: Koneksi TCP downlink dari Ingestion server ke port `10000` client didirikan menggunakan `net.Dial("tcp", client_ip)`. Koneksi ini tidak mengkonfigurasi deadline waktu baca/tulis.
  2. **Thread Blocking**: Ketika client target mati secara tidak wajar, soket di Ingestion server tertahan dalam status `ESTABLISHED` (TCP half-open socket). Server menunggu respons stdout/stderr dari agen selamanya di goroutine utama, memicu starvation pada resource connection pool Go net library.
- **Severity**: `High`
- **Fix Recommendation**:
  1. Terapkan batas waktu koneksi, pembacaan, dan penulisan eksplisit pada soket TCP menggunakan `SetDeadline` di sisi Go server:
     ```go
     conn, err := net.DialTimeout("tcp", net.JoinHostPort(clientIP, "10000"), 5*time.Second)
     if err != nil {
         return fmt.Errorf("failed to reach agent: %w", err)
     }
     defer conn.Close()
     
     // Set deadline baca dan tulis maksimum 15 detik
     conn.SetDeadline(time.Now().Add(15 * time.Second))
     ```
  2. Jalankan perintah remote di dalam goroutine terisolasi dengan mekanisme channel select timeout agar tidak memblokir alur utama server.
- **Regression Risk**:
  Perintah remote yang membutuhkan durasi eksekusi lama (misalnya pemindaian direktori disk besar atau download updater package) akan terputus paksa (timeout error) jika deadline diatur terlalu ketat. Oleh karena itu, perintah berdurasi lama harus diubah menjadi asinkron (server mengirim perintah ➔ client membalas `ACK` ➔ client menjalankan tugas background ➔ client mengirim respons hasil tugas via HTTP POST /telemetry terpisah).
