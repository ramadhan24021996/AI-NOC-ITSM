# API Validation & Security Compliance Report

Laporan ini mendokumentasikan spesifikasi pengujian API, parameter batas input, penanganan kesalahan (*error handling*), perilaku batas kecepatan (*rate limiting*), dan validasi skema untuk seluruh endpoint operasional **OSI AI Incident Analysis System**.

---

## 🛠️ Matriks Audit Endpoint API

### 1. Endpoint `/telemetry` (Ingestion Pipeline)
- **Metode**: `POST`
- **Fungsi**: Menerima data metrik telemetri hardware dari agen Windows.
- **Audit Pengujian**:
  - **Valid Input**: JSON payload lengkap memuat `"type": "telemetry"`, `"agent_id"`, `"pc_name"`, `"ip_address"`, serta data metrik CPU/RAM yang valid. Server mengembalikan HTTP 200 OK.
  - **Invalid Input**: Pengiriman string kosong, JSON terpotong, atau kolom tipe metrik yang tidak valid. Server menolak dengan HTTP 400 Bad Request.
  - **Boundary Test**: Nilai persentase beban CPU bernilai `-5%` atau `150%`. Server menormalisasi data batas menjadi `0%` atau `100%` melalui `normalization.go` tanpa menghentikan pemrosesan.
  - **Timeout Behavior**: Jika jaringan database PostgreSQL lambat, payload ditahan di antrean broker Redis/NATS. Ingestion API merespons client dalam < 50ms tanpa menunggu penulisan database fisik selesai (Asynchronous Non-blocking I/O).
  - **Error Handling**: Jika PostgreSQL mati total, Ingestion tetap membalas HTTP 200 dan mengalirkan log ke Redis buffer list/DLQ lokal.
  - **Rate Limit Behavior**: Batas rate-limit diaktifkan di Nginx: maks 120 request per menit per IP client. Jika dilanggar, server membalas HTTP 429 Too Many Requests.

---

### 2. Endpoint `/api/chat/ws` (WebSocket Gateway Client)
- **Metode**: `GET` (Protokol Upgrade ke WS)
- **Fungsi**: Gerbang socket komunikasi real-time dua arah agen client.
- **Audit Pengujian**:
  - **Valid Input**: Request parameter query `client_id` (UUID valid) dan `pc_name` valid. Handshake sukses, mengembalikan HTTP 101 Switching Protocols.
  - **Invalid Input**: Melakukan handshake tanpa menyertakan `client_id`. Server membalas HTTP 400 Bad Request dan langsung menutup koneksi.
  - **Boundary Test**: Membuka 20 koneksi WebSocket simultan dari client_id yang sama. Ingestion Server mendeteksi duplikasi, memutuskan koneksi socket lama, dan mempertahankan koneksi socket yang paling baru (Single Connection Session Enforcement).
  - **Timeout Behavior**: Ping-Pong interval diatur setiap 10 detik. Jika client tidak merespons ping dalam 30 detik, server memutus koneksi socket secara sepihak untuk menghemat resource memori.
  - **Error Handling**: Jika parser JSON di websocket menerima data korup, server mengabaikan event tersebut tanpa menutup koneksi utama.
  - **Rate Limit Behavior**: Maksimum 50 event pesan per menit per WebSocket session. Jika terlampaui, event diabaikan secara diam-diam dan status peringatan dikirim ke client.

---

### 3. Endpoint `/api/chat/upload` (File Upload & Compression)
- **Metode**: `POST` (Multipart Form Data)
- **Fungsi**: Mengunggah file screenshot chat dan file log sistem.
- **Audit Pengujian**:
  - **Valid Input**: Mengirim parameter file dengan berkas `.png`, `.jpg`, `.txt`, atau `.zip` berukuran < 15MB. Server membalas HTTP 200 dengan JSON memuat `attachment_path` relatif.
  - **Invalid Input**: Mengunggah berkas berekstensi berbahaya (seperti `.exe`, `.bat`, `.dll`, `.sh`, `.php`). Server langsung memblokir dan membalas HTTP 400 Bad Request.
  - **Boundary Test**: Mengunggah file berukuran tepat `15.01MB` (melebihi limit 15MB). Nginx/Go memblokir request awal dan membalas HTTP 413 Payload Too Large.
  - **Timeout Behavior**: Unggahan lambat pada koneksi seluler dibatasi timeout selama 30 detik di server. Jika waktu habis sebelum file selesai diunggah, server menghentikan koneksi.
  - **Error Handling**: Gagal menulis file ke direktori `/uploads/chat/` (misal: disk penuh) menghasilkan respons HTTP 500 Internal Server Error dengan log kesalahan server yang lengkap.
  - **Rate Limit Behavior**: Maksimum 10 unggahan berkas per menit per IP. Pelanggaran memicu status HTTP 429.

---

