"""
Remediation Routing Module (routers/remediation_router.py)

Routes remediation plans to automated execution or Human-In-The-Loop approval.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger("REMEDIATION_ROUTER")


class RemediationRouter:
    """Routes remediation execution requests based on risk level and HITL policies."""

    def route_remediation(self, incident_id: int, risk_score: float) -> str:
        """
        High risk (>0.75) requires HITL approval; low risk runs autonomous.
        """
        if risk_score > 0.75:
            route = "HUMAN_IN_THE_LOOP_APPROVAL"
        else:
            route = "AUTONOMOUS_EXECUTION"
        logger.info(f"[REMEDIATION_ROUTER] Incident {incident_id} (risk={risk_score}) routed to {route}")
        return route
