# Master Verification Checklist (NOC & Agent Integration)

Dokumen ini mendefinisikan seluruh kasus uji (test cases) untuk verifikasi kesiapan produksi dari **OSI AI Incident Analysis System**.

| ID | Modul | Test Case | Expected Result | Status | Severity |
| :--- | :--- | :--- | :--- | :---: | :---: |
| **SRV-01** | Server (Go) | HTTP Telemetry Ingestion (`POST /telemetry`) | Menerima payload telemetri valid, memvalidasi skema, mengalirkan ke NATS/Redis, dan menyimpan ke PostgreSQL. | ✅ | High |
| **SRV-02** | Server (Go) | HTTP Telemetry Ingestion dengan Skema Invalid | Menolak request dengan HTTP 400 Bad Request, mencatat log error, tidak menulis ke DB. | ✅ | Medium |
| **SRV-03** | Server (Go) | API History Query (`GET /api/chat/history`) | Mengembalikan daftar pesan chat terurut berdasarkan ID untuk client tertentu. | ✅ | Medium |
| **SRV-04** | Server (Go) | API Search Query (`GET /api/chat/search`) | Mengembalikan hasil pencarian berbasis teks (ILIKES) dalam database chat history. | ✅ | Low |
| **SRV-05** | Server (Go) | API Suggested Reply (`GET /api/chat/suggest`) | AI Engine memproses riwayat & diagnosis terbaru, mengembalikan 3 saran balasan dalam format JSON. | ✅ | Medium |
| **SRV-06** | Server (Go) | static Assets Server (Port 18800 `/uploads/`) | Menyajikan berkas lampiran chat secara static tanpa terjadi CORS error dari client. | ✅ | High |
| **CLI-01** | Client Agent | Instalasi Windows Service SCM | Skrip `installer/main.go` mendaftarkan `OSI AI Agent` dengan startup `Delayed Auto`, Recovery Policy aktif. | ✅ | High |
| **CLI-02** | Client Agent | Module watchdog Heartbeat | Watchdog melacak aktivitas modul via touch timestamp. Modul crash 3x berturut-turut mentransfer modul ke status `Unhealthy` dan memicu alert. | ✅ | Critical |
| **CLI-03** | Client Agent | Watchdog Cooldown Safeguard | Menjeda restart modul selama 15 detik untuk mencegah loop restart cepat (flicker instability). | ✅ | High |
| **CLI-04** | Client Agent | Local Cache Telemetry | Saat server offline, log telemetri disimpan ke direktori cache lokal. Data ditransmisikan saat koneksi pulih. | ✅ | High |
| **TRY-01** | Tray UI | localhost TCP Polling (Port 10000) | Tray aplikasi melakukan query status `"GET_STATUS"` via TCP localhost ke agen service setiap 2 detik. | ✅ | High |
| **TRY-02** | Tray UI | Dynamic GDI+ Rendering | Menggambar ikon warna dinamis (Hijau, Kuning, Merah, Abu, Biru, Oranye) sesuai status agen. | ✅ | Medium |
| **TRY-03** | Tray UI | Double-Click & Context Menu | Membuka jendela chat kustom (`ChatForm.cs`) saat diklik ganda atau dipilih dari menu tray. | ✅ | Medium |
| **TRY-04** | Tray UI | Form Hide on Close | Menutup jendela chat (tombol close X) menyembunyikannya ke tray tanpa mematikan agen utama. | ✅ | Medium |
| **CHT-01** | Chat Form | WS Handshake & Connection | Membuka WebSocket ke `/api/chat/ws`. Menampilkan banner status `"Connected"` (Hijau) saat sukses. | ✅ | High |
| **CHT-02** | Chat Form | WS Reconnection & Fallback Polling | Jika WebSocket disconnect, status berubah ke `"Reconnecting..."` dan memicu HTTP short polling `/api/chat/poll` setiap 5s. | ✅ | High |
| **CHT-03** | Chat Form | WMI Diagnostics Auto-Collect | Klik tombol "Start Chat" mengumpulkan info hardware (CPU, RAM, Disk, SMART, Services, Events) dan mengirimkannya. | ✅ | High |
| **CHT-04** | Chat Form | Offline Message Queueing | Pesan terkirim saat offline diantrekan dengan tanda `⏳ Pending` dan dikirim otomatis ketika socket terhubung kembali. | ✅ | High |
| **CHT-05** | Chat Form | File Upload & Thumbnail Preview | Membatasi maks 5 berkas. Unggahan gambar memicu JPEG compression 75% kualitas. Berkas log/zip diunggah mentah. Pratinjau ikon sesuai tipe berkas. | ✅ | High |
| **CHT-06** | Chat Form | Clipboard Image Paste (Ctrl+V) | Mengubah gambar clipboard Windows menjadi file png temporer, mengunggah ke server, dan menampilkan pratinjau. | ✅ | Medium |
| **CHT-07** | Chat Form | Screen Capture Shortcut | Menekan `Ctrl + Shift + S` otomatis meminimalkan form, memicu snapshot layar utama, memulihkan form, dan menambahkannya ke lampiran. | ✅ | Medium |
| **CHT-08** | Chat Form | Local Search Filter | Kolom pencarian chat menyaring gelembung pesan secara lokal seketika tanpa request server. | ✅ | Low |
| **CHT-09** | Chat Form | Read Receipts Sync | Mengirim event `read_receipt` ke WebSocket saat user membaca pesan operator di layar chat aktif. | ✅ | Medium |
| **CHT-10** | Chat Form | Typing Status Transmission | Mengirim event `typing` saat user mengetik. Menerima status typing operator dan memunculkan label "Operator is typing...". | ✅ | Medium |
| **DSH-01** | NOC Dashboard | WS Gateway `/ws/chat` | Broadcaster status chat operator. Menerima input chat operator, menyimpannya di DB, dan mendistribusikan pesan ke target client. | ✅ | High |
| **DSH-02** | NOC Dashboard | Live Status Filters | Triage filter berdasarkan site, keparahan (severity), status (All, Open, Waiting Operator, Active, Closed). | ✅ | Medium |
| **DSH-03** | NOC Dashboard | Device Context Sidebar | Menampilkan riwayat (30 chats terakhir, 10 screenshot, 5 insiden, 3 remote) dari client aktif yang sedang diklik. | ✅ | Medium |
| **BOT-01** | Telegram Bot | Swipe-Reply Message Parsing | Menguraikan relasi reply bot. Memetakan operator reply kembali ke client ID via tabel `telegram_chat_mappings` dan meneruskannya ke Redis. | ✅ | High |
| **BOT-02** | Telegram Bot | Admin Authorization Guard | Membatasi operator reply hanya untuk pengguna yang terdaftar di konfigurasi `AUTHORIZED_ADMINS`. | ✅ | High |
| **DB-01** | Database | Partitioning telemetry_logs | Memvalidasi pembuatan tabel partisi bulanan (`telemetry_logs_y2026mXX`) berjalan tanpa hambatan. | ✅ | High |
| **DB-02** | Database | Indexing & Foreign Keys | Menjamin indeks kunci asing (foreign key) pada tabel `chat_messages` dan `telegram_chat_mappings` dibuat untuk performa query cepat. | ✅ | High |
