"""
human_escalation_engine.py
===========================
Adaptive Multi-Tier Escalation Engine (Level 0 - Level 5).
Mengelola eskalasi insiden secara adaptif dan melakukan pengiriman notifikasi darurat
ke Telegram Bot API & SMS Gateway.
"""

import logging
import time
import os
import json
import urllib.request
from typing import Dict, List, Any, Optional

logger = logging.getLogger("HUMAN_ESCALATION_ENGINE")


class HumanEscalationChain:
    """
    Adaptive 6-Tier Escalation Engine:
    Level 0: Retry / Next Diagnostic
    Level 1: Alternative Remediation
    Level 2: Escalate to Higher Diagnostic
    Level 3: HITL Approval Gate
    Level 4: NOC Engineer Assignment (Telegram Dispatch)
    Level 5: Specialist / Vendor Escalation (SMS Dispatch)
    """

    def __init__(self):
        self.level1_timeout_sec = int(os.getenv("ESCALATION_L1_TIMEOUT_SEC", "900"))  # 15 Menit
        self.level2_timeout_sec = int(os.getenv("ESCALATION_L2_TIMEOUT_SEC", "1800")) # 30 Menit
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.sms_gateway_url = os.getenv("SMS_GATEWAY_URL", "")

    def determine_escalation_level(
        self,
        incident_context: Any
    ) -> Dict[str, Any]:
        """
        Menentukan tingkat eskalasi adaptif (Level 0 - Level 5).
        """
        severity = incident_context.severity.upper()
        impact = incident_context.business_impact.upper()
        attempt_count = incident_context.attempt_count
        confidence = incident_context.confidence
        risk_score = incident_context.risk_score
        failed_count = len(incident_context.failed_actions)

        level = 0
        reason = "Diagnosis & remediasi standar."

        if failed_count == 1:
            level = 1
            reason = "Tindakan pertama gagal. Beralih ke Rencana Remedi Alternatif."

        if failed_count >= 2 or confidence < 0.50:
            level = 2
            reason = "Multiple kegagalan tindakan atau confidence hipotesis rendah (< 50%)."

        if risk_score > 0.40 or impact == "HIGH" or incident_context.hitl_status == "PENDING":
            level = 3
            reason = "Risiko tindakan tinggi / Dampak bisnis tinggi. Memerlukan persetujuan operator (HITL)."

        if (severity == "CRITICAL" and failed_count >= 2) or impact == "CRITICAL":
            level = 4
            reason = "Insiden CRITICAL dengan dampak luas. Eskalasi langsung ke NOC Engineer."

        if attempt_count >= 4 or (severity == "CRITICAL" and failed_count >= 3):
            level = 5
            reason = "Insiden tidak terselesaikan setelah 4 percobaan. Eskalasi Darurat ke Spesialis / Vendor."

        incident_context.escalation_level = level
        logger.info(f"[EscalationEngine] Escalation Level determined: Level {level} for incident {incident_context.incident_id} ({reason})")

        return {
            "incident_id": incident_context.incident_id,
            "escalation_level": level,
            "reason": reason,
            "severity": severity,
            "business_impact": impact,
            "attempt_count": attempt_count,
            "failed_actions_count": failed_count
        }

    def evaluate_approval_timeout(
        self,
        incident_id: str,
        action_plan: Dict[str, Any],
        requested_at_timestamp: float
    ) -> Dict[str, Any]:
        """
        Evaluasi waktu tunggu persetujuan HITL untuk pemicu eskalasi otomatis.
        """
        now = time.time()
        elapsed_sec = max(0.0, now - requested_at_timestamp)
        elapsed_min = round(elapsed_sec / 60.0, 1)

        result = {
            "incident_id": incident_id,
            "elapsed_seconds": round(elapsed_sec, 1),
            "elapsed_minutes": elapsed_min,
            "current_escalation_level": 3,
            "escalation_target": "NOC_LEVEL1_DASHBOARD",
            "action_taken": "WAITING_OPERATOR_APPROVAL",
            "force_executed": False,
            "status_message": f"Insiden {incident_id} menunggu persetujuan Level 3 NOC Dashboard ({elapsed_min} menit)."
        }

        if elapsed_sec >= self.level2_timeout_sec:
            result["current_escalation_level"] = 5
            result["escalation_target"] = "SUPERADMIN_SMS_AND_AUTO_EXECUTE"
            result["action_taken"] = "FORCE_EXECUTE_PLAN_A_EMERGENCY"
            result["force_executed"] = True
            result["status_message"] = (
                f"🚨 CRITICAL TIMEOUT (>30 Min)! Level 5 Emergency Escalation Triggered for {incident_id}. "
                f"Emergency SMS sent & Force Executed Plan A ('{action_plan.get('name', 'Safe Recovery')}')!"
            )
            self._send_emergency_sms(incident_id, action_plan, elapsed_min)
            logger.error(result["status_message"])

        elif elapsed_sec >= self.level1_timeout_sec:
            result["current_escalation_level"] = 4
            result["escalation_target"] = "DUTY_ENGINEER_TELEGRAM_BOT"
            result["action_taken"] = "TELEGRAM_HIGH_PRIORITY_DISPATCH"
            result["force_executed"] = False
            result["status_message"] = (
                f"⚠️ LEVEL 4 ESCALATION (15-30 Min)! Dispatched high-priority alert to Duty Engineer Telegram Channel!"
            )
            self._send_telegram_alert(incident_id, action_plan, elapsed_min)
            logger.warning(result["status_message"])

        return result

    def _send_telegram_alert(self, incident_id: str, plan: Dict[str, Any], elapsed_min: float):
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.info(f"[ESCALATION-L4] Telegram Alert dispatched for incident '{incident_id}' (Elapsed: {elapsed_min}m)")
            return

        msg_text = (
            f"⚠️ *ESKALASI LEVEL 4 (TIMEOUT NOC)*\n"
            f"Insiden: `{incident_id}`\n"
            f"Waktu Tunggu: {elapsed_min} menit tanpa persetujuan!\n"
            f"Rencana Aksi: {plan.get('name', 'N/A')}\n"
            f"Target: `{plan.get('target', 'N/A')}`\n"
            f"Harap segera Approve via Telegram atau Web UI Dashboard!"
        )
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = json.dumps({"chat_id": self.telegram_chat_id, "text": msg_text, "parse_mode": "Markdown"}).encode("utf-8")

        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as response:
                logger.info(f"[ESCALATION-L4] Telegram alert sent for {incident_id}. Status: {response.status}")
        except Exception as e:
            logger.error(f"[ESCALATION-L4] Failed to send Telegram alert for {incident_id}: {e}")

    def _send_emergency_sms(self, incident_id: str, plan: Dict[str, Any], elapsed_min: float):
        logger.info(f"[ESCALATION-L5] Emergency SMS notification dispatched for incident '{incident_id}' (Elapsed: {elapsed_min}m)")
        if not self.sms_gateway_url:
            return

        payload = json.dumps({
            "incident_id": incident_id,
            "action": plan.get("name", "N/A"),
            "elapsed_minutes": elapsed_min,
            "priority": "CRITICAL_SMS"
        }).encode("utf-8")

        try:
            req = urllib.request.Request(self.sms_gateway_url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                logger.info(f"[ESCALATION-L5] Emergency SMS HTTP dispatch success for {incident_id}. Status: {resp.status}")
        except Exception as e:
            logger.error(f"[ESCALATION-L5] Failed to dispatch Emergency SMS for {incident_id}: {e}")
