PROMPT UNTUK ANTIGRAVITY AI
ROLE

Anda adalah Senior Desktop Application Engineer, Senior Full Stack Developer, Backend Engineer, UI/UX Engineer, Telegram Bot Engineer, AI Engineer, DevOps Engineer, dan System Architect.

Lakukan refactoring menyeluruh pada sistem OSI AI Helpdesk tanpa menghilangkan fitur yang sudah ada. Semua fitur lama harus tetap berjalan, namun mekanisme notifikasi incident diubah menjadi berbasis Chat Center.

TUJUAN

Saat Agent mendeteksi gangguan pada komputer user:

JANGAN LAGI MENAMPILKAN POPUP "SISTEM OSI MENDETEKSI GANGGUAN".

Popup tersebut harus dihapus sepenuhnya.

Sebagai gantinya:

Semua informasi incident hanya muncul di dalam OSI AI SUPPORT CHAT.

Panel chat menjadi pusat komunikasi antara:

Desktop User
AI Assistant
NOC Engineer
Telegram Bot
Dashboard Admin

Semua terhubung secara realtime.

ALUR SISTEM BARU
STEP 1 - DETEKSI INCIDENT

Desktop Agent terus melakukan monitoring terhadap:

Windows Event Viewer
Application Crash
Service Stop
Network Down
Printer Error
CPU High
RAM High
Disk Full
Database Error
Windows Error
Internet Disconnect
dan seluruh monitoring yang sudah ada.

Begitu incident terdeteksi:

Jangan tampilkan Popup.
Jangan membuka Window baru.
Langsung kirim Incident ke OSI AI SUPPORT CHAT.

Jika Chat sudah terbuka, cukup tambahkan pesan baru.

STEP 2 - AI MENGIRIM PESAN

Di dalam chat otomatis muncul pesan:

🤖 OSI AI

Saya mendeteksi gangguan pada komputer Anda.

Sedang melakukan analisa...

Mohon tunggu beberapa saat.

Setelah proses analisa selesai:

🧠 Analisa Selesai

Network Connectivity Lost

Komputer kehilangan koneksi menuju server sehingga aplikasi tidak dapat berjalan normal.

Kemudian:

🔧 Rekomendasi

• Periksa kabel LAN
• Restart Network Adapter
• Pastikan koneksi internet aktif
• Jalankan Diagnosis Network
STEP 3 - INCIDENT CARD

Popup lama diganti menjadi Incident Card di dalam Chat.

Contoh:

🚨 INCIDENT TERDETEKSI

Incident
Network Connectivity Lost

Severity
Medium

Analisa AI
Komputer kehilangan koneksi menuju server.

Rekomendasi

• Restart Network Adapter

• Periksa LAN

• Hubungi NOC

Button:

✔ Saya Sudah Memperbaiki

💬 Hubungi NOC

Jika User memilih:

Hubungi NOC

Maka otomatis:

Membuat Ticket
Membuat Room Chat
Mengirim ke Dashboard
Mengirim ke Telegram
STEP 4 - DASHBOARD

Dashboard langsung berubah realtime.

Status Ticket

Waiting NOC

Jumlah Incident bertambah.

Status User berubah.

Tanpa refresh browser.

Gunakan:

WebSocket
atau
Socket.IO
TELEGRAM

Telegram BUKAN hanya notifikasi, tetapi menjadi media komunikasi antara User dan NOC.

Namun notifikasi awal dibuat sederhana.

Saat Incident Terjadi

Bot Telegram TIDAK PERLU mengirim:

Ticket ID
Hostname
Nama PC
Username Windows
IP Address
Departemen
MAC Address
CPU
RAM
Event Log
Informasi teknis lainnya

Informasi tersebut cukup disimpan di database dan ditampilkan di Dashboard.

Telegram Hanya Mengirim
🚨 INCIDENT BARU TERDETEKSI

📸 Screenshot Desktop User
(otomatis terlampir)

🧠 Analisa Masalah

Network Connectivity Lost

Komputer kehilangan koneksi ke server sehingga aplikasi tidak dapat berkomunikasi dengan sistem pusat.

🔧 Cara Menangani

• Pastikan kabel LAN terpasang.
• Periksa koneksi WiFi.
• Restart Network Adapter.
• Jalankan Diagnosis Network.
• Hubungi NOC apabila masih terjadi.

────────────────────────

Status

Waiting NOC

Lampiran:

📷 Screenshot Desktop User
TELEGRAM BUTTON

Telegram hanya memiliki tombol:

💬 Chat User

atau

