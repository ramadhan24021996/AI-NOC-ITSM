# 📋 Implementation Plan - Smart Incident Stream Menu (`Diagnostics & Comm`)

Penambahan menu baru **Smart Incident Stream** (`#p-smart_stream`) di bawah kelompok menu **Diagnostics & Comm** pada sidebar dashboard NOC IT AI Command Center v3.0, yang menyajikan aliran insiden terstruktur bahasa manusia secara *real-time* dari telemetri terproses.

---

## User Review Required

> [!IMPORTANT]
> - Menu baru **Smart Incident Stream** akan ditempatkan pada sidebar di bawah kategori **Diagnostics & Comm** (sejajar dengan *Live Logs*, *NATS Subjects*, *Live Chat*).
> - Seluruh data yang ditampilkan diambil langsung dari API live terproses `/api/ai_decision_logs` dan WebSocket event stream, tanpa mengubah struktur database yang ada.

---

## Proposed Changes

### Dashboard Navigation & Sidebar (`portal/templates/index.html`)

#### [MODIFY] [index.html](file:///home/it-itsm/AI/incident-analysis/portal/templates/index.html)
- **Sidebar Navigation**: Menambahkan tombol menu `<div class="nav-item" data-panel="smart_stream" onclick="Nav.go('smart_stream',this)">` di bawah grup **Diagnostics & Comm**.
- **Panel HTML (`#p-smart_stream`)**: Membuat container panel independen yang memuat:
  1. Executive Summary Cards (Insiden Aktif, Auto-Resolved, Waiting Approval, Confidence Avg).
  2. Search & Filter Bar (Nama PC Online/Offline, Status, Severity).
  3. Stream Feed Cards Interaktif (Kartu insiden bahasa manusia + tombol aksi HITL 1-klik).
- **JavaScript `Panels.smart_stream`**:
  - Implementasi handler `Panels.smart_stream.load()` dan `Panels.smart_stream.render()`.
  - Integrasi dengan WebSocket `Bus.on('log:new')` dan API `/api/ai_decision_logs` untuk pembaruan real-time.
- **RBAC Updates**: Menambahkan `'smart_stream'` pada `defaultAllowedPanels` untuk peran `superadmin`, `admin`, `noc_engineering`, dan `operator`.

---

## Verification Plan

### Automated Tests
- Menjalankan audit struktur HTML DOM untuk memastikan 39 panel (termasuk `#p-smart_stream`) tertutup dan seimbang secara sempurna:
  ```bash
  python3 -c "..."
  ```
- Menjalankan kompilasi biner Go GoOS Linux:
  ```bash
  CGO_ENABLED=0 GOOS=linux go build -o dashboard_server ./portal
  ```

### Manual Verification
- Hard Refresh browser (**Ctrl + F5**).
- Mengeklik menu **Smart Incident Stream** di bawah **Diagnostics & Comm**.
- Verifikasi pencarian nama PC (terdaftar online/offline) dan pembaruan insiden terstruktur bahasa manusia.
