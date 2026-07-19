"""
OSI AI Ops — Dry-Run Gate (Simulation Sandbox)
Sprint 2: Gap 3

Alur:
  1. PolicyEngine memanggil DryRunGate.evaluate() sebelum approve aksi HIGH_RISK
  2. DryRunGate menganalisis Blast Radius dari World Model (fleet_devices DB)
  3. Jika risk CRITICAL → return HITL_REQUIRED, bukan eksekusi langsung
  4. Semua evaluasi dicatat ke dry_run_logs untuk audit & learning
"""

import json
import logging
from typing import Optional

logger = logging.getLogger("DRY_RUN_GATE")

# Matriks Risiko Aksi Dasar
ACTION_RISK_MATRIX = {
    "PING": "LOW",
    "SHOW_ROUTE": "LOW",
    "GET_STATUS": "LOW",
    "FLUSH_DNS": "LOW",
    "RESTART_SERVICE": "MEDIUM",
    "CLEAR_SPOOLER": "MEDIUM",
    "KILL_PROCESS": "MEDIUM",
    "REBOOT_HOST": "HIGH",
    "DISABLE_INTERFACE": "HIGH",
    "CMD": "HIGH",
    "POWERSHELL": "HIGH",
    "RUNCOMMAND": "HIGH",
    "FAILOVER_ROUTE": "CRITICAL",
    "ISOLATE_DEVICE": "CRITICAL",
    "BLOCK_IP": "CRITICAL",
    "FIREWALL_CHANGE": "CRITICAL",
}

# Bobot numerik untuk kalkulasi
RISK_WEIGHTS = {
    "LOW": 1,
    "MEDIUM": 2,
    "HIGH": 3,
    "CRITICAL": 5,
}

