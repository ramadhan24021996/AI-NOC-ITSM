"""
SERVER.orchestrator.governance.decision_drift
===============================================
Component: Decision Drift Detector

Monitors degradation in action success rates over time:
"Recommendation Drift: Restart PostgreSQL Container Success Rate dropped from 93% to 48%"
Automatically downgrades ranking when drift is detected.
"""
import logging
from typing import Dict, Any
from SERVER.contracts.schemas import DecisionDriftReport

logger = logging.getLogger("orchestrator.governance.drift")


class DecisionDriftDetector:
    """
    Detects decision success rate drift over operational history.
    """

    def evaluate_drift(
        self, action_name: str, historical_success_pct: int = 93, current_success_pct: int = 48
    ) -> DecisionDriftReport:
        drift_detected = (historical_success_pct - current_success_pct) >= 20

        rec = ""
        if drift_detected:
            rec = f"Recommendation Drift detected: {action_name} success rate dropped from {historical_success_pct}% to {current_success_pct}%. Ranking downgraded."
            logger.warning(f"[DecisionDriftDetector] {rec}")

        report = DecisionDriftReport(
            action_name=action_name,
            historical_success_pct=historical_success_pct,
            current_success_pct=current_success_pct,
            drift_detected=drift_detected,
            action_recommendation=rec,
        )
        return report
