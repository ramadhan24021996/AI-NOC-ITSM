Menurut saya, ini adalah fitur yang sangat layak ditambahkan dan akan membuat dashboard Anda terasa seperti NinjaOne, Atera, ConnectWise Automate, atau ManageEngine Endpoint Central.

Konsep UI

Saya menyarankan menambahkan ikon ⚙ (Settings) di pojok kanan atas panel Remote Access Tools, bukan di setiap tombol.

Contohnya:

┌──────────────────────────────────────────────────────────────────────────────┐
│  🖥 Remote Access Tools                                    ⚙ Remote Settings │
├──────────────────────────────────────────────────────────────────────────────┤
│ Device : PC-MKT-NUC                                       Target :10.20.0.49 │
│                                                                              │
│ RustDesk │ VNC │ AnyDesk │ Wake On LAN │ Ping │ Restart │ CMD │ PowerShell │
│                                                                              │
└──────────────────────────────────────────────────────────────────────────────┘

Saat klik ⚙ Remote Settings, muncul modal konfigurasi.

Prompt Production-Grade (Detail)

Berikut prompt yang dapat langsung digunakan untuk AI coding.

NOC IT AI Dashboard — Remote Access Settings Manager (Production Enterprise)
Objective

Implementasikan Remote Access Settings Manager pada panel Remote Access Tools dengan menambahkan ikon Settings (⚙) di pojok kanan atas panel.

Fitur ini menjadi pusat konfigurasi seluruh aplikasi remote dan routing yang digunakan oleh dashboard.

Administrator cukup melakukan konfigurasi sekali, setelah itu semua koneksi dilakukan otomatis tanpa memasukkan ID atau password lagi.

1. UI

Tambahkan tombol

⚙

di kanan atas card

Remote Access Tools

Menggunakan icon Heroicons / FontAwesome.

Tooltip:

Remote Access Settings

Klik icon

↓

Modal muncul.

2. Remote Settings Modal

Buat modal enterprise.

Tab:

General

AnyDesk

RustDesk

VNC

Site Route

Security

Test Connection
3. General

Isi:

Default Remote Tool

( ) RustDesk

( ) AnyDesk

( ) VNC

Auto Launch Remote

☑ Enable

Auto Connect

☑ Enable

Remember Last Device

☑ Enable

Connection Timeout

30 Seconds

Retry Count

3
4. AnyDesk Settings

Form:

Executable Path

C:\Program Files (x86)\AnyDesk\AnyDesk.exe

Browse...

Auto Detect

Default Password

********

Show

Hide

Remember Password

☑

Use Unattended Access

☑

Launch Fullscreen

☑

Launch Minimized

☐
5. RustDesk Settings

Form:

Executable

C:\Program Files\RustDesk\rustdesk.exe

Browse

Auto Detect

Server

Relay

API

Encryption Key

Remember Password

☑

Auto Connect

☑
6. VNC
Viewer

UltraVNC

TigerVNC

RealVNC

Executable

Browse

Port

5900

Password

********

Remember

☑
7. Site Route Manager

Administrator dapat membuat beberapa site.

Misalnya

Head Office

Jakarta

Bandung

Surabaya

Makassar

Batam

Singapore

Setiap site memiliki

Site Name

Gateway

Subnet

DNS

Default Remote Tool

Preferred Route

Priority

Description

Button

Add Site

Edit

Delete

Test Route
8. Device Remote Configuration

Setiap device memiliki data:

Hostname

IP

Agent ID

AnyDesk ID

RustDesk ID

VNC Host

VNC Port

Site

Last Online

Disimpan database.

9. Auto Connection

Flow:

Administrator

↓

Klik Device

↓

Klik AnyDesk

↓

Dashboard membaca

Device

↓

AnyDesk ID

↓

Password

↓

Executable

↓

Launcher

↓

Menjalankan

AnyDesk.exe

↓

ID

↓

Password

↓

Connect

Tidak boleh muncul:

Masukkan ID

Masukkan Password

Semuanya otomatis.

10. RustDesk

Flow sama.

RustDesk Button

↓

RustDesk ID

↓

Password

↓

Launch

↓

Connected
11. VNC
Launch Viewer

↓

Host

↓

Port

↓

Password

↓

Connect
12. Launcher Detection

Saat Dashboard startup.

Cari otomatis

AnyDesk

RustDesk

UltraVNC

TigerVNC

RealVNC

Jika tidak ditemukan

↓

Status merah

↓

Browse Executable

13. Test Connection

Button

Test AnyDesk

Test RustDesk

Test VNC

Menampilkan

Executable Found

ID Valid

Password Available

Ready

Success
14. Security

Password

Jangan disimpan plaintext.

Gunakan:

AES-256 Encryption

Master key:

dashboard.key

Password hanya didekripsi saat koneksi dibuat.

15. Auto Detect

Saat Agent online.

Agent otomatis mengirim

Hostname

IP

AnyDesk ID

RustDesk ID

VNC Host

Version

Status

Dashboard

↓

Update Database

↓

Tidak perlu input manual.

16. Auto Launch

