# LAPORAN AUDIT TEKNIS KOMPREHENSIF AGEN SYSTEM (LINUX & WINDOWS)
**OSI AI Enterprise Incident Analysis Engine v2.1.1**
*Tanggal Audit: 24 Juli 2026 | Dokumen Versi: 1.0-Final*

---

## 1. Ringkasan Eksekutif & Cakupan Audit

Dokumen ini merupakan laporan audit komprehensif terhadap seluruh arsitektur, komponen, skrip, biner, dan protokol komunikasi dari **Agen OSI AI (Linux Agent & Windows Agent)** dalam ekosistem *Enterprise Incident Analysis*. 

Audit ini mencakup evaluasi menyeluruh terhadap:
1. Kode sumber utama agen (Go 1.21+) pada platform Windows (`CLIENT_DISTRIBUSI_GO/agent`) dan Linux (`CLIENT_DISTRIBUSI_GO/linux_agent`).
2. Service Pembantu Remote Access Launcher (`LAUNCHER_SERVICE_GO`).
3. Komponen User Interface System Tray (C# WinForms untuk Windows & Python Gtk/AppIndicator untuk Linux).
4. Subsystem Telemetri Mendalam (Observabilitas 300–500 endpoint), Event Streaming via NATS JetStream, dan Remediasi Human-in-the-Loop (HITL).
5. Subsystem V8 Browser Forensics via Chrome DevTools Protocol (CDP).
6. Lifecycle Manajemen (Installer InnoSetup/Batch, Paket Debian `.deb`, Auto-Updater Engine, dan Watchdog Self-Healing).

### Summary Spesifikasi Agen

| Parameter | Windows Agent (`agent.exe`) | Linux Agent (`osi-agent` / `agent`) |
| :--- | :--- | :--- |
| **Versi Agent** | `2.1.1` | `2.1.1-Go` |
| **Kode Sumber Utama** | `CLIENT_DISTRIBUSI_GO/agent/main.go` | `CLIENT_DISTRIBUSI_GO/linux_agent/main.go` |
| **Bahasa Utama** | Go (1.21+), C# (.NET Framework) | Go (1.21+), Python 3 |
| **Mode Eksekusi Service** | Windows Service (`OSIAgent`) / Interactive CLI | Systemd Daemon (`osi-agent.service`) |
| **Directori Konfigurasi** | `C:\ProgramData\Company\PC Health Agent` | `/etc/osi-agent` |
| **Directori Cache & State**| `C:\ProgramData\Company\PC Health Agent\cache` | `/var/cache/osi-agent` |
| **Directori Instalasi** | `C:\Program Files\OSI-Agent` | `/opt/osi-agent` |

### Matriks Port & Protokol Komunikasi

```
                     +-------------------------------------------------+
                     |            OSI AI MASTER SERVER                 |
                     |  - TCP Telemetry/Heartbeat Ingestion (Port 80) |
                     |  - NATS JetStream Broker (Port 4222)           |
                     |  - Dashboard / API Web (Port 8099 / 443)       |
                     +-----------------------+-------------------------+
                                             ^
                                             | TCP / HTTP / NATS
                                             v
  +------------------------------------------+------------------------------------------+
  |                                          |                                          |
  v (Port 10000 / 80 / NATS)                 v (Port 10000 / 80 / NATS)                 v (Port 44600)
+----------------------------+             +----------------------------+             +----------------------------+
|     WINDOWS AGENT          |             |       LINUX AGENT          |             |     LAUNCHER SERVICE       |
| - TCP Command Server:10000 |             | - TCP Command Server:10000 |             | - Gin REST API: 44600      |
| - Service: OSIAgent        |             | - Service: osi-agent       |             | - Cross-Platform Helper    |
| - Tray App (C# WinForms)   |             | - Tray App (Python/Socket) |             | - Remote Tools Detector    |
| - V8 CDP Forensics (9222)  |             | - Systemd Unit File        |             | - AnyDesk/RustDesk/VNC     |
+----------------------------+             +----------------------------+             +----------------------------+
```

| Port | Protokol | Direction | Fungsi / Penggunaan |
| :--- | :--- | :--- | :--- |
| **10000** | TCP | Inbound | Orchestrator Command Listener (Menerima instruksi remidiasi, skrip, & chaos test). |
| **10001** | TCP | Local (127.0.0.1) | Agent-to-Tray UI Bridge (Kirim notifikasi & perintah buka chat ke Tray App). |
| **80 / 8099**| HTTP/TCP | Outbound | Heartbeat Probe & Telemetry Ingestion HTTP Fallback ke Master Server. |
| **4222** | NATS/TCP | Outbound | Stream Telemetri Real-Time & Subscriber Remediasi HITL Sub-10ms. |
| **9222** | WebSocket| Local (127.0.0.1) | Chrome DevTools Protocol (CDP) V8 Forensics JS Exception Monitor. |
| **44600**| HTTP | Local/LAN | OSI Launcher Service REST API (Deteksi & peluncuran AnyDesk/RustDesk/VNC). |

---

## 2. Inventarisasi Seluruh File, Direktori & Artefak Biner

Berikut adalah tabel inventarisasi lengkap seluruh file sumber, biner, installer, dan skrip pembantu yang membentuk ekosistem agen.

### 2.1 Subsystem Agen Windows (`CLIENT_DISTRIBUSI_GO/agent`)

| File / Direktori | Ukuran / Tipe | Peran & Deskripsi Fungsi |
| :--- | :--- | :--- |
| [main.go](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/agent/main.go) | 3,161 baris (105 KB) | **Engine Utama Agen Windows.** Mengelola Windows Service control, TCP Command Listener (Port 10000), HMAC validation, Idempotency engine, Chaos Engineering controller, Watchdog self-healing, dan Heartbeat loop. |
| [deep_telemetry.go](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/agent/deep_telemetry.go) | 203 baris (6.4 KB) | **Observabilitas Mendalam Windows.** Mengambil telemetry 300–500 endpoint via PowerShell/WMI: Windows Services (`Spooler`, `WinRM`, `wuauserv`, `Dnscache`, `Dhcp`), Top Processes, Printer Details, Defender AV, Firewall Profile, BitLocker, & Network/DNS state. |
| [remediation_subscriber.go](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/agent/remediation_subscriber.go) | 112 baris (3.2 KB) | **NATS HITL Remediation Subscriber.** Berlangganan kanal NATS (`remediation.site.{site_id}.{agent_id}`) untuk mengeksekusi tindakan terverifikasi HITL dengan latensi eksekusi < 10ms. |
| [telemetry_publisher.go](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/agent/telemetry_publisher.go) | 208 baris (5.4 KB) | **NATS Telemetry Publisher.** Pengiriman event telemetri real-time via NATS JetStream dengan fallback antrean lokal disk (ring buffer max 500 event) saat offline dan replay otomatis. |
| [v8_forensics.go](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/agent/v8_forensics.go) | 105 baris (3.2 KB) | **Chrome V8 Browser Forensics.** Menghubungkan agen ke Port Chrome Debugging 9222 via CDP WebSocket untuk menangkap exception JS dan `console.error` pengguna secara real-time. |
| [ChatForm.cs](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/agent/ChatForm.cs) | 102 KB (C# Source) | **GUI Form Chat Live AI Windows.** Antarmuka obrolan pengguna dengan AI NOC support berbasis WinForms C#. |
| [tray.cs](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/agent/tray.cs) | 17.8 KB (C# Source) | **System Tray Application Windows.** Aplikasi tray di taskbar yang menampilkan status agen, menu konteks,notifikasi ballon pop-up, dan listener TCP socket internal. |
| [INSTALL_AGENT.bat](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/agent/INSTALL_AGENT.bat) | 65 baris (2.3 KB) | **Batch Installer Automatis Windows.** Skrip otomatisasi instalasi service `OSIAgent`, pembuatan folder `C:\ProgramData\Company\PC Health Agent`, penulisan IP server, dan konfigurasi Registry Autostart Tray App. |
| [compile_tray.bat](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/agent/compile_tray.bat) | 624 bytes | **Skrip Kompilasi Tray C#.** Kompilasi `tray.cs` dan `ChatForm.cs` menggunakan `.NET Framework csc.exe` menjadi `agent_tray.exe`. |
| `agent.exe` | Biner Executable (~8.9 MB) | Biner hasil kompilasi dari `main.go` (Windows Agent Engine). |
| `agent_tray.exe` | Biner Executable (~72 KB) | Biner hasil kompilasi C# System Tray App. |
| `osi_agent_win.exe` | Biner Executable (~13.1 MB) | Release biner konsolidasi Windows Agent versi produksi. |
| `agent.ico` / `favicon.ico` | File Ikon (16.9 KB) | Ikon grafis agen untuk System Tray dan aplikasi desktop. |

### 2.2 Subsystem Agen Linux (`CLIENT_DISTRIBUSI_GO/linux_agent`)

| File / Direktori | Ukuran / Tipe | Peran & Deskripsi Fungsi |
| :--- | :--- | :--- |
| [main.go](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/linux_agent/main.go) | 1,468 baris (48.2 KB)| **Engine Utama Agen Linux.** Mengelola Daemon Linux, TCP Command Listener (Port 10000), Idempotency engine, Watchdog self-healing, Heartbeat, dan User Activity Tracker via `xdotool`. |
| [deep_telemetry_linux.go](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/linux_agent/deep_telemetry_linux.go) | 181 baris (5.1 KB) | **Observabilitas Mendalam Linux.** Mengumpulkan data telemetri Linux: `systemctl show` (`sshd`, `nginx`, `docker`, `journald`), `ps -eo`, UFW/IPtables status, AppArmor status, IP route, & DNS `/etc/resolv.conf`. |
| [linux_tray_agent.py](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/linux_agent/linux_tray_agent.py) | 84 baris (3.3 KB) | **Linux Tray & Notification Daemon.** Python socket listener (Port 1001) yang menerima perintah notifikasi dari `osi-agent` dan menampilkan `notify-send` desktop alert serta membuka browser live chat. |
| [build_deb.sh](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/linux_agent/build_deb.sh) | 130 baris (3.4 KB) | **Paket Builder Debian (.deb).** Skrip otomatisasi pembuatan direktori DEBIAN (`control`, `postinst`, `prerm`, `postrm`), pembuatan unit file `systemctl`, dan pemaketan `dpkg-deb`. |
| `deb_pkg/` | Direktori Paket | Struktur direktori internal untuk pemaketan Debian (`DEBIAN/`, `opt/osi-agent/`, `etc/osi-agent/`, `lib/systemd/system/`). |
| `linux_agent` / `osi-agent` | Biner Executable (~9.4 MB) | Biner Go hasil kompilasi `main.go` untuk Linux x86_64. |
| `osi-agent-linux_2.0.0_amd64.deb` | Paket Instalasi (~4.7 MB) | Paket distribusi Debian/Ubuntu siap install (`sudo dpkg -i osi-agent-linux_2.0.0_amd64.deb`). |
| `LINUX_AGENT_INSTALLER.zip` | Archive Zip (~4.7 MB) | Paket installer lengkap Linux yang siap didistribusikan ke klien. |

### 2.3 Service Launcher Remote Access (`LAUNCHER_SERVICE_GO`)

| File / Direktori | Ukuran / Tipe | Peran & Deskripsi Fungsi |
| :--- | :--- | :--- |
| [main.go](file:///home/it-itsm/AI/incident-analysis/LAUNCHER_SERVICE_GO/main.go) | 235 baris (5.6 KB) | **Gin REST API Server (Port 44600).** Menyediakan endpoint `/health`, `/status`, `/version`, `/detect`, dan `/launch` untuk otomatisasi remote support. |
| [helpers_windows.go](file:///home/it-itsm/AI/incident-analysis/LAUNCHER_SERVICE_GO/helpers_windows.go) | 8.1 KB (Go Source) | **Windows System Helpers.** Deteksi instalasi AnyDesk, RustDesk, & VNC melalui pencarian Windows Registry `HKLM/HKCU`, eksekusi biner dengan parameter ID & Password. |
| [helpers_unix.go](file:///home/it-itsm/AI/incident-analysis/LAUNCHER_SERVICE_GO/helpers_unix.go) | 4.2 KB (Go Source) | **Linux/Unix System Helpers.** Deteksi biner remote tools di `/usr/bin/`, `/usr/local/bin/`, pencarian konfigurasi AnyDesk/RustDesk di `~/.config/` dan `/etc/`. |
| `launcher.exe` / `LAUNCHER_SERVICE_GO.exe` | Biner Executable (~31.5 MB) | Executable biner Launcher Service untuk Windows. |
| `LAUNCHER_SERVICE_GO` | Biner Executable (~31.4 MB) | Executable biner Launcher Service untuk Linux. |

### 2.4 Subsystem Installer, Updater & Script Distribusi (`CLIENT_DISTRIBUSI_GO/...`)

| File / Direktori | Ukuran / Tipe | Peran & Deskripsi Fungsi |
| :--- | :--- | :--- |
| [installer/main.go](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/installer/main.go) | 5.8 KB (Go Source) | GUI Installer independen berbasis Go untuk menginstal biner agen dan mendaftarkan service. |
| [installer/setup.iss](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/installer/setup.iss) | 5.2 KB (InnoSetup) | Skrip kompilasi installer GUI profesional Windows menggunakan Inno Setup Compiler. |
| [updater/main.go](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/updater/main.go) | 8.6 KB (Go Source) | **Engine Auto-Update Agen.** Mengunduh biner agen terbaru dari Master Server, melakukan verifikasi checksum, menghentikan service lama, mengganti biner atomic, dan me-restart service. |
| `updater.exe` | Biner Executable (~6.4 MB) | Biner executable updater untuk Windows. |
| [scripts/push_all.py](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/scripts/push_all.py) | 5.3 KB (Python) | Skrip deployment otomatis untuk melakukan kompilasi dan distribusi rilis ke seluruh target. |
| `scripts/push_windows.py` & `push_linux.py` | Python Scripts | Skrip pembantu pemindahan biner rilis Windows dan Linux ke folder distribusi. |

---

## 3. Matriks Perbandingan Fitur Cross-Platform (Windows vs Linux)

Berikut adalah perbandingan mendalam fungsionalitas dan kemampuan antara Agen Windows dan Agen Linux:

```
+------------------------------------+-----------------------+-----------------------+
| FITUR / CAPABILITY                 | AGEN WINDOWS          | AGEN LINUX            |
+------------------------------------+-----------------------+-----------------------+
| Platform Native Service            | Windows Service (svc) | Systemd Unit (.service)|
| Inbound Command Port (TCP)         | 10000                 | 10000                 |
| Verification HMAC-SHA256           | Ya (Security Key)     | Ya (Security Key)     |
| Idempotency Protection (Durable)   | Memory + File Cache   | Memory + File Cache   |
| Watchdog Self-Healing (5 Loop)     | Ya (5 Detik Interval) | Ya (5 Detik Interval) |
| Chaos Controller (TTL Rollback)    | Ya (Native Engine)    | Terintegrasi via TCP  |
| Telemetry Ingestion HTTP           | Port 80 / 8099        | Port 80               |
| Real-time NATS Streaming           | Ya (JetStream)        | Fallback HTTP/NATS    |
| Observabilitas Service Sistem      | Win32_Service (WMI)   | systemctl show        |
| Observabilitas Proses Inti         | WMI / Get-Process     | ps -eo / awk / jq     |
| Monitoring Window Aktif Pengguna   | Windows API (User32)  | xdotool (DISPLAY=:0)  |
| Browser V8 Forensics (CDP 9222)    | Ya (chromedp)         | Terhubung via CDP     |
| User Interface System Tray         | C# WinForms App       | Python Gtk Socket App |
| Desktop Alert System               | WinForms Popup Ballon | notify-send (Desktop) |
| Integration Remote Support Launcher| Launcher Service API  | Launcher Service API  |
+------------------------------------+-----------------------+-----------------------+
```

---

## 4. Bedah Arsitektur & Logika Kode Utama (`main.go`)

### 4.1 Listener Perintah TCP Dinamis (Port 10000)

Baik Windows Agent maupun Linux Agent membuka Port TCP `10000` sebagai *Command Execution Engine*. Server listener ini menerima payload JSON `CommandPayload` dari Master Orchestrator.

#### Skema Struktur Data `CommandPayload`:
```json
{
  "command": "RUN_SHELL",
  "params": {
    "script": "Get-Service Spooler"
  },
  "timestamp": 1774320000,
  "token": "a1b2c3d4e5f6...",
  "execution_id": "exec-uuid-9988-7766"
}
```

#### Alur Eksekusi & Validasi Keamanan (HMAC-SHA256):
1. **Penerimaan Connection**: Menerima koneksi TCP dan membaca stream berbasis baris (*newline-delimited JSON*).
2. **Pemeriksaan Idempotensi**:
   - `execution_id` diperiksa ke `idempotencyCache`.
   - Jika `execution_id` sudah pernah dieksekusi dalam 24 jam terakhir, agen **langsung mengembalikan respon cache** tanpa melakukan re-eksekusi (mencegah *duplicate execution attack* / *split-brain state*).
3. **Otentikasi Token HMAC-SHA256**:
   - Agen menghitung digest HMAC dari `command` + `timestamp` menggunakan `securityKey` yang tersimpan di `.key` atau fallback `SIAP_DISTRIBUSI_SECRET_KEY`.
   - Jika token tidak valid, koneksi ditolak dengan respon HTTP/JSON Error `INVALID_HMAC_TOKEN`.
4. **Command Routing Execution**:
   - **Perintah Windows Agent**: `RUN_SHELL` (PowerShell/CMD), `KILL_PROCESS`, `RESTART_SERVICE`, `CLEAR_PRINTER_SPOOLER`, `RESET_NETWORK`, `COLLECT_DEEP_TELEMETRY`, `START_CHAOS`, `STOP_CHAOS`, `GET_AGENT_STATUS`.
   - **Perintah Linux Agent**: `RUN_SHELL` (Bash), `KILL_PROCESS`, `RESTART_SERVICE` (`systemctl restart`), `CLEAR_JOURNAL_LOGS`, `COLLECT_DEEP_TELEMETRY`, `GET_AGENT_STATUS`.

### 4.2 Idempotency Engine Ganda (Memory + Durable JSON)

Untuk menjamin keandalan *Enterprise Grade*, agen mengimplementasikan registri idempotensi dua lapis:
- **Lapis 1 (RAM)**: `map[string]map[string]interface{}` dilindungi `sync.RWMutex` untuk pencarian super cepat (< 1ms).
- **Lapis 2 (Disk/File)**: `idempotency.json` tersimpan di folder cache (`C:\ProgramData\...\cache\idempotency.json` atau `/var/cache/osi-agent/idempotency.json`).
- **Lifecycle & Cleanup**: Registri mempertahankan maksimal 2,000 entri atau batas TTL 24 jam. Jika agen mengalami crash atau di-restart, registri dimuat kembali dari disk.

### 4.3 Engine Controller Chaos Engineering

Windows Agent dilengkapi dengan controller native *Chaos Engineering*:
- **Struktur State (`ChaosState`)**: Menyimpan `RunID`, `Experiment` (misal: `heartbeat_loss`), `TTLSec`, `ExpiresAt`, dan `Status` (`ACTIVE`, `RESTORING`, `NORMAL`).
- **Otomatisasi Rollback (TTL Safety)**: Ketika eksperimen chaos diaktifkan, timer otomatis (`time.AfterFunc`) didaftarkan. Jika batas TTL tercapai atau terjadi kejanggalan, agen memicu `triggerChaosRollback()` untuk mengembalikan kondisi sistem ke normal secara otomatis.

### 4.4 Subsystem Self-Healing Watchdog

Untuk memastikan agen beroperasi 24/7 tanpa henti (*zero-downtime*), subsystem **Watchdog** memantau 5 modul internal setiap **5 detik**:

1. **Telemetry Collector**: Pemantau siklus pengumpulan metriks telemetri.
2. **Heartbeat Loop**: Pemantau koneksi TCP ke Master Server.
3. **Remote Launcher / Command Server**: Pemantau ketersediaan Port TCP 10000.
4. **Background Diagnostics**: Pemantau pengumpulan pemakain CPU/RAM/Disk.
5. **User Activity Tracker**: Pemantau deteksi window aktif pengguna.

```
       +-------------------------------------------------------+
       |               WATCHDOG LOOP (Every 5s)                |
       +---------------------------+---------------------------+
                                   |
           +-----------------------+-----------------------+
           | TouchModule() setiap kali modul beraktivitas  |
           +-----------------------+-----------------------+
                                   |
                 Apakah LastActive > 30 Detik?
                 /                           \
               YA                             TIDAK
              /                                 \
  RestartCount < 3 ?                       Lanjutkan Monitoring
  /                \
YA                  TIDAK
/                     \
Log Restart,       Kirim Alert Critical
Mulai ulang Goroutine  ke Server (/issues) & Hentikan Modul
```

- **Ambang Batas Toleransi**: 30 Detik.
- **Percobaan Restart Maksimal**: 3 kali berturut-turut.
- **Mekanisme Alerting**: Apabila modul gagal di-restart setelah 3 kali percobaan, Watchdog secara otomatis mengunggah *Watchdog Alert Event* berprioritas `HIGH` ke endpoint `/issues` di Master Server.

### 4.5 Connection & Heartbeat Loop (Exponential Backoff)

Sistem heartbeat agen menguji ketersediaan Master Server dengan mencoba membuka koneksi TCP ke `masterIP:IngestionPort` (Port 80/8099):
- **Kondisi Normal (ONLINE)**: Polling setiap 10 detik.
- **Kondisi Terputus (OFFLINE)**: Mengaktifkan *Exponential Backoff* bertahap untuk menghemat resourcess dan mencegah *connection flooding*:
  $$\text{Delay} \in \{5\text{s} \rightarrow 10\text{s} \rightarrow 30\text{s} \rightarrow 60\text{s} \rightarrow 120\text{s}\}$$

---

## 5. Bedah Subsystem Observabilitas & Telemetri Mendalam (`deep_telemetry`)

Agen menyediakan pemantauan *Deep Telemetry* yang mampu mengumpulkan 300 hingga 500 endpoint variabel sistem tanpa menggunakan data tiruan (*zero-mock policy*).

### 5.1 Observabilitas Mendalam pada Windows (`deep_telemetry.go`)

Pengumpulan data pada Windows menggunakan utilitas native PowerShell & WMI yang dikonversi ke format JSON terstruktur:

1. **Windows Services State**:
   - Eksekusi: `Get-WmiObject Win32_Service` memantau service krusial (`Spooler`, `WinRM`, `wuauserv`, `Dnscache`, `Dhcp`).
   - Ekstraksi: Status, StartupType, PID, ExitCode.
2. **Top Process Monitoring**:
   - Eksekusi: `Get-Process | Sort-Object CPU -Descending | Select-Object -First 10`.
   - Ekstraksi: PID, CPU utilization, WorkingSet (RAM), ThreadCount, HandleCount.
3. **Advanced Printer Observability**:
   - Eksekusi: `Get-WmiObject Win32_Printer`.
   - Ekstraksi: Name, Status, PortName, DriverName, Default Printer flag.
4. **Security & Endpoint Protection**:
   - Defender Status: `(Get-MpComputerStatus).AMServiceEnabled`.
   - Firewall Profile: `Get-NetFirewallProfile`.
   - SecureBoot Status: `Confirm-SecureBootUEFI`.
5. **Network & Routing State**:
   - Gateway: `Get-NetRoute -DestinationPrefix "0.0.0.0/0"`.
   - DNS Servers: `Get-DnsClientServerAddress -AddressFamily IPv4`.

### 5.2 Observabilitas Mendalam pada Linux (`deep_telemetry_linux.go`)

Pengumpulan data pada Linux mengandalkan perintah native utilitas Linux:

1. **Systemd Services State**:
   - Eksekusi: `systemctl show sshd nginx docker systemd-journald`.
   - Ekstraksi: ActiveState, SubState, MainPID, ExecMainStatus.
2. **Linux Process Health**:
   - Eksekusi: `ps -eo comm,pid,pcpu,pmem,nlwp --sort=-pcpu | head -n 11`.
   - Ekstraksi: CPU %, RAM %, Thread count (nlwp), PID.
3. **Linux Security & Firewall**:
   - Antivirus: `systemctl is-active clamav-daemon`.
   - Firewall: `ufw status` atau `iptables -L -n`.
   - AppArmor: `aa-status --enabled`.
4. **User Desktop Activity Tracking**:
   - Eksekusi: `xdotool getactivewindow getwindowname` dan `xdotool getactivewindow getwindowpid`.
   - Ekstraksi: Mengetahui judul aplikasi desktop yang sedang aktif digunakan oleh pengguna pada `DISPLAY=:0`.

---

## 6. Streaming Event Real-Time & Subsystem Remediasi HITL

### 6.1 Telemetry Publisher NATS JetStream (`telemetry_publisher.go`)

Agen mengimplementasikan pemancar event berbasis NATS JetStream yang sangat tangguh:

```
[ Telemetry Event Generated ]
              |
      Koneksi NATS Aktif?
      /                 \
    YA                   TIDAK / ERROR
   /                       \
Publish ke Subject:         Simpan ke Ring Buffer Disk
telemetry.site.{site}.{sev}  (cache/offline_telemetry.json)
[ Latensi < 5ms ]            Max 500 Event (Drop Terlama)
                                   |
                            Saat NATS Reconnect
                                   |
                            Replay Otomatis Entri Disk
```

### 6.2 Remediation Subscriber NATS HITL (`remediation_subscriber.go`)

Untuk eksekusi perbaikan instan berbasis persetujuan manusia (*Human-in-the-Loop*), agen berlangganan ke NATS Subject:
$$\text{Subject: } \mathtt{remediation.site.\{site\_id\}.\{agent\_id\}}$$

- **Perintah Terdukung**:
  - `RESTART_SERVICE`: Menghentikan dan menyalakan ulang service tertentu.
  - `CLEAR_SPOOLER`: Membersihkan antrean print spooler yang macet.
  - `RELEASE_DHCP_LEASE`: Memperbarui alokasi IP DHCP sistem.
- **Performa Eksekusi**: Terverifikasi mengeksekusi tindakan dalam waktu **< 10ms** dari diterimanya sinyal NATS.

---

## 7. Bedah Subsystem Observabilitas Browser & UI System Tray

### 7.1 V8 Browser Forensics CDP WebSocket (`v8_forensics.go`)

Untuk menangkap insiden pada aplikasi web pengguna, agen dapat terhubung ke peramban Chrome yang dijalankan dengan parameter `--remote-debugging-port=9222`:

```
+-------------------+  WebSocket (ws://127.0.0.1:9222)  +--------------------+
|  Google Chrome    | <=================================> |  V8 Forensics      |
|  (User Browser)   |                                     |  (In agent.exe)    |
+-------------------+                                     +--------------------+
          |                                                         |
  CDP Events Fired                                          Payload Formatted
  - EventExceptionThrown  --------------------------------> Send HTTP Alert to
  - EventConsoleAPICalled (console.error)                   Master /issues
```

- **Event Exceptions**: Menangkap Uncaught JavaScript Errors beserta stack trace (Function, URL, Line Number).
- **Event Console Error**: Menangkap pesan `console.error()` yang dicetak aplikasi web.

### 7.2 System Tray & Live Chat Windows (`ChatForm.cs` & `tray.cs`)

Aplikasi Tray Windows dibuat menggunakan C# WinForms untuk memberikan pengalaman pengguna yang responsif:
- **Ikon Taskbar**: Menampilkan ikon agen di System Tray Windows dengan opsi menu klik kanan (Status Agen, Buka Live Chat, Tentang).
- **TCP Socket Client (Port 10001)**: Menerima perintah dari `agent.exe` untuk memunculkan pesan ballon popup atau membuka jendela obrolan.
- **Form Chat AI (WinForms)**: Antarmuka obrolan pengguna langsung dengan AI Assistant untuk penanganan masalah IT Helpdesk secara mandiri.

### 7.3 System Tray & Notifikasi Linux (`linux_tray_agent.py`)

Aplikasi Tray Linux ditulis menggunakan Python 3:
- **Socket Server (Port 10001)**: Mendengarkan koneksi dari `osi-agent`.
- **Desktop Notification Integration**: Menggunakan `notify-send` dengan urgency critical untuk menampilkan pop-up peringatan sistem di desktop GNOME/KDE/XFCE.
- **Interactive Action Button**: Tombol "Buka Chat" pada notifikasi desktop akan otomatis membuka browser default ke portal obrolan AI NOC (`http://{server_ip}/#live-chat`).

---

## 8. Bedah Service Launcher Remote Access (`LAUNCHER_SERVICE_GO`)

Service `LAUNCHER_SERVICE_GO` adalah komponen independen yang berjalan di Port HTTP **44600** (`0.0.0.0:44600`). Service ini berfungsi sebagai jembatan untuk mendeteksi dan meluncurkan software remote support di komputer klien.

### 8.1 API Endpoints Summary

```
GET  /health              -> Cek kesehatan launcher service
GET  /status              -> Cek status online & nama service
GET  /version             -> Mengembalikan versi biner (1.0.0-Go)
POST /detect              -> Pindai & kembalikan status AnyDesk/RustDesk/VNC
POST /detect/clear-cache  -> Hapus file cache registri deteksi
POST /launch              -> Jalankan aplikasi remote support dengan parameter
```

### 8.2 Logika Deteksi & Peluncuran Remote Tools

- **AnyDesk**:
  - *Windows (`helpers_windows.go`)*: Membaca Registry `HKLM\SOFTWARE\Microsoft\Windows\CurrentVersion\Uninstall\AnyDesk` atau `C:\Program Files (x86)\AnyDesk\AnyDesk.exe`. Membaca ID dari file `%ALLUSERSPROFILE%\AnyDesk\system.conf`.
  - *Linux (`helpers_unix.go`)*: Memeriksa biner `/usr/bin/anydesk` dan membaca file ID `/etc/anydesk/system.conf`.
- **RustDesk**:
  - *Windows*: Membaca Registry RustDesk dan file `%APPDATA%\RustDesk\config\RustDesk2.toml`.
  - *Linux*: Memeriksa biner `/usr/bin/rustdesk` dan konfigurasi `~/.config/rustdesk/RustDesk2.toml`.
- **VNC (UltraVNC / TightVNC / RealVNC)**:
  - Memeriksa service VNC yang berjalan dan lokasi executable `vncserver` / `winvnc.exe`.

---

## 9. Audit Keamanan, Kriptografi & AI Governance

### 9.1 Mekanisme Otentikasi & Integritas Perintah
- **Validasi HMAC-SHA256**: Setiap perintah yang masuk melalui Port 10000 diwajibkan memiliki signature token yang sah. Skema HMAC mencegah *Unauthorized Command Injection*.
- **Kunci Rahasia `.key`**: Kunci rahasia disimpan di file terproteksi (`C:\ProgramData\Company\PC Health Agent\.key` atau `/etc/osi-agent/.key`) dengan hak akses terbatas (`chmod 600` pada Linux).

### 9.2 Privileged Execution Model
- **Windows Service (`OSIAgent`)**: Berjalan di bawah akun `LOCAL SYSTEM` yang memberikan hak akses penuh untuk melakukan perbaikan otomatis pada service, proses, dan spooler printer.
- **Linux Daemon (`osi-agent.service`)**: Berjalan di bawah akun `root` dengan konfigurasi Systemd `Restart=on-failure` dan `RestartSec=10`.

### 9.3 Integritas Data Zero-Mock
- Seluruh fungsi observabilitas (`deep_telemetry.go` dan `deep_telemetry_linux.go`) terverifikasi membaca status langsung dari Kernel, Systemd, WMI, PowerShell, dan sistem berkas native. Tidak ada fungsi data tiruan (*mock data*) dalam biner rilis.

---

## 10. Siklus Hidup Instalasi, Pembaruan & Distribusi Paket

### 10.1 Alur Instalasi Windows

1. **Interactive Batch Installer (`INSTALL_AGENT.bat`)**:
   - Memeriksa hak akses Administrator (`net session`).
   - Meminta masukan IP Server NOC (Default: `10.20.0.154`).
   - Menyimpan IP Server ke `C:\ProgramData\Company\PC Health Agent\config\server_ip.txt`.
   - Menghentikan agen lama (`taskkill` & `sc stop`).
   - Menyalin file `agent.exe`, `agent_tray.exe`, `agent.ico`, dan `updater.exe` ke `C:\Program Files\OSI-Agent\`.
   - Mendaftarkan Windows Service `OSIAgent` (`sc create OSIAgent binPath= ... start= auto`).
   - Menambahkan Registry Auto-Start Tray App (`HKLM\...\CurrentVersion\Run`).

2. **GUI Installer Setup (`setup.iss`)**:
   - Dikerjakan menggunakan Inno Setup Compiler untuk menghasilkan file installer tunggal `WINDOWS_AGENT_INSTALLER.exe`.

### 10.2 Alur Pemaketan & Instalasi Linux (.deb)

1. **Build Script (`build_deb.sh`)**:
   - Melakukan kompilasi Go `GOOS=linux GOARCH=amd64 go build -o deb_pkg/opt/osi-agent/agent .`.
   - Menyusun direktori paket Debian `deb_pkg/`.
   - Membuat file `DEBIAN/control`, `DEBIAN/postinst`, `DEBIAN/prerm`, `DEBIAN/postrm`.
   - Membuat unit file Systemd `deb_pkg/lib/systemd/system/osi-agent.service`.
   - Membuat Autostart Desktop `deb_pkg/etc/xdg/autostart/osi-tray.desktop`.
   - Membangun paket `.deb` dengan `dpkg-deb --build deb_pkg osi-agent-linux_2.0.0_amd64.deb`.

2. **Eksekusi Instalasi (`postinst`)**:
   - Saat `dpkg -i` dijalankan, skrip `postinst` meminta pengguna memasukkan IP Server NOC secara interaktif melalui `/dev/tty`.
   - Konfigurasi disimpan ke `/etc/osi-agent/server_ip.txt`.
   - Memuat ulang daemon `systemctl daemon-reload` dan mengaktifkan service `systemctl enable --now osi-agent.service`.

### 10.3 Engine Auto-Update Atomic (`updater/main.go`)

```
[ Master Server Releases New Version ]
                 |
[ Agen Menerima Sinyal Auto-Update ]
                 |
[ Updater Engine (updater.exe) Mengunduh Biner ]
                 |
Verifikasi SHA256 Checksum & Hash Biner
                 |
Hentikan Service Agen (sc stop / systemctl stop)
                 |
Ganti Biner Lama dengan Biner Baru secara Atomic
                 |
Nyalakan Kembali Service (sc start / systemctl start)
```

---

## 11. Temuan Audit, Kerentanan & Rekomendasi Perbaikan

Berdasarkan analisis mendalam terhadap kode sumber dan arsitektur agen, berikut adalah temuan teknis beserta rekomendasi hardening:

### 11.1 Temuan Keamanan (Security Audit Findings)

> [!WARNING]
> **1. Fallback Hardcoded Security Key**
> - **Lokasi**: [agent/main.go:L188](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/agent/main.go#L188), [linux_agent/main.go:L80](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/linux_agent/main.go#L80).
> - **Temuan**: Apabila file `.key` tidak ditemukan, agen menggunakan fallback key statis `SIAP_DISTRIBUSI_SECRET_KEY`.
> - **Rekomendasi**: Hapus fallback statis pada lingkungan produksi. Agen harus menolak booting jika file `.key` yang sah tidak ditemukan di disk.

> [!IMPORTANT]
> **2. Notifikasi Local Socket Tanpa Otentikasi**
> - **Lokasi**: [linux_agent/linux_tray_agent.py:L55](file:///home/it-itsm/AI/incident-analysis/CLIENT_DISTRIBUSI_GO/linux_agent/linux_tray_agent.py#L55).
> - **Temuan**: Port socket local `10001` pada Linux Tray Agent tidak melakukan validasi token. Aplikasi lokal lain pada PC pengguna dapat mengirim payload JSON ke port ini untuk membuka URL browser.
> - **Rekomendasi**: Tambahkan token otentikasi sederhana berbasis file secret lokal pada socket Port `10001`.

> [!NOTE]
> **3. HTTP Ingestion Port Fallback (Port 80)**
> - **Lokasi**: `main.go` (`IngestionPort = 80`).
> - **Temuan**: Penggunaan Port 80 HTTP tanpa TLS dapat menyebabkan data telemetri berpotensi diintip (*eavesdropping*) pada jaringan lokal yang tidak terenkripsi.
> - **Rekomendasi**: Terapkan HTTPS (TLS 1.3) wajib untuk seluruh pengiriman telemetri HTTP fallback.

### 11.2 Temuan Performa & Reliabilitas (Reliability Audit Findings)

> [!TIP]
> **1. Penggunaan Subprocess Command Timeout**
> - **Temuan**: Beberapa eksekusi shell via PowerShell atau Bash pada pengumpulan telemetri tidak menggunakan `exec.CommandContext` dengan timeout ketat. Jika perintah PowerShell menggantung, goroutine dapat tertahan.
> - **Rekomendasi**: Bungkus seluruh panggilan `exec.Command` dengan `context.WithTimeout(ctx, 5*time.Second)`.

---

## 12. Kesimpulan

Agen OSI AI (Linux & Windows) versi **2.1.1** telah berhasil dirancang dengan arsitektur cross-platform yang sangat solid, responsif, dan kaya akan fitur observabilitas enterprise. Keberadaan mekanisme **Watchdog Self-Healing**, **Registri Idempotensi Terpersistensi**, **NATS JetStream Ring-Buffer Offline Queue**, serta **V8 CDP Browser Forensics** menjadikan agen ini memiliki ketahanan tinggi (*high availability*) serta latensi remediasi instan (< 10ms).

Dokumen audit ini menyajikan seluruh inventarisasi dan bedah teknis dari agen untuk dijadikan panduan resmi tata kelola dan pemeliharaan sistem.

---
*Laporan Audit Selesai Di-generate.*