### 4. Endpoint `/api/chat/history` (Chat History Retrievals)
- **Metode**: `GET`
- **Fungsi**: Memuat riwayat perbincangan lama antara client dan operator.
- **Audit Pengujian**:
  - **Valid Input**: Query parameter `client_id` memuat UUID yang terdaftar di database. Server membalas HTTP 200 dengan array JSON pesan terurut.
  - **Invalid Input**: Query tanpa `client_id` atau UUID dengan karakter ilegal (SQL injection payload). SQL injection dicegah oleh parameterized GORM query, server membalas dengan array kosong.
  - **Boundary Test**: Meminta riwayat dari client yang memiliki 5.000 riwayat chat. Server membatasi pemuatan maksimum 100 pesan terakhir (pagination default) untuk meminimalkan beban memori HTTP.
  - **Timeout Behavior**: Query database dibatasi timeout maksimum 5 detik. Jika database terkunci (lock contention), server membalas HTTP 504 Gateway Timeout.
  - **Error Handling**: Sesi chat tidak ditemukan mengembalikan HTTP 200 dengan array JSON kosong `[]` (bukan melempar HTTP 500).
  - **Rate Limit Behavior**: Maksimum 60 query per menit per IP client.

---

### 5. Endpoint `/api/chat/suggest` (AI Suggested Replies)
- **Metode**: `GET`
- **Fungsi**: Memanggil analisis AI untuk menghasilkan saran jawaban operator di dashboard.
- **Audit Pengujian**:
  - **Valid Input**: Query parameter `client_id` berisi UUID valid dengan minimal 1 pesan terkirim. Server membalas HTTP 200 berisi 3 saran kalimat.
  - **Invalid Input**: Query tanpa parameter `client_id` mengembalikan HTTP 400 Bad Request.
  - **Boundary Test**: Dipanggil berulang-ulang dalam jeda waktu 1 detik. Server mengambil hasil cache diagnosis terakhir di Redis tanpa memicu evaluasi ulang AI untuk menghemat utilisasi CPU.
  - **Timeout Behavior**: Pemanggilan API AI supervisor dibatasi timeout 3 detik. Jika engine tidak merespons, server membalas dengan saran default NOC.
  - **Error Handling**: Jika server AI offline, sistem mencatat log error dan membalas dengan saran penanganan spooler standar.
  - **Rate Limit Behavior**: Maksimum 30 request per menit.

---

### 6. Endpoint Group `/api/remote/*` & `/api/orchestrator/*`
- **Metode**: `POST` / `GET`
- **Fungsi**: Pemicu remote command execution ke port kontrol lokal `10000` agen client.
- **Audit Pengujian**:
  - **Valid Input**: Request parameter `client_id` valid, otentikasi JWT operator valid, dan perintah valid (`CLEAR_SPOOLER`, `SHOW_ROUTE`). Server membalas dengan status eksekusi.
  - **Invalid Input**: Request tanpa header otentikasi Bearer Token JWT yang valid, atau menyertakan token yang kedaluwarsa. Server membalas HTTP 401 Unauthorized atau HTTP 403 Forbidden.
  - **Boundary Test**: Mengirimkan perintah routing dengan parameter IP gateway kosong. Agen Windows mendeteksi error argumen, membatalkan eksekusi, dan membalas dengan pesan error format parameter.
  - **Timeout Behavior**: Koneksi TCP ke port `10000` client dibatasi timeout 10 detik. Jika PC client mati atau terputus jaringan sebelum perintah selesai dieksekusi, API membalas HTTP 504 Gateway Timeout.
  - **Error Handling**: Perintah routing yang memerlukan hak administrator tinggi dijalankan pada akun non-admin mengembalikan string error stderr dari OS Windows (`Access Denied`) dan dibalas dengan respons sukses berisi status gagal.
  - **Rate Limit Behavior**: Maksimum 10 perintah remote per operator per menit untuk menghindari penyalahgunaan kontrol jaringan.

---

## 📡 Audit Saluran WebSocket (WebSocket Channels)

### 1. Saluran Chat Client (`/api/chat/ws`)
- **Tipe Event yang Dikirim Client**:
  - `init_context`: Mengirimkan spesifikasi hardware awal (format JSON).
  - `diagnostic`: Mengirimkan payload diagnosis lengkap (WMI logs, Event logs).
  - `message`: Mengirimkan teks chat dan attachment path.
  - `typing`: Mengirimkan boolean status sedang mengetik (`true`/`false`).
  - `read_receipt`: Mengirimkan pesan ID terakhir yang telah dibaca user di layar.
- **Tipe Event yang Diterima Client**:
  - `message`: Berisi data chat balasan dari operator NOC atau grup Telegram.
  - `typing`: Status mengetik operator.
  - `operator_status`: Mengirim status kehadiran operator (`ONLINE` / `OFFLINE`).

### 2. Saluran Dashboard Operator (`/ws/chat`)
- **Fungsi**: Menghubungkan visualisasi chat feed di dashboard.
- **Pesan Broadcast**:
  - Menyebarkan event chat baru, update status centang biru dibaca (`read_receipt`), dan status mengetik client ke seluruh layar browser operator aktif melalui Redis Pub/Sub `chat_channel`.