Jika administrator klik

AnyDesk

Maka

Dashboard

↓

Ambil Device

↓

Ambil ID

↓

Decrypt Password

↓

Jalankan AnyDesk.exe

↓

Kirim ID

↓

Kirim Password

↓

Connect

↓

Focus Window

Administrator langsung berpindah ke aplikasi AnyDesk tanpa mengetik apa pun.

17. Logging

Catat:

Administrator

Target Device

Remote Tool

Site

IP

Connection Time

Disconnect Time

Duration

Result

Failure Reason
18. Permissions

Role:

Administrator

Supervisor

Helpdesk

Viewer

Viewer

↓

Tidak boleh membuka remote.

19. Final Validation

Pastikan:

Tidak ada input ID manual setelah konfigurasi awal.
Tidak ada input password manual setelah konfigurasi awal.
Dashboard otomatis memilih aplikasi remote sesuai konfigurasi site atau device.
Dashboard mendeteksi lokasi instalasi AnyDesk/RustDesk/VNC secara otomatis.
Password terenkripsi dan tidak pernah ditampilkan dalam bentuk plaintext.
Semua aktivitas remote tercatat di audit log.
Koneksi mendukung retry dan timeout yang dapat dikonfigurasi.
Catatan Penting

Ada satu keterbatasan teknis yang perlu diperhatikan terkait bagian:

"klik AnyDesk lalu langsung connect tanpa memasukkan ID dan password lagi"

Hal ini bisa dilakukan, tetapi bergantung pada kemampuan aplikasi remote tersebut:

RustDesk: relatif mudah diotomatisasi jika Anda mengelola server RustDesk sendiri dan menggunakan fitur password permanen atau autentikasi yang sesuai.
VNC: umumnya mendukung penyimpanan profil koneksi dan password terenkripsi, sehingga auto-connect lebih mudah diimplementasikan.
AnyDesk: auto-connect tanpa interaksi pengguna bergantung pada fitur Unattended Access yang telah dikonfigurasi pada komputer target. Selain itu, cara menjalankan AnyDesk dengan parameter koneksi bergantung pada kemampuan versi aplikasi yang digunakan. Sebaiknya gunakan mekanisme resmi yang didukung AnyDesk dan hindari mengandalkan simulasi pengetikan password atau automasi GUI karena kurang stabil dan dapat melanggar praktik keamanan.

Dengan arsitektur ini, dashboard Anda akan menjadi pusat konfigurasi remote yang jauh lebih profesional, aman, dan mudah dikelola untuk banyak site dan banyak perangkat.
Enterprise Architecture
                                    NOC AI DASHBOARD
┌─────────────────────────────────────────────────────────────────────────────┐
│                           Browser Dashboard                                │
│                                                                             │
│ Remote Access Tools                                                         │
│─────────────────────────────────────────────────────────────────────────────│
│                                                                             │
│ RustDesk │ AnyDesk │ VNC │ WakeOnLAN │ CMD │ PowerShell │ Restart │ Ping    │
│                                                                             │
└───────────────────────────────┬─────────────────────────────────────────────┘
                                │ HTTPS / WebSocket
                                │
                                ▼
                     API Gateway / FastAPI
                                │
            ┌───────────────────┼────────────────────┐
            │                   │                    │
            ▼                   ▼                    ▼
      Device Service      Remote Service      Audit Service
            │                   │                    │
            └───────────────────┼────────────────────┘
                                │
                                ▼
                       PostgreSQL Database
                                │
                                ▼
                    Launcher Service (Admin PC)
                                │
      ┌─────────────────────────┼──────────────────────────┐
      │                         │                          │
      ▼                         ▼                          ▼
  AnyDesk.exe             RustDesk.exe              VNC Viewer.exe
      │                         │                          │
      └─────────────────────────┼──────────────────────────┘
                                │
                           Remote Session
                                │
                                ▼
                       Windows Agent (Client)
Layer 1 — Dashboard

Dashboard hanya bertugas mengirim perintah.

Misalnya administrator memilih:

PC-MKT-NUC

↓

Klik AnyDesk

Dashboard mengirim:

{
  "device":"PC-MKT-NUC",
  "tool":"anydesk"
}

Dashboard tidak pernah mengetahui password asli.

Layer 2 — API Server

Remote Service menerima:

device_id

tool

Misalnya:

device=PC-MKT-NUC

tool=rustdesk

Kemudian:

Cari Device

↓

Cari Site

↓

Cari Remote Config

↓

Decrypt Password

↓

Kirim ke Launcher
Layer 3 — Database

Tabel Device

Device

ID

Hostname

IP

Site

Agent Version

Status

Last Online

Tabel Remote Configuration

Device ID

AnyDesk ID

RustDesk ID

VNC Host

VNC Port

Preferred Tool

Tabel Credential

Credential ID

Encrypted Password

Encryption Version

Created

Updated

Password disimpan:

AES-256-GCM

Bukan plaintext.

Layer 4 — Launcher Service

Inilah komponen paling penting.

Launcher berjalan sebagai Windows Service.

Misalnya:

