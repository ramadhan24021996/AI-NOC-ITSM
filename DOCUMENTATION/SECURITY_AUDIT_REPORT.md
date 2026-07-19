# Laporan Audit Keamanan Sistem (Security Audit Report)

Laporan ini mendokumentasikan hasil audit keamanan komprehensif pada **OSI AI Incident Analysis System**, mengidentifikasi potensi celah keamanan (*vulnerabilities*), menentukan tingkat bahaya (*severity*), dan merekomendasikan langkah hardening untuk deployment produksi.

---

## 🔒 Ringkasan Temuan Audit Keamanan

### 1. Injeksi SQL (SQL Injection)
- **Lokasi**: Query pencarian chat (`/api/chat/search?query=...`) dan logging telemetri.
- **Hasil Temuan**: Seluruh interaksi database menggunakan GORM ORM parameterized query (seperti `db.Where("client_id = ? AND message ILIKE ?", client_id, "%"+query+"%")`). Hal ini meniadakan kemungkinan eksploitasi SQL Injection klasik karena input pengguna tidak digabungkan langsung secara mentah ke dalam string query SQL.
- **Tingkat Bahaya**: `Low`
- **Rekomendasi**: Pertahankan penggunaan GORM secara konsisten. Hindari penggunaan query string mentah (`db.Raw("... + input + ...")`) pada pengembangan modul kustom di masa depan.

---

### 2. Cross-Site Scripting / XSS (NOC Dashboard UI)
- **Lokasi**: Area render pesan chat dan riwayat log remote action di file `templates/index.html`.
- **Hasil Temuan**: Pesan chat yang dikirim oleh client mengandung tag HTML (misalnya `<script>alert('xss')</script>`) dapat dieksekusi oleh browser operator NOC jika data dirender langsung menggunakan property `.innerHTML` di javascript dashboard.
- **Tingkat Bahaya**: `High`
- **Rekomendasi**: Gunakan properti `.textContent` atau `.innerText` saat memperbarui balon chat di javascript dashboard. Lakukan sanitasi data input menggunakan library HTML sanitizer sebelum merendernya ke UI dashboard.

---

### 3. Cross-Site Request Forgery / CSRF
- **Lokasi**: Endpoint aksi remote `/api/remote/launch/*` dan `/api/remote/test/*`.
- **Hasil Temuan**: Jika operator NOC membuka situs jahat di tab browser lain saat sedang login ke Dashboard, situs jahat tersebut dapat mengirimkan request post remote action ke server NOC karena ketiadaan mekanisme token anti-CSRF atau CORS policy yang ketat pada API.
- **Tingkat Bahaya**: `High`
- **Rekomendasi**: Implementasikan header otentikasi `Bearer <JWT_TOKEN>` wajib untuk seluruh transaksi remote, dan jangan mengandalkan otentikasi berbasis cookie. Konfigurasikan kebijakan Nginx CORS Origin Whitelist secara ketat agar hanya menerima request dari domain tepercaya.

---

### 4. Serangan Balasan Telegram (Replay Attack on Telegram Relay)
- **Lokasi**: Secure Relay Endpoint `/relay/telegram/send` pada port `9998`.
- **Hasil Temuan**: Relay pengiriman alert Telegram rentan terhadap serangan Replay Attack jika penyerang berhasil menyadap request pengiriman alert yang ditandatangani HMAC. Penyerang dapat mengirimkan request yang sama berulang kali untuk membombardir grup Telegram operator.
- **Tingkat Bahaya**: `Medium`
- **Rekomendasi**: Implementasikan pengecekan masa berlaku timestamp (`X-Timestamp`) pada Secure Relay. Tolak seluruh request yang memiliki selisih waktu timestamp lebih besar dari 5 menit dibandingkan dengan waktu server saat ini.

---