class DryRunGate:
    """
    Simulation Sandbox untuk memvalidasi dampak aksi AI sebelum eksekusi nyata.
    Menggantikan eksekusi langsung dengan analisis Blast Radius berbasis DB.
    """

    def __init__(self, db_conn=None):
        self.db = db_conn

    def evaluate(self, action: str, device: str, params: dict) -> dict:
        """
        Evaluasi dampak aksi sebelum eksekusi.
        Returns:
            {
                "approved":   bool,
                "risk_level": "LOW" | "MEDIUM" | "HIGH" | "CRITICAL",
                "affected":   list[str],
                "reason":     str,
                "dry_run_id": str,
            }
        """
        base_risk = ACTION_RISK_MATRIX.get(action.upper(), "HIGH")
        
        # Non-destructive actions langsung diapprove
        if base_risk == "LOW":
            result = {
                "approved":   True,
                "risk_level": "LOW",
                "affected":   [],
                "reason":     f"Action '{action}' is a LOW risk operation. Auto-approved.",
            }
            self._log(action, device, result)
            return result

        # Analisis Business Criticality & Blast Radius
        device_criticality = self._get_device_criticality(device)
        affected = self._get_affected_devices(device)
        
        final_risk = self._calculate_final_risk(base_risk, device_criticality, len(affected), action)

        result = {
            "approved":   final_risk["level"] not in ("CRITICAL", "HIGH"),
            "risk_level": final_risk["level"],
            "affected":   affected,
            "reason":     final_risk["reason"],
        }

        logger.info(
            "[DRY-RUN] action=%s device=%s final_risk=%s approved=%s affected=%d",
            action, device, final_risk["level"], result["approved"], len(affected)
        )

        self._log(action, device, result)
        return result

    # ─────────────────────────────────────────────────────────────
    # BLAST RADIUS ANALYSIS
    # ─────────────────────────────────────────────────────────────

    def _get_affected_devices(self, device: str) -> list:
        """
        Temukan perangkat lain yang berbagi gateway/switch dengan device target.
        Perangkat yang berada di segmen jaringan yang sama dianggap terdampak
        jika target device dimatikan/di-restart.
        """
        if not self.db:
            return list()
        try:
            with self.db.cursor() as cur:
                # Cari gateway dari device target
                cur.execute(
                    """
                    SELECT hardware_info->>'gateway' as gw,
                           hardware_info->>'ip' as ip
                    FROM fleet_devices
                    WHERE pc_name = %s LIMIT 1
                    """,
                    (device,),
                )
                row = cur.fetchone()
                if not row or not row[0]:
                    return list()

                gateway = row[0]

                # Temukan semua perangkat lain di segmen yang sama
                cur.execute(
                    """
                    SELECT pc_name FROM fleet_devices
                    WHERE hardware_info->>'gateway' = %s
                      AND pc_name != %s
                      AND status IN ('ACTIVE', 'ONLINE')
                    """,
                    (gateway, device),
                )
                return [r[0] for r in cur.fetchall()]
        except Exception as e:
            logger.warning("[DRY-RUN] DB error getting affected devices: %s", e)
            return list()

    def _get_device_criticality(self, device: str) -> str:
        """Menentukan business criticality dari perangkat (Core, Aggregation, Access)."""
        if not self.db:
            return "MEDIUM"
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    "SELECT hardware_info->>'role', pc_name FROM fleet_devices WHERE pc_name = %s LIMIT 1",
                    (device,)
                )
                row = cur.fetchone()
                if not row:
                    return "MEDIUM"
                
                role = (row[0] or "").lower()
                name = (row[1] or "").lower()
                
                if "core" in role or "core" in name or "gateway" in role:
                    return "CRITICAL"
                elif "dist" in role or "agg" in role or "server" in name:
                    return "HIGH"
                else:
                    return "MEDIUM"
        except Exception as e:
            logger.exception("[DRY-RUN] Fatal error in _get_device_criticality: %s", e)
            return "MEDIUM"

    def _calculate_final_risk(self, base_risk: str, criticality: str, affected_count: int, action: str) -> dict:
        """Kalkulasi risk matrix kombinasi: Action Risk + Device Criticality + Blast Radius."""
        score = RISK_WEIGHTS.get(base_risk, 3) * RISK_WEIGHTS.get(criticality, 2)
        
        # Tambahan beban dari blast radius
        if affected_count > 10:
            score += 10
        elif affected_count > 5:
            score += 5
        elif affected_count > 2:
            score += 2

        # Konversi score kembali ke level
        if score >= 15:
            level = "CRITICAL"
            reason = f"Aksi '{action}' pada perangkat {criticality} akan berdampak ke {affected_count} perangkat lain. HITL WAJIB."
        elif score >= 8:
            level = "HIGH"
            reason = f"Risiko eksekusi '{action}' TINGGI pada perangkat {criticality}. Dry-Run & HITL disarankan."
        elif score >= 4:
            level = "MEDIUM"
            reason = f"Aksi '{action}' aman dieksekusi dengan monitoring Rollback aktif. Terdampak: {affected_count} perangkat."
        else:
            level = "LOW"
            reason = f"Risiko eksekusi '{action}' RENDAH. Terdampak: {affected_count} perangkat. Auto-execute."
            
        return {"level": level, "reason": reason}

    # ─────────────────────────────────────────────────────────────
    # AUDIT LOGGING
    # ─────────────────────────────────────────────────────────────

    def _log(self, action: str, device: str, result: dict) -> None:
        """Catat hasil evaluasi ke dry_run_logs untuk audit & learning."""
        if not self.db:
            return
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO dry_run_logs (action, device, result, created_at)
                    VALUES (%s, %s, %s, NOW())
                    """,
                    (action, device, json.dumps(result)),
                )
            self.db.commit()
        except Exception as e:
            logger.warning("[DRY-RUN] Failed to log dry run result: %s", e)
            try:
                self.db.rollback()
            except Exception as e:
                logger.exception("[DRY-RUN] Failed to rollback DB: %s", e)
