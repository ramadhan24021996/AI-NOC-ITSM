# 🎨 BLUEPRINT REKOMENDASI DESAIN, ANALISIS, & PENERAPAN HUMAN-CENTRIC UI/UX
> **Sistem:** Incident Analysis Platform — Autonomous AI Ops & Proactive Root Cause Analysis  
> **Fokus Utama:** Transformasi Tampilan Dashboard & Rekomendasi Penanganan Insiden Agar Mudah Dipahami Manusia (*Human-Readable & Actionable AI*)

---

## 🎯 1. ANALISIS KEBUTUHAN: MENGAPA PERLU PENDEKATAN HUMAN-CENTRIC?

Operator L1/L2 NOC dan Tim IT Support sering kali mengalami kendala saat membaca dashboard AI Ops konvensional karena:
1. **Bahasa Terlalu Teknis/Mesin:** Istilah seperti `UNRECOGNIZED_TELEMETRY_SIGNATURE`, `MISSING_CONTEXT`, atau `TEMPORAL_HISTORY_COMPLETE` membingungkan operator non-spesialis.
2. **Rekomendasi Terlalu Abstrak:** Petunjuk statis seperti *"Review system log"* tidak memberikan langkah konkret atau tombol eksekusi cepat.
3. **Kelelahan Informasi (*Cognitive Overload*):** Banyaknya data log dan variabel tanpa hierarki visual yang jelas memperlambat waktu pengambilan keputusan (*MTTR*).

---

## 💡 2. 5 PILAR DESAIN & PENERAPAN KESISTEM (HUMAN-CENTRIC DESIGN)

```
┌─────────────────────────────────────────────────────────────────────────┐
│                      5 PILAR HUMAN-CENTRIC AI OPS                      │
├──────────────────────────┬──────────────────────┬───────────────────────┤
│ 1. Narrative Diagnosis   │ 2. Interactive HITL  │ 3. Human AI Co-Pilot  │
│    (Bahasa Manusia Jelas)│    (1-Click Action)  │    (Saran Balasan)    │
├──────────────────────────┴──────────────────────┴───────────────────────┤
│ 4. Traffic Light Hierarchy (Merah / Kuning / Hijau / Biru)             │
│ 5. Dual-View Perspective (Tampilan Operator vs Manajerial)            │
└─────────────────────────────────────────────────────────────────────────┘
```

---

### PILAR 1: Narrative Storytelling Diagnosis (Penjelasan Bahasa Manusia)
Mengubah diagnostik mesin menjadi 3 pertanyaan mendasar yang selalu ditanyakan manusia saat terjadi masalah:

| Komponen Diagnostik | Bahasa Mesin (Lama) | Bahasa Manusia (Baru - Human Narrative) |
|---|---|---|
| **Apa Masalahnya?** | `UNRECOGNIZED_TELEMETRY_SIGNATURE` | 🔴 **Layanan Printer Spooler di PC-MKT-NUC Macet (Tidak Merespons)** |
| **Mengapa Terjadi?** | `Transient Hardware Fault + Config Drift` | 🔍 **Penyebab:** Penumpukan 45 dokumen cetak bermasalah (*corrupted print queue*) sejak pukul 14:15. |
| **Apa Dampaknya?** | `Unknown deviation in metric baseline` | ⚠️ **Dampak:** User Marketing tidak dapat mencetak dokumen faktur penjualan. |

---

### PILAR 2: Actionable Remediation Checklist (Kartu Penanganan Interaktif 1-Klik)
Mengubah daftar rekomendasi teks statis menjadi **Kartu Eksekusi Interaktif (HITL Safeguard)**:

```html
<!-- MOCKUP KARTU REKOMENDASI INTERAKTIF -->
<div class="remediation-card">
  <h4>🛠️ Rekomendasi Penanganan Terpandu (Guided Recovery Checklist)</h4>
  
  <!-- Langkah 1: Eksekusi Otomatis 1-Klik -->
  <div class="step-item active">
    <div class="step-num">1</div>
    <div class="step-info">
      <b>[Rekomendasi Utama] Restart Service Print Spooler</b>
      <p>Sistem AI akan merestart service Spooler dan membersihkan antrean spool tanpa reboot PC.</p>
    </div>
    <button class="btn btn-primary btn-sm">⚡ Eksekusi Sekarang (1-Click HITL)</button>
  </div>

  <!-- Langkah 2: Tindakan Pembersihan lanjutan -->
  <div class="step-item">
    <div class="step-num">2</div>
    <div class="step-info">
      <b>[Opsional] Clear Corrupted Print Buffer</b>
      <p>Menghapus file *.SPL dan *.SHD yang tertahan pada direktori System32/spool/PRINTERS.</p>
    </div>
    <button class="btn btn-outline btn-sm">🧹 Bersihkan Buffer</button>
  </div>

  <!-- Langkah 3: Panduan Manual untuk Operator -->
  <div class="step-item">
    <div class="step-num">3</div>
    <div class="step-info">
      <b>[Panduan Manual] Cek Koneksi Fisik USB / LAN Printer</b>
      <p>Jika langkah 1 & 2 tidak menyelesaikan masalah, minta user memastikan kabel USB printer terpasang erat.</p>
    </div>
  </div>
</div>
```

