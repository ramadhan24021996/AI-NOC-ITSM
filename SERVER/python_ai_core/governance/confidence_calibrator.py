"""
Adaptive Confidence Calibration Engine (governance/confidence_calibrator.py)

Dynamically calibrates AI Confidence Thresholds based on:
1. Historical success rate per host / site (14 days)
2. Recent operator human rejections / rollbacks (< 24 hours)
3. Risk multiplier of the target action

Standard Base Thresholds:
- AUTO_EXECUTE: >= 92.0%
- HITL_APPROVAL: 70.0% - 91.9%
- GUIDANCE_ONLY: < 70.0%
"""

import logging
import json

logger = logging.getLogger("CONFIDENCE_CALIBRATOR")

class AdaptiveConfidenceCalibrator:
    def __init__(self, conn=None):
        self.conn = conn

    def get_calibrated_threshold(self, pc_name: str, action_name: str, base_threshold: float = 92.0) -> tuple[float, str]:
        """
        Calculates the calibrated auto-execute confidence threshold for a target node.
        Returns: (calibrated_threshold: float, reason: str)
        """
        if not self.conn or not pc_name or pc_name == "UNKNOWN":
            return base_threshold, "Standard Base Threshold (92.0%)"

        try:
            with self.conn.cursor() as cur:
                # 1. Check for recent human rejections or rollbacks within 24h
                cur.execute("""
                    SELECT COUNT(*) FROM hitl_audit_logs 
                    WHERE (pc_name = %s OR action_taken ILIKE %s)
                      AND action_taken ILIKE 'REJECT%'
                      AND created_at >= NOW() - INTERVAL '24 hours'
                """, (pc_name, f"%{action_name}%"))
                recent_rejections = cur.fetchone()[0]

                if recent_rejections > 0:
                    calibrated = min(98.0, base_threshold + 4.0)  # Raise to 96%
                    reason = f"Node '{pc_name}' has {recent_rejections} recent operator rejection(s) < 24h. Threshold raised to {calibrated:.1f}%."
                    logger.info(f"[CALIBRATOR] {reason}")
                    return calibrated, reason

                # 2. Check 14-day resolution success rate
                cur.execute("""
                    SELECT COUNT(*), 
                           COUNT(*) FILTER (WHERE final_outcome = 'RESOLVED' OR verification_result = 'PASSED')
                    FROM autonomous_decision_records
                    WHERE agent_id = %s AND created_at >= NOW() - INTERVAL '14 days'
                """, (pc_name,))
                row = cur.fetchone()
                total_records = row[0] if row else 0
                successful_records = row[1] if row else 0

                if total_records >= 3 and successful_records == total_records:
                    calibrated = max(85.0, base_threshold - 4.0)  # Lower to 88%
                    reason = f"Node '{pc_name}' has 100% success rate ({successful_records}/{total_records}) over 14 days. Threshold lowered to {calibrated:.1f}%."
                    logger.info(f"[CALIBRATOR] {reason}")
                    return calibrated, reason

        except Exception as err:
            logger.warning(f"[CALIBRATOR] Database check failed: {err}. Using base threshold.")

        return base_threshold, f"Standard Node Baseline ({base_threshold:.1f}%)"

def calibrate_decision_tier(confidence_score: float, pc_name: str, action_name: str, conn=None) -> dict:
    """
    Evaluates final decision tier (AUTO_EXECUTE, HITL_APPROVAL, GUIDANCE_ONLY) 
    using dynamically calibrated confidence threshold.
    """
    calibrator = AdaptiveConfidenceCalibrator(conn)
    auto_thresh, reason = calibrator.get_calibrated_threshold(pc_name, action_name, base_threshold=92.0)

    if confidence_score >= auto_thresh:
        tier = "AUTO_EXECUTE"
    elif confidence_score >= 70.0:
        tier = "HITL_APPROVAL"
    else:
        tier = "GUIDANCE_ONLY"

    return {
        "tier": tier,
        "confidence_score": confidence_score,
        "calibrated_auto_threshold": auto_thresh,
        "calibration_reason": reason
    }
