# OSI Agent — Browser Extension

Ekstensi Chrome/Edge perusahaan yang mengirimkan metrik aktivitas tab browser secara real-time ke **OSI Local Agent** yang berjalan di komputer pengguna.

## Arsitektur Komunikasi

```
[Tab Browser Aktif]
      |
      | POST JSON (setiap 10 detik)
      ▼
[http://127.0.0.1:10001/ext-telemetry]  ← HTTP Server di dalam Agent Go
      |
      | Agent relay menggunakan IP Server dari server_ip.txt
      ▼
[http://<MASTER_IP>:80/browser-events]  ← Dashboard AIOps
```

**Keunggulan pendekatan ini vs scraping SQLite:**
- ✅ Akurasi durasi aktif tab (Active Time) yang sesungguhnya
- ✅ Tidak ada risiko database browser corruption
- ✅ Tidak diblokir oleh Antivirus/EDR
- ✅ Ekstensi tidak perlu tahu IP Server (Agent yang mengurus)
- ✅ Dapat di-deploy secara paksa via Enterprise Policy (tanpa interaksi user)

---

## Cara Pengembangan

### 1. Load di Chrome/Edge (Mode Developer)
1. Buka `chrome://extensions` atau `edge://extensions`
2. Aktifkan **Developer Mode** (pojok kanan atas)
3. Klik **Load unpacked** → pilih folder `browser_extension/`
4. Pastikan Local Agent Go sudah berjalan di komputer

### 2. Publish ke Chrome Web Store (Private)
1. Zip seluruh isi folder `browser_extension/` (bukan foldernya)
2. Buka [Chrome Web Store Developer Dashboard](https://chrome.google.com/webstore/devconsole)
3. Upload sebagai **Private/Unlisted** extension
4. Salin **Extension ID** yang diberikan oleh Web Store
5. Ganti konstanta `ExtChromeID` di:
   - `linux_agent/browser_ext_server.go`
   - `agent/browser_ext_server.go`

### 3. Auto-Deploy via Enterprise Policy
Setelah Extension ID diisi, cukup jalankan agent sebagai:
- **Linux**: `sudo` (root) — agent akan otomatis menulis file JSON ke `/etc/opt/chrome/policies/managed/`
- **Windows**: Run as Administrator — agent akan otomatis menulis ke Windows Registry HKLM

---

## Files

| File | Keterangan |
|------|-----------|
| `manifest.json` | Konfigurasi ekstensi (Manifest V3) |
| `background.js` | Service Worker: tracking tab & kirim ke agent |
| `popup.html` | UI saat icon ekstensi diklik |
| `popup.js` | Cek status koneksi ke local agent |
