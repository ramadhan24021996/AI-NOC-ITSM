"""
Enterprise Remediation Policy Engine
Evaluates Risk Score, Maintenance Window, Confidence Thresholds (<80% HITL, >95% Auto-Execute),
and Automation Policies before remediation actions are dispatched.
"""

import logging
import time
from typing import Dict, Any

logger = logging.getLogger("REMEDIATION_POLICY_ENGINE")

class RemediationPolicyEngine:
    """
    Enterprise Policy Engine & Automation Guardrail
    Determines whether an action can execute automatically or requires Human-in-the-Loop approval.
    """

    def evaluate_action_policy(
        self,
        confidence: float,
        risk_score: float,
        is_maintenance_window: bool = True
    ) -> Dict[str, Any]:
        """
        Evaluates policy rules:
        - Confidence >= 0.95 & Risk <= 50.0 -> AUTO_EXECUTE
        - Confidence < 0.80 or Risk > 70.0 -> HITL_APPROVAL_REQUIRED
        - Otherwise -> HYBRID_APPROVAL_FAST_TRACK
        """
        if confidence >= 0.95 and risk_score <= 50.0 and is_maintenance_window:
            decision = "AUTO_EXECUTE"
            reason = "High confidence (>95%) and low risk (<=50) within maintenance window."
        elif confidence < 0.80 or risk_score > 70.0:
            decision = "HITL_APPROVAL_REQUIRED"
            reason = f"Confidence ({confidence*100:.1f}%) below 80% or Risk Score ({risk_score}) above 70."
        else:
            decision = "HYBRID_APPROVAL_FAST_TRACK"
            reason = "Moderate risk/confidence profile. Fast-track operator approval recommended."

        logger.info("[POLICY ENGINE] Decision: %s (Reason: %s)", decision, reason)
        return {
            "action": decision,
            "reason": reason,
            "confidence": confidence,
            "risk_score": risk_score,
            "is_maintenance_window": is_maintenance_window,
            "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
