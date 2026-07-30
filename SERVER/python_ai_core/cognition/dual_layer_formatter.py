"""
Dual-Layer Operator SOP Formatter (cognition/dual_layer_formatter.py)

Synthesizes AI Incident Analysis & Remediation Plans into Dual-Layer Readable Formats:
  - Layer 1: Ringkasan Bahasa Awam NOC (Operator-Friendly Summary in 30 Seconds)
  - Layer 2: Blueprint Teknis Deep RCA (Senior Engineer Detailed 5-Section SOP)
"""

import logging
import json
import os
import sys
import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s — %(message)s')
logger = logging.getLogger("DUAL_LAYER_FORMATTER")

class DualLayerSOPFormatter:
    def format_remediation_payload(self, incident_data: dict) -> dict:
        """Formats raw incident RCA and remediation data into Dual-Layer Readable Output."""
        logger.info(f"✨ [FORMATTER] Generating Dual-Layer Readable SOP for '{incident_data.get('incident_id', 'INC-NOC')}'...")

        title = incident_data.get("title", "Penanganan Anomali Sistem")
        symptoms = incident_data.get("symptoms", "Gejala penurunan performa ditemukan.")
        root_cause = incident_data.get("root_cause", "Terjadi penumpukan beban antrean proses.")
        command_script = incident_data.get("command", "systemctl restart application_service")

        # Layer 1: Bahasa Awam NOC (Ringkas & Mudah Dipahami Dalam 30 Detik)
        layman_summary = (
            f"📌 **Ringkasan Cepat (30 Detik)**:\n"
            f"Sistem mendeteksi masalah pada **{title}**. "
            f"Penyebab utamanya adalah **{root_cause}**. "
            f"Lakukan langkah remedi cepat dengan menekan tombol eksekusi skrip di bawah atau hubungi tim teknis jika masalah berlanjut dalam 5 menit."
        )

        # Layer 2: Detail Teknis Terstruktur 5-Seksi (Senior Engineer & Audit)
        technical_blueprint = f"""# 📄 SOP PENANGANAN TERSTRUKTUR 5-SEKSI: {title.upper()}

### 1. 📌 Ringkasan Kasus & Gejala (Operator Summary)
- **ID Insiden**: {incident_data.get('incident_id', 'INC-AUTOGEN')}
- **Gejala Terdeteksi**: {symptoms}
- **Tingkat Risiko**: {incident_data.get('risk_level', 'MEDIUM')}

### 2. 🔍 Analisis Akar Masalah (Root Cause Deep RCA)
- **Akar Masalah Utama**: {root_cause}
- **Dampak Bisnis (Blast Radius)**: {incident_data.get('impact', 'Potensi keterlambatan transaksi kasir Subang/Store.')}

### 3. ⚡ Panduan Penanganan 3-Tahap (MTTR < 5m)
- **Tahap 1: Diagnosa Cepat (60s)** ➔ Verifikasi status port & konsumsi CPU/RAM.
- **Tahap 2: Eksekusi Remedi (Workaround)** ➔ Jalankan skrip pemulihan di bawah ini.
- **Tahap 3: Verifikasi Pemulihan** ➔ Pastikan status service berubah menjadi ONLINE.

### 4. 💻 Skrip Command Eksekusi Aman (Executable Script)
```bash
# Executable Script (1-Click Copy)
{command_script}
```

### 5. 📊 Kriteria Pemulihan Metrik & Rollback
- **Kriteria Sukses**: Status Service = `ONLINE`, Latensi < 100ms, Error Rate = 0%.
- **Prosedur Rollback**: Jika terjadi kendala dalam 3 menit, jalankan skrip fallback `rules.pkl`.
"""

        return {
            "layman_summary": layman_summary,
            "technical_blueprint": technical_blueprint,
            "formatted_at": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        }

if __name__ == "__main__":
    formatter = DualLayerSOPFormatter()
    sample = {
        "incident_id": "INC-2026-SUBANG-04",
        "title": "Spooler Printer Deadlock Subang",
        "symptoms": "Antrean cetak struk kasir Subang tertahan.",
        "root_cause": "Print queue buffer jam akibat lonjakan transaksi.",
        "command": "net stop spooler && del /q /f %systemroot%\\System32\\Spool\\Printers\\* && net start spooler",
        "risk_level": "LOW",
        "impact": "Struk kasir tertunda cetak 2 menit."
    }
    res = formatter.format_remediation_payload(sample)
    print("=== DUAL-LAYER FORMATTER RESULT ===")
    print("--- LAYMAN SUMMARY ---")
    print(res["layman_summary"])
    print("\n--- TECHNICAL BLUEPRINT ---")
    print(res["technical_blueprint"])