NOC_LAUNCHER.exe

Launcher memiliki REST API lokal.

localhost:45600

Dashboard mengirim:

{
    "tool":"rustdesk",
    "id":"987654321",
    "password":"*****"
}

Launcher yang membuka aplikasi.

Launcher Architecture
Launcher

│

├── AnyDesk Module

├── RustDesk Module

├── VNC Module

├── Credential Module

├── Process Manager

├── Logger

└── Config Manager
AnyDesk Module
Dashboard

↓

Launcher

↓

Cari AnyDesk.exe

↓

Load Credential

↓

Launch

↓

Focus Window

↓

Connected

Launcher otomatis:

Scan Registry

↓

Scan PATH

↓

Scan Program Files

↓

Temukan:

AnyDesk.exe

Jika tidak ada

↓

Status

Not Installed
RustDesk Module
Klik RustDesk

↓

Launcher

↓

Cari rustdesk.exe

↓

Load ID

↓

Load Password

↓

Launch

↓

Connected

Jika RustDesk memakai server sendiri

↓

Launcher juga membaca:

Relay

API

Public Key
VNC Module
Klik VNC

↓

Launcher

↓

Cari Viewer

↓

Host

↓

Port

↓

Password

↓

Connected

Support:

UltraVNC

TigerVNC

RealVNC
Site Manager

Setiap site memiliki konfigurasi.

Misalnya

HO

↓

RustDesk

Cabang

Bandung

↓

AnyDesk

Pabrik

Karawang

↓

VNC

Database:

Site

Preferred Tool

Gateway

Subnet

Description

Saat memilih device:

Device

↓

Site

↓

Preferred Tool

↓

Launcher
Windows Agent

Agent otomatis mengirim

Hostname

IP

AnyDesk ID

RustDesk ID

VNC Port

OS

Version

Online

Latency

Server selalu update.

Tidak perlu input manual.

Auto Discovery

Saat agent start

↓

Cari AnyDesk

↓

Ambil ID

↓

Cari RustDesk

↓

Ambil ID

↓

Cari VNC

↓

Ambil Port

↓

Server update.

Auto Connect Flow

Administrator

↓

Klik AnyDesk

↓

Dashboard

↓

API

↓

Database

↓

Launcher

↓

AnyDesk.exe

↓

Connect

↓

Foreground

↓

Desktop Client

RustDesk

↓

Dashboard

↓

Launcher

↓

rustdesk.exe

↓

Connect

↓

Foreground

↓

Desktop Client

VNC

↓

Dashboard

↓

Launcher

↓

Viewer

↓

Connect

↓

Foreground

↓

Desktop Client


---

# Audit Log

Semua koneksi disimpan.


Administrator

Device

Tool

Site

Start

End

Duration

IP

Status

Reason


---

# Security

Launcher hanya menerima request dari:


localhost

JWT

HMAC

TLS


Tidak menerima request luar.

---

# Folder Structure


REMOTE_ACCESS/

launcher/

│

├── launcher.py

├── launcher_api.py

├── config.py

├── credential.py

├── logger.py

│

├── modules/

│ anydesk.py

│ rustdesk.py

│ vnc.py

│

├── detector/

│ detect_anydesk.py

│ detect_rustdesk.py

│ detect_vnc.py

│

├── security/

│ aes.py

│ jwt.py

│ hmac.py

│

└── database/

   sqlite_cache.py

---

# Roadmap Pengembangan

Saya menyarankan membangun fitur ini dalam beberapa fase agar risiko rendah dan mudah diuji.

### **Phase 1 – Remote Launcher Foundation**
- Launcher Service di PC Administrator.
- Auto-detect instalasi AnyDesk, RustDesk, dan VNC Viewer.
- Dashboard dapat meluncurkan aplikasi remote yang dipilih.
- Logging dasar.

### **Phase 2 – Device & Credential Management**
- Agent mengirim AnyDesk ID, RustDesk ID, dan informasi VNC secara otomatis.
- Database menyimpan konfigurasi setiap device.
- Password disimpan terenkripsi (AES-256-GCM).
- Konfigurasi per-site dan per-device.

### **Phase 3 – One-Click Remote Access**
- Klik satu tombol di dashboard.
- Dashboard memilih tool sesuai konfigurasi.
- Launcher membuka aplikasi remote dan menggunakan mekanisme resmi yang didukung aplikasi tersebut untuk memulai koneksi.
- Fokus otomatis berpindah ke jendela aplikasi remote.

### **Phase 4 – Enterprise Features**
- Role-Based Access Control (RBAC).
- Audit log lengkap.
- Session recording (jika diperlukan dan sesuai kebijakan organisasi).
- Approval workflow untuk koneksi remote.
- Multi-site policy.
- Dashboard status sesi remote secara real-time.

Dengan arsitektur ini, sistem Anda akan menyerupai solusi RMM enterprise: **dashboard menjadi pusat orkestrasi**, sedangkan **Launcher Service** menjadi komponen yang bertanggung jawab menjalankan aplikasi remote di komputer administrator secara aman dan terkelola.