💬 Mulai Chat

Saat tombol ditekan:

Telegram langsung membuka Room Chat dengan User.

SCREENSHOT

Saat Incident terjadi:

Desktop Agent otomatis:

Capture Screen

↓

Upload ke Server

↓

Kirim ke Telegram

↓

Kirim ke Dashboard

↓

Simpan ke Database

Screenshot menjadi lampiran pertama.

Tidak perlu konfirmasi User.

LIVE CHAT

Setelah Engineer menekan:

💬 Chat User

Telegram berubah menjadi media chatting realtime.

Alur:

Desktop User

↓

Server

↓

Telegram Bot

↓

NOC

↓

Telegram

↓

Server

↓

Desktop Chat

Semua realtime.

CONTOH

User

Printer saya tidak bisa digunakan.

Telegram

Rendy

Printer saya tidak bisa digunakan.

Engineer membalas

Silakan restart Print Spooler terlebih dahulu.

Balasan langsung muncul di Desktop Chat.

Tanpa Refresh.
CHAT UI

Desain seperti WhatsApp.

User Bubble

Sebelah kanan

Hijau

NOC Bubble

Sebelah kiri

Abu

AI Bubble

Biru

Bot Bubble

Ungu

Timestamp

19:31

Read Receipt

✓ Sent

✓✓ Delivered

✓✓ Read

Typing Indicator

NOC sedang mengetik...

Auto Scroll.

HEADER CHAT
OSI AI SUPPORT CHAT

● Connected

Status

Waiting NOC

Engineer

Belum Ditugaskan
SIDEBAR CHAT

Riwayat:

Hari Ini
Kemarin
Minggu Ini
Bulan Ini

Search Chat.

FILE ATTACHMENT

Desktop dapat mengirim:

Screenshot
JPG
PNG
PDF
TXT
CSV
ZIP
LOG

Drag & Drop.

Telegram menerima file.

Dashboard menerima file.

TOMBOL SCREENSHOT

Tambahkan tombol:

📷 Screenshot

Sekali klik.

Desktop otomatis capture.

Langsung terkirim ke Chat.

DATABASE

Buat tabel:

chat_rooms
id

ticket_id

user_pc

hostname

assigned_engineer

status

created_at
chat_messages
id

ticket_id

sender

sender_type

message

attachment

status

created_at

read_at
STATUS CHAT

Support:

Online

Offline

Delivered

Read

Typing...
BACKEND

Pisahkan service menjadi:

Incident Service

AI Analysis Service

Chat Service

Notification Service

Telegram Service

Dashboard Service

Desktop Gateway

WebSocket Service

File Upload Service

Monitoring Service

Jangan menggunakan satu file besar.

Gunakan arsitektur modular.
YANG TIDAK BOLEH HILANG

Pastikan seluruh fitur lama tetap berjalan:

Auto Monitoring
Auto Detect Incident
AI Analysis
Auto Ticket
Dashboard
Telegram Integration
History Incident
Event Log
Monitoring Service
Auto Recovery
Login
Teknisi Online/Offline
Database
Notifikasi Realtime

Jangan menghapus satu pun fitur tersebut.

HAPUS TOTAL POPUP

Hapus seluruh kode yang berkaitan dengan:

SISTEM OSI MENDETEKSI GANGGUAN

Popup tersebut tidak boleh muncul lagi.

Seluruh logic popup dipindahkan menjadi Incident Card di dalam OSI AI SUPPORT CHAT.

HASIL AKHIR YANG DIHARAPKAN

Setelah implementasi selesai:

Popup "SISTEM OSI MENDETEKSI GANGGUAN" tidak muncul lagi.
Semua incident muncul sebagai Incident Card di OSI AI SUPPORT CHAT.
AI otomatis melakukan analisa dan memberikan rekomendasi.
Dashboard menerima incident secara realtime tanpa refresh.
Telegram hanya menerima Screenshot + Analisa Masalah + Cara Menangani + Tombol Chat User.
Setelah tombol Chat User ditekan, Telegram menjadi media chat dua arah realtime antara User dan NOC seperti WhatsApp.
Semua percakapan tersimpan di database.
Screenshot, file, log, dan attachment dapat dikirim dari Desktop, Dashboard, maupun Telegram.
Seluruh sistem menggunakan WebSocket/Socket.IO agar sinkron secara realtime.
Arsitektur dibuat modular, scalable, mudah dipelihara, dan siap digunakan untuk ratusan hingga ribuan client secara bersamaan tanpa mengubah fitur-fitur yang sudah ada.s