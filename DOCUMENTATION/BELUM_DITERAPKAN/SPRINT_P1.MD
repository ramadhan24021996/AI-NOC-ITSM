# SPRINT P1 - Enterprise Telemetry Expansion

## 1. Integrasi Netdata Metrics
Seluruh payload metrik dari Netdata (termasuk webhook) sekarang dilanggan (subscribe) secara langsung oleh AI Supervisor via subjek NATS `telemetry.netdata`.
Metrik ini tidak lagi dianggap sebagai sekadar "alarm", melainkan diproses sebagai bagian dari arsitektur *Enterprise Evidence*.

## 2. Pemetaan ke Evidence Fabric
Modul `evidence_fabric.py` telah diperbarui untuk mengekstraksi dan melakukan *unrolling* terhadap payload berukuran besar. 
Kategori yang kini dikenali secara eksplisit:

### CLIENT PC METRICS:
- CPU, RAM, Disk, Temperature, SMART, Battery, Network, WiFi, Bluetooth, USB, Printer, Scanner, Camera, Audio, COM, GPU, Monitor
- Windows Service, Linux Service, Scheduled Task, Startup Program, Antivirus, Firewall, Windows Update, Linux Package, Process
- Application, Browser, POS Application, Office Application, TMS Application, ERP Application

### NETWORK METRICS:
- SNMP, Switch, Router, VPN (Aktif/Disconnect), Access Point, LLDP, ARP, BGP, DNS, DHCP, Internet, Packet Loss, Latency, Bandwidth

## 3. Struktur Enterprise Evidence
Setiap *record* (baik Client PC maupun Network) secara otomatis dipecah dan dikonversi menjadi instans `EvidenceItem` individual dengan atribut berikut:
- **TraceID:** Dilacak hingga ke ID kejadian NATS / Webhook asli.
- **Timestamp:** Stempel waktu ISO 8601 dipertahankan.
- **Collector:** Digenerate secara dinamis (contoh: `collector-netdata`, `collector-snmp`).
- **Host:** Diambil dari target yang dilaporkan.
- **Source:** Menunjukkan asal asli.
- **Reliability:** Dipetakan otomatis menggunakan `SOURCE_RELIABILITY_MAP` (misalnya: Smart = 0.99, SNMP = 0.95).
- **Freshness:** Mengalami peluruhan (decay) sebesar 50% jika usianya melebihi 1 jam (`STALE`).
- **Confidence:** Dikalkulasi silang secara komprehensif.
- **Quality:** Menyatu ke dalam `EvidenceQuality` yang mengukur kelengkapan (completeness), akurasi waktu, dan validasi lintas (*cross validation*).

AI Supervisor telah direstart dan siap menerima aliran data SPRINT P1.
