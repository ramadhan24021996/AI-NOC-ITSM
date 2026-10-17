"""
SERVER.jarvis.remediation.one_click_remediator — One-Click Voice Auto-Remediation Engine
========================================================================================
Tahap 3.1 — Production-Ready AI NOC Voice Remediation

Memetakan indikator insiden live ke SOP remediasi otomatis, mengelola pending state per sesi,
dan mengeksekusi tindakan perbaikan secara instan ketika pengguna memberikan konfirmasi suara
(misal: "Ya, eksekusi", "Ya, jalankan", "Jalankan SOP").
"""
import logging
import re
from typing import Dict, Any, Optional

logger = logging.getLogger("jarvis.remediation.one_click")

# Production SOP Remediation Mapping
INDICATOR_SOP_MAP = [
    {
        "pattern": r"(?:printer|spooler|print test|print queue)",
        "action_code": "restart spooler",
        "sop_name": "SOP Pemulihan Print Spooler Kasir & Fleets",
        "description": "Restart service spooler printer & bersihkan antrean cetak yang macet.",
    },
    {
        "pattern": r"(?:redis|memory high|ram high|memory leak)",
        "action_code": "restart redis",
        "sop_name": "SOP Restrukturisasi & Flush Cache Redis",
        "description": "Restart service Redis & bebaskan alokasi memori ram.",
    },
    {
        "pattern": r"(?:postgres|database|db lock|postgresql)",
        "action_code": "restart postgresql",
        "sop_name": "SOP Recovery Koneksi Database PostgreSQL",
        "description": "Refresh pool koneksi & restart service database.",
    },
    {
        "pattern": r"(?:network|link down|isp|ping failed|rtt high)",
        "action_code": "failover isp",
        "sop_name": "SOP Failover Link Jaringan ke Backup ISP",
        "description": "Pindahkan rute gateway utama ke jalur cadangan ISP.",
    },
    {
        "pattern": r"(?:cpu high|load high|cpu usage)",
        "action_code": "restart service",
        "sop_name": "SOP Penanganan Lonjakan CPU Process",
        "description": "Restart service agent & optimasi thread CPU.",
    },
]


class JarvisOneClickRemediator:
    """
    Mesin auto-remediasi suara satu-klik.
    Menyarankan SOP yang relevan berdasarkan bukti insiden live dan mengeksekusi
    begitu konfirmasi suara diterima dari operator.
    """

    def __init__(self):
        self._pending_actions: Dict[str, Dict[str, Any]] = {}

    def get_recommendation(self, incident_data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Menganalisis data insiden live dan mengembalikan rekomendasi SOP jika ada pencocokan.
        """
        if not incident_data:
            return None

        evidence = str(incident_data.get("evidence") or incident_data.get("flag") or incident_data.get("title", "")).lower()
        device = incident_data.get("device_name") or incident_data.get("agent") or "Global"
        inc_id = incident_data.get("incident_id") or incident_data.get("id")

        for sop in INDICATOR_SOP_MAP:
            if re.search(sop["pattern"], evidence, re.IGNORECASE):
                rec = {
                    "incident_id": inc_id,
                    "action_code": sop["action_code"],
                    "sop_name": sop["sop_name"],
                    "description": sop["description"],
                    "device": device,
                    "prompt_text": (
                        f"\n\n💡 REKOMENDASI AUTO-REMEDIASI AI:\n"
                        f"• SOP Disarankan: {sop['sop_name']} (`{sop['action_code']}`)\n"
                        f"• Perangkat     : {device}\n"
                        f"• Deskripsi     : {sop['description']}\n\n"
                        f"❓ Ucapkan *\"Ya, eksekusi\"* atau *\"Jalankan SOP\"* untuk mengeksekusi tindakan ini secara langsung."
                    ),
                }
                logger.info(f"[OneClickRemediator] Found matching SOP '{sop['sop_name']}' for INC-{inc_id}")
                return rec

        return None

    def set_pending_action(self, session_id: str, recommendation: Dict[str, Any]):
        """Menyimpan pending action per sesi percakapan."""
        if session_id and recommendation:
            self._pending_actions[session_id] = recommendation
            logger.info(f"[OneClickRemediator] Set pending action for session={session_id}: {recommendation['action_code']}")

    def get_pending_action(self, session_id: str) -> Optional[Dict[str, Any]]:
        """Mengambil pending action untuk sesi tertentu."""
        return self._pending_actions.get(session_id)

    def clear_pending_action(self, session_id: str):
        """Menghapus pending action setelah dieksekusi atau dibatalkan."""
        if session_id in self._pending_actions:
            del self._pending_actions[session_id]
            logger.info(f"[OneClickRemediator] Cleared pending action for session={session_id}")

    def is_confirmation_query(self, query_text: str) -> bool:
        """Memeriksa apakah kata-kata pengguna mengandung konfirmasi eksekusi."""
        q = query_text.lower().strip()
        confirm_keywords = [
            "eksekusi jalankan", "eksekusi insiden", "ya eksekusi", "ya jalankan",
            "jalankan sop", "eksekusi sop", "setuju eksekusi", "oke eksekusi",
            "jalankan remedi", "eksekusi sekarang", "eksekusi tindakan", "eksekusi perbaikan",
            "lakukan eksekusi", "eksekusi aksi", "ya lakukan", "eksekusi", "ya", "setuju", "jalankan"
        ]
        return any(k in q for k in confirm_keywords)