### 5. Kebocoran Token Telegram Bot (Token Leakage)
- **Lokasi**: Environment variable server.
- **Hasil Temuan**: Arsitektur server diisolasi dengan menaruh token bot Telegram (`TELEGRAM_BOT_TOKEN`) hanya di dalam container `osi-secure-relay` dan `osi-telegram-bot`. Container Ingestion Server dan Dashboard Server tidak memegang token ini, melainkan berkomunikasi via localhost/portproxy. Hal ini membatasi risiko kebocoran token jika salah satu server utama dieksploitasi.
- **Tingkat Bahaya**: `Low`
- **Rekomendasi**: Jangan pernah mencatat (log) environment variable token ke dalam log file server. Gunakan Docker Secret Manager untuk injeksi runtime token daripada menyimpannya di file `.env` mentah.

---

### 6. Pemalsuan Tanda Tangan HMAC (HMAC Spoofing)
- **Lokasi**: Jalur komunikasi Secure Relay API.
- **Hasil Temuan**: Verifikasi tanda tangan digital HMAC SHA-256 (`X-Signature`) menggunakan kunci rahasia bersama (`HMACSecret`). Jika penyerang tidak memegang kunci rahasia ini, mereka tidak dapat membuat signature yang valid untuk mengirimkan alert palsu ke Telegram.
- **Tingkat Bahaya**: `Low`
- **Rekomendasi**: Pastikan kunci rahasia `HMACSecret` diganti secara berkala di file `.env` dan tidak menggunakan kunci bawaan default pabrik.

---

### 7. Eksekusi Remote Tanpa Hak Akses (Unauthorized Remote Execution)
- **Lokasi**: TCP Port `10000` di localhost client Windows.
- **Hasil Temuan**: Port `10000` pada PC client Windows mendengarkan koneksi TCP lokal dari service daemon. Namun, jika port ini diekspos ke jaringan luar (melalui firewall Windows yang terbuka atau konfigurasi portproxy yang salah), penyerang di jaringan LAN yang sama dapat mengirimkan perintah JSON langsung ke port `10000` dan mengeksekusi aksi di PC client tanpa otentikasi dashboard.
- **Tingkat Bahaya**: `Critical`
- **Rekomendasi**: Konfigurasikan Windows Firewall secara ketat agar port `10000` **HANYA** mendengarkan alamat loopback `127.0.0.1`. Jangan izinkan koneksi masuk dari IP eksternal LAN pada port `10000`.

---

### 8. Celah Unggahan Berkas (File Upload Vulnerability & Directory Traversal)
- **Lokasi**: File Upload API `/api/chat/upload`.
- **Hasil Temuan**: Penyerang dapat mengunggah script web shell (seperti `shell.php`) jika server tidak memvalidasi ekstensi file. Penyerang juga dapat memanipulasi nama file (seperti `../../etc/nginx/nginx.conf`) untuk menimpa file konfigurasi server melalui celah *Directory Traversal*.
- **Tingkat Bahaya**: `Critical`
- **Rekomendasi**:
  1. Bersihkan nama file menggunakan `filepath.Base` sebelum menyimpannya ke disk.
  2. Gunakan whitelist ketat untuk ekstensi file yang diizinkan (gambar, txt, log, zip, pdf, evtx, csv).
  3. Simpan file dengan nama acak/unik yang di-generate server (seperti UUID/Timestamp), jangan gunakan nama asli yang dikirim client.

---

### 9. Eskalasi Hak Akses Agen (Privilege Escalation)
- **Lokasi**: Windows Service `agent.exe` yang berjalan sebagai `LocalSystem`.
- **Hasil Temuan**: Karena agen berjalan dengan hak akses tertinggi `LocalSystem`, eksploitasi celah keamanan (seperti buffer overflow) pada parser command port `10000` dapat memberikan penyerang hak kontrol sistem penuh (*SYSTEM level shell*) pada komputer Windows client.
- **Tingkat Bahaya**: `Critical`
- **Rekomendasi**:
  1. Batasi fungsionalitas remote execution hanya pada sekumpulan fungsi whitelist kaku yang terdefinisi di code program (seperti yang telah diimplementasikan di `executeAgentCommand`).
  2. Hindari fungsi dinamis yang mengevaluasi input string mentah langsung ke shell (seperti `cmd.exe /c + input`). Gunakan parameterisasi argumen yang aman.
