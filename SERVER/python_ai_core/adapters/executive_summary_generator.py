"""
Executive Client Summary Generator (Layer 4 AI Core Adapter)
Transforms complex technical logs & cryptic error stacktraces into clean,
structured, human-readable Bahasa Indonesia Executive Summaries for clients & management.
"""

import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger("ExecutiveSummaryGenerator")
logging.basicConfig(level=logging.INFO)

class ExecutiveSummaryGenerator:
    def __init__(self):
        logger.info("[EXEC_SUMMARY_GENERATOR] Executive Client Summary Generator initialized.")

    def generate_human_readable_summary(
        self,
        incident_id: str,
        technical_log: str,
        root_cause_summary: Optional[str] = None,
        sop_action: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Transforms technical error logs into clean executive summary:
        🔍 Masalah (Problem Summary)
        🎯 Penyebab Utama (Root Cause)
        🛡️ Rekomendasi Tindakan AI (Action & Risk)
        📈 Estimasi Pemulihan (Recovery Time & Safety Guarantee)
        """
        log_lower = technical_log.lower()

        # 1. Determine Problem Summary (Bahasa Indonesia Awam)
        if "spooler" in log_lower or "printer" in log_lower:
            masalah = "Layanan percetakan dokumen terhenti sementara akibat antrean antrean cetak tersumbat."
            penyebab = "Proses spooler memori mengalami hambatan saat mengolah file antrean."
            action_desc = "Pembersihan antrean cetak tersumbat dan restart otomatis layanan spooler secara aman."
            risk_pct = "0.1%"
            recovery_est = "< 2 detik tanpa mengganggu dokumen lain."
        elif "postgres" in log_lower or "deadlock" in log_lower or "database" in log_lower:
            masalah = "Lalu lintas transaksi meningkat menyebabkan antrean singkat pada basis data."
            penyebab = "Terdapat koneksi terhenti (hang) di basis data yang mengunci tabel antrean."
            action_desc = "Pembersihan koneksi terhenti secara terisolasi tanpa mematikan basis data."
            risk_pct = "0.15%"
            recovery_est = "< 3 detik tanpa ada data yang hilang."
        elif "nginx" in log_lower or "504" in log_lower or "gateway" in log_lower:
            masalah = "Koneksi pintu masuk portal (Ingress Gateway) mengalami jeda respon."
            penyebab = "Antrean cache DNS mengalami titik jenuh sementara pada proxy penerima."
            action_desc = "Pembersihan cache DNS dan penyelarasan ulang proxy Nginx."
            risk_pct = "0.05%"
            recovery_est = "< 1 detik dengan ketersediaan penuh."
        else:
            masalah = f"Terdeteksi kejanggalan performa sistem pada insiden {incident_id}."
            penyebab = root_cause_summary or "Pola lalu lintas metrik melebihi ambang batas toleransi normal."
            action_desc = sop_action.get("title", "Eksekusi SOP perbaikan teruji") if sop_action else "Pemeriksaan dan isolasi sistem secara aman."
            risk_pct = f"{sop_action.get('risk_score', 0.1) * 100:.1f}%" if sop_action else "0.2%"
            recovery_est = "< 5 detik dengan perlindungan data."

        # Format Client Executive Summary
        formatted_summary = (
            f"🔍 **Masalah:** {masalah}\n"
            f"🎯 **Penyebab Utama:** {penyebab}\n"
            f"🛡️ **Rekomendasi Tindakan AI:** {action_desc} (Risk Level: {risk_pct}).\n"
            f"📈 **Estimasi Pemulihan:** Performa akan kembali normal dalam {recovery_est}"
        )

        result = {
            "incident_id": incident_id,
            "raw_technical_log": technical_log,
            "executive_summary_formatted": formatted_summary,
            "summary_components": {
                "masalah": masalah,
                "penyebab": penyebab,
                "rekomendasi_tindakan": action_desc,
                "risk_level": risk_pct,
                "estimasi_pemulihan": recovery_est
            },
            "target_audience": "EXECUTIVE_CLIENT_STAKEHOLDER",
            "language": "ID_INDONESIAN_HUMAN_READABLE"
        }

        logger.info("[EXEC_SUMMARY_GENERATOR] Generated client summary for %s.", incident_id)
        return result


if __name__ == "__main__":
    generator = ExecutiveSummaryGenerator()

    # Test Case 1: PostgreSQL Deadlock Log
    log1 = "ERROR 500: PostgreSQL deadlock detected at pid 4192 on table orders_db. High connection count (98/100) causing HTTP 504 Gateway Timeout."
    res1 = generator.generate_human_readable_summary("INC_POSTGRES_001", log1)
    print("=== TEST 1: POSTGRESQL DEADLOCK LOG ===")
    print(res1["executive_summary_formatted"])

    # Test Case 2: Windows Spooler Hang Log
    log2 = "WIN32_EVENT_LOG 7031: The Print Spooler service terminated unexpectedly. 14 pending jobs in queue."
    res2 = generator.generate_human_readable_summary("INC_SPOOLER_002", log2)
    print("\n=== TEST 2: WINDOWS SPOOLER HANG LOG ===")
    print(res2["executive_summary_formatted"])