---

### PILAR 3: Human AI Co-Pilot Widget (Saran Balasan & Komunikasi Operator)
Menyediakan teks balasan siap pakai (*Ready-to-Send Template*) bagi L1 Operator untuk membalas tiket user atau berkoordinasi dengan tim lapangan:

```html
<!-- SARAN BALASAN AI INTERAKTIF -->
<div class="ai-copilot-box">
  <div class="copilot-header">
    <span>💬 <b>AI Co-Pilot:</b> Draft Pesan Respon ke User / Client</span>
    <button class="btn-copy">📋 Salin Teks</button>
  </div>
  <div class="copilot-body">
    "Halo Tim Marketing, kami mendeteksi antrean cetak pada PC-MKT-NUC sedang mengalami kendala. Tim NOC sedang melakukan proses restart layanan printer remote (estimasi 1 menit). Mohon tunggu sejenak sebelum mencoba mencetak kembali."
  </div>
</div>
```

---

### PILAR 4: Traffic Light & Visual Badging (Hierarki Visual yang Jelas)
Menghilangkan istilah status yang membingungkan (`MISSING_CONTEXT`) dan menggantinya dengan lencana indikator kesehatan berwarna:

- 🟢 **NORMAL (Hijau):** `[ CPU: 18% Stable ]` `[ RAM: 4.2 GB / 8 GB ]`
- 🟡 **WARNING (Kuning):** `[ DISK: 85% Full - Perlu Cleanup ]`
- 🔴 **CRITICAL (Merah):** `[ PRINTER SPOOLER: STOPPED ]`
- 🔵 **ACTIVE (Biru):** `[ NETWORK: 1 Gbps Active ]`

---

### PILAR 5: Dual-View Perspective (Tampilan Operator vs Manajerial)

| Fitur | Perspective 1: NOC / L1-L2 Operator | Perspective 2: IT Manager / C-Level |
|---|---|---|
| **Fokus Utama** | Detail Perangkat, PID, Service Name, Logs | Status Kesehatan Cabang, Jumlah Incident Active |
| **Aksi Utama** | Tombol 1-Click Mitigation (Restart/Flush) | Laporan Downtime, SLA Compliance %, ROI Bisnis |
| **Visualisasi** | Terminal Log, Real-time Graph 60 FPS | Topology Map Multi-Site, Summary Ringkasan |

---

## 🚀 3. PLAN IMPLEMENTASI KODE DI PORTAL UI (`portal/templates/index.html`)

### Langkah 1: Update Komponen Template Rekomendasi Insiden
Mengganti fungsi rendering kartu insiden di `index.html` dengan struktur **Guided Remediation Card**:

```javascript
// Contoh Logika JavaScript Rendering Human-Readable Checklist
function renderHumanReadableRemediation(incident) {
  const steps = [
    { title: "Restart Service " + (incident.service || "Spooler"), type: "auto", action: "restart_service" },
    { title: "Bersihkan Cache & Buffer Temporer", type: "auto", action: "clear_cache" },
    { title: "Verifikasi Indikator Fisik & Kabel Jaringan", type: "manual", instructions: "Pastikan kabel LAN/USB terpasang dengan benar." }
  ];

  return steps.map((s, idx) => `
    <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;margin-bottom:6px;background:var(--bg3);border:1px solid var(--bd);border-radius:6px">
      <div style="display:flex;align-items:center;gap:10px">
        <span style="background:var(--blue);color:#fff;border-radius:50%;width:22px;height:22px;display:flex;align-items:center;justify-content:center;font-size:11px;font-weight:bold">${idx+1}</span>
        <div>
          <div style="font-weight:600;font-size:12px;color:var(--txt)">${s.title}</div>
          ${s.instructions ? `<div style="font-size:11px;color:var(--txt2)">${s.instructions}</div>` : ''}
        </div>
      </div>
      ${s.type === 'auto' ? `<button class="btn btn-primary btn-xs" onclick="Panels.hitl.approveAction('${incident.id}', '${s.action}')">⚡ Eksekusi HITL</button>` : '<span class="tag tag-gray">Manual</span>'}
    </div>
  `).join('');
}
```

---

## ✅ KESIMPULAN REKOMENDASI TERAPAN
Dengan menerapkan **5 Pilar Human-Centric UI/UX** di atas:
1. Operator L1/L2 dapat memahami masalah insiden **kurang dari 5 detik** tanpa membaca log mentah.
2. Tindakan mitigasi dapat dilakukan **dalam 1-klik melalui tombol HITL Safeguard**, mencegah kesalahan manual operator.
3. Komunikasi dengan user menjadi instan melalui **AI Co-Pilot Draft Message**.
