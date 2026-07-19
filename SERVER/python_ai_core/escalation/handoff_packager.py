"""
OSI AI Ops — Contextual Human Hand-off Packager
Sprint 2: Gap 4

Alur:
  1. EscalationEngine memanggil HandoffPackager.build() saat Level 3 escalation
  2. Packager mengumpulkan: ERG nodes, hipotesis, aksi yang sudah dicoba, rollback history
  3. Format ringkas dikirim ke Telegram NOC agar teknisi tidak perlu mulai dari nol
"""

import json
import logging
from typing import Optional

logger = logging.getLogger("HANDOFF_PACKAGER")


class HandoffPackager:
    """
    Mengemas konteks investigasi AI menjadi satu paket hand-off
    yang informatif untuk NOC Engineer.
    """

    def __init__(self, db_conn=None):
        self.db = db_conn

    def build(self, incident_id: int) -> dict:
        """
        Kumpulkan semua bukti investigasi AI dan kembalikan sebagai dict.
        """
        package = {
            "incident_id":       incident_id,
            "summary":           self._get_incident_summary(incident_id),
            "device":            self._get_device(incident_id),
            "severity":          self._get_severity(incident_id),
            "erg_nodes":         self._get_erg_nodes(incident_id),
            "hypotheses_tested": self._get_hypotheses(incident_id),
            "actions_attempted": self._get_actions_attempted(incident_id),
            "rollbacks":         self._get_rollbacks(incident_id),
            "dry_run_blocks":    self._get_dry_run_blocks(incident_id),
            "recommendation":    (
                "AI telah mencapai batas kemampuan otonom. "
                "Investigasi manual oleh NOC Engineer diperlukan."
            ),
        }
        logger.info(
            "[HANDOFF] Package built for incident=%d | nodes=%d hypotheses=%d actions=%d",
            incident_id,
            len(package["erg_nodes"]),
            len(package["hypotheses_tested"]),
            len(package["actions_attempted"]),
        )
        return package

    def to_telegram_message(self, package: dict) -> str:
        """Format package menjadi pesan Telegram yang informatif."""
        inc      = package["incident_id"]
        summ     = package["summary"] or "Tidak ada deskripsi."
        device   = package.get("device", "Unknown")
        severity = package.get("severity", "UNKNOWN")
        n_hypo   = len(package["hypotheses_tested"])
        n_acts   = len(package["actions_attempted"])
        n_rolls  = len(package["rollbacks"])
        n_blocks = len(package["dry_run_blocks"])

        # Ringkasan hipotesis (maks 3)
        hypo_lines = ""
        for i, h in enumerate(package["hypotheses_tested"]):
            verdict = h.get("verdict", "ACTIVE")
            hypo_text = h.get('hypothesis', 'N/A')
            reason = h.get('reason', '')
            
            if verdict == "REJECTED":
                hypo_lines += f"  ❌ Hypothesis {i+1} Rejected: {reason or 'Evidence not supporting'}\n"
            elif verdict == "CONFIRMED":
                hypo_lines += f"  ✅ Hypothesis {i+1} Confirmed: {reason or 'Evidence found'}\n"
            else:
                hypo_lines += f"  🔍 Hypothesis {i+1} Active: {hypo_text}\n"
                
        if not hypo_lines:
            hypo_lines = "  • Tidak ada hipotesis yang dicatat (Mungkin langsung eskalasi)\n"

        # Ringkasan aksi (maks 3)
        action_lines = ""
        for a in package["actions_attempted"][:3]:
            st_icon = "✅" if a.get("status") == "SUCCESS" else "❌"
            action_lines += f"  {st_icon} {a.get('action', 'N/A')}\n"
        if not action_lines:
            action_lines = "  • Tidak ada aksi yang dieksekusi\n"

        msg = (
            f"🚨 *ESKALASI AI → NOC ENGINEER*\n"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"🔴 Incident ID : `{inc}`\n"
            f"💻 Device      : `{device}`\n"
            f"⚠️ Severity    : `{severity}`\n"
            f"📋 *Deskripsi  :* {summ}\n\n"
            f"🧠 *Investigasi AI (Summary):*\n"
            f"• Hipotesis diuji      : `{n_hypo}`\n"
            f"• Aksi dieksekusi      : `{n_acts}`\n"
            f"• Rollback terjadi     : `{n_rolls}`\n"
            f"• Diblokir Dry-Run     : `{n_blocks}`\n\n"
            f"🔬 *Hipotesis:*\n{hypo_lines}"
            f"🔧 *Aksi Terakhir:*\n{action_lines}"
            f"━━━━━━━━━━━━━━━━━━━━━━\n"
            f"⚠️ *AI tidak dapat menyelesaikan insiden ini.*\n"
            f"👤 Silakan ambil alih dari *dashboard NOC*.\n"
            f"📊 Detail lengkap tersedia di ERG Viewer."
        )
        return msg

    # ─────────────────────────────────────────────────────────────
    # DATA COLLECTORS
    # ─────────────────────────────────────────────────────────────

    def _get_incident_summary(self, incident_id: int) -> Optional[str]:
        return self._query_one(
            "SELECT COALESCE(raw_data->>'description', raw_data->>'message', 'No description') "
            "FROM incidents WHERE incident_id = %s",
            (incident_id,),
        )

    def _get_device(self, incident_id: int) -> Optional[str]:
        return self._query_one(
            "SELECT device_name FROM incidents WHERE incident_id = %s",
            (incident_id,),
        )

    def _get_severity(self, incident_id: int) -> Optional[str]:
        return self._query_one(
            "SELECT COALESCE(raw_data->>'severity', 'UNKNOWN') FROM incidents WHERE incident_id = %s",
            (incident_id,),
        )

    def _get_erg_nodes(self, incident_id: int) -> list:
        return self._query_all(
            "SELECT node_type, node_label FROM erg_nodes WHERE incident_id = %s LIMIT 15",
            (incident_id,),
            lambda r: {"type": r[0], "label": r[1]},
        )

    def _get_hypotheses(self, incident_id: int) -> list:
        # Fallback query menggunakan ai_reflection_logs karena tabel erg_hypotheses belum dibuat sepenuhnya
        return self._query_all(
            """
            SELECT first_hypothesis, 'REJECTED', 'Failed verification' 
            FROM ai_reflection_logs WHERE incident_id = %s AND first_hypothesis IS NOT NULL
            UNION ALL
            SELECT second_hypothesis, 'ACTIVE', '' 
            FROM ai_reflection_logs WHERE incident_id = %s AND second_hypothesis IS NOT NULL
            LIMIT 3
            """,
            (incident_id, incident_id),
            lambda r: {"hypothesis": r[0], "verdict": r[1], "reason": r[2]},
        )

    def _get_actions_attempted(self, incident_id: int) -> list:
        return self._query_all(
            """
            SELECT action, status FROM remediation_logs
            WHERE incident_id = %s ORDER BY created_at DESC LIMIT 10
            """,
            (incident_id,),
            lambda r: {"action": r[0], "status": r[1]},
        )

    def _get_rollbacks(self, incident_id: int) -> list:
        return self._query_all(
            """
            SELECT original_action, created_at FROM rollback_logs
            WHERE incident_id = %s ORDER BY created_at DESC LIMIT 5
            """,
            (incident_id,),
            lambda r: {"action": r[0], "at": str(r[1])},
        )

    def _get_dry_run_blocks(self, incident_id: int) -> list:
        """Ambil aksi yang diblokir DryRunGate karena risk CRITICAL."""
        return self._query_all(
            """
            SELECT action, result->>'reason', created_at FROM dry_run_logs
            WHERE device = (
                SELECT device_name FROM incidents WHERE incident_id = %s LIMIT 1
            ) AND result->>'risk_level' = 'CRITICAL'
            ORDER BY created_at DESC LIMIT 5
            """,
            (incident_id,),
            lambda r: {"action": r[0], "reason": r[1], "at": str(r[2])},
        )

    # ─────────────────────────────────────────────────────────────
    # HELPERS
    # ─────────────────────────────────────────────────────────────

    def _query_one(self, sql: str, params: tuple):
        if not self.db:
            return None
        try:
            with self.db.cursor() as cur:
                cur.execute(sql, params)
                row = cur.fetchone()
                return row[0] if row else None
        except Exception as e:
            logger.warning("[HANDOFF] Query error: %s", e)
            return None

    def _query_all(self, sql: str, params: tuple, mapper) -> list:
        if not self.db:
            return list()
        try:
            with self.db.cursor() as cur:
                cur.execute(sql, params)
                return [mapper(r) for r in cur.fetchall()]
        except Exception as e:
            logger.warning("[HANDOFF] Query error: %s", e)
            return list()
