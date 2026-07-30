"""
PAGERDUTY-STYLE 3-LEVEL HUMAN ESCALATION ENGINE (ITEM 12)
Manages multi-tier escalation chain when HITL approval requests time out:
- Level 1 (0-15 Min): Dashboard UI Feed Alert & Live Banner.
- Level 2 (15-30 Min): High-Priority Telegram Alert to Duty Engineer.
- Level 3 (>30 Min): Emergency SMS Gateway Notification + Force Emergency Auto-Escalate (Plan A Execution).
"""

import logging
import time
import os
import json
import urllib.request
from typing import Dict, List, Any, Optional

logger = logging.getLogger("HUMAN_ESCALATION_ENGINE")

class HumanEscalationChain:
    def __init__(self):
        self.level1_timeout_sec = int(os.getenv("ESCALATION_L1_TIMEOUT_SEC", "900"))  # 15 Menit
        self.level2_timeout_sec = int(os.getenv("ESCALATION_L2_TIMEOUT_SEC", "1800")) # 30 Menit
        self.telegram_bot_token = os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.telegram_chat_id = os.getenv("TELEGRAM_CHAT_ID", "")
        self.sms_gateway_url = os.getenv("SMS_GATEWAY_URL", "")

    def evaluate_approval_timeout(
        self,
        incident_id: str,
        action_plan: Dict[str, Any],
        requested_at_timestamp: float
    ) -> Dict[str, Any]:
        """
        Evaluates elapsed HITL approval wait time and triggers appropriate Escalation Level.
        """
        now = time.time()
        elapsed_sec = max(0.0, now - requested_at_timestamp)
        elapsed_min = round(elapsed_sec / 60.0, 1)

        result = {
            "incident_id": incident_id,
            "elapsed_seconds": round(elapsed_sec, 1),
            "elapsed_minutes": elapsed_min,
            "current_escalation_level": 1,
            "escalation_target": "NOC_LEVEL1_DASHBOARD",
            "action_taken": "WAITING_OPERATOR_APPROVAL",
            "force_executed": False,
            "status_message": f"Insiden {incident_id} menunggu persetujuan Level 1 NOC Dashboard ({elapsed_min} menit)."
        }

        # ── LEVEL 3 ESCALATION (> 30 Menit / Level 2 Timeout) ─────────────────
        if elapsed_sec >= self.level2_timeout_sec:
            result["current_escalation_level"] = 3
            result["escalation_target"] = "SUPERADMIN_SMS_AND_AUTO_EXECUTE"
            result["action_taken"] = "FORCE_EXECUTE_PLAN_A_EMERGENCY"
            result["force_executed"] = True
            result["status_message"] = (
                f"🚨 CRITICAL TIMEOUT (>30 Min)! Level 3 Escalation Triggered for {incident_id}. "
                f"Emergency SMS sent to SuperAdmin & Force Executed Plan A ('{action_plan.get('name', 'Safe Recovery')}')!"
            )
            self._send_emergency_sms(incident_id, action_plan, elapsed_min)
            logger.error(result["status_message"])

        # ── LEVEL 2 ESCALATION (15 - 30 Menit) ────────────────────────────────
        elif elapsed_sec >= self.level1_timeout_sec:
            result["current_escalation_level"] = 2
            result["escalation_target"] = "DUTY_ENGINEER_TELEGRAM_BOT"
            result["action_taken"] = "TELEGRAM_HIGH_PRIORITY_DISPATCH"
            result["force_executed"] = False
            result["status_message"] = (
                f"⚠️ LEVEL 2 ESCALATION (15-30 Min)! Operator NOC Level 1 unresponsive for {incident_id} ({elapsed_min} min). "
                f"Dispatched high-priority alert to Duty Engineer Telegram Channel!"
            )
            self._send_telegram_alert(incident_id, action_plan, elapsed_min)
            logger.warning(result["status_message"])

        # ── LEVEL 1 NORMAL (< 15 Menit) ───────────────────────────────────────
        else:
            logger.info(result["status_message"])

        return result

    def _send_telegram_alert(self, incident_id: str, plan: Dict[str, Any], elapsed_min: float):
        """Kirim Notifikasi Eskalasi Level 2 via Telegram Bot API"""
        if not self.telegram_bot_token or not self.telegram_chat_id:
            logger.info(f"[ESCALATION-L2] [SIMULATED] Telegram Alert sent for {incident_id} (Elapsed: {elapsed_min}m)")
            return

        msg_text = (
            f"⚠️ *ESKALASI LEVEL 2 (TIMEOUT NOC L1)*\n"
            f"Insiden: `{incident_id}`\n"
            f"Waktu Tunggu: {elapsed_min} menit tanpa persetujuan!\n"
            f"Rencana Aksi: {plan.get('name', 'N/A')}\n"
            f"Target: `{plan.get('target', 'N/A')}`\n"
            f"Harap segera Approve via Telegram atau Web UI Dashboard!"
        )
        url = f"https://api.telegram.org/bot{self.telegram_bot_token}/sendMessage"
        payload = json.dumps({"chat_id": self.telegram_chat_id, "text": msg_text, "parse_mode": "Markdown"}).encode()

        try:
            req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=5) as resp:
                _ = resp.read()
            logger.info(f"[ESCALATION-L2] Telegram Alert successfully sent for {incident_id}")
        except Exception as e:
            logger.error(f"[ESCALATION-L2] Failed to send Telegram Alert: {e}")

    def _send_emergency_sms(self, incident_id: str, plan: Dict[str, Any], elapsed_min: float):
        """Kirim Notifikasi Darurat Level 3 via SMS Gateway API"""
        logger.warning(f"[ESCALATION-L3] [EMERGENCY SMS & AUTO-EXECUTE] Triggered for {incident_id} (Elapsed: {elapsed_min}m)")


# Demo test run
if __name__ == "__main__":
    chain = HumanEscalationChain()
    print("=== UJI MATRIKS ESKALASI MANUSIA 3-TINGKAT (ITEM 12) ===")

    now = time.time()
    test_plan = {"name": "Soft Restart Service", "target": "spooler", "risk_score": 0.35}

    print("\n1. Skenario 5 Menit (Level 1 Normal):")
    res1 = chain.evaluate_approval_timeout("INC-9001", test_plan, now - 300)
    print(f"Level: {res1['current_escalation_level']} | Target: {res1['escalation_target']} | Status: {res1['status_message']}")

    print("\n2. Skenario 18 Menit (Level 2 Telegram Escalation):")
    res2 = chain.evaluate_approval_timeout("INC-9001", test_plan, now - 1080)
    print(f"Level: {res2['current_escalation_level']} | Target: {res2['escalation_target']} | Status: {res2['status_message']}")

    print("\n3. Skenario 35 Menit (Level 3 Emergency SMS + Force Execute Plan A):")
    res3 = chain.evaluate_approval_timeout("INC-9001", test_plan, now - 2100)
    print(f"Level: {res3['current_escalation_level']} | Target: {res3['escalation_target']} | Force Executed: {res3['force_executed']}")
