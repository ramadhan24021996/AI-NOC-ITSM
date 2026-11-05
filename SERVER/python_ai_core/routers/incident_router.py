"""
Incident Routing Module (routers/incident_router.py)

Handles routing, filtering, and state transitions for incident lifecycle.
"""
import logging
from typing import Dict, Any, List

logger = logging.getLogger("INCIDENT_ROUTER")


class IncidentRouter:
    """Routes incident queries and SLA state transitions."""

    def route_incident_state(self, incident_id: int, current_status: str) -> str:
        """Determines next incident lifecycle state based on AI investigation status."""
        state_flow = {
            "TRIGGERED": "ANALYZING",
            "ANALYZING": "REMEDIATION_PROPOSED",
            "REMEDIATION_PROPOSED": "REMEDIATING",
            "REMEDIATING": "VERIFYING",
            "VERIFYING": "RESOLVED",

        }
        next_state = state_flow.get(current_status.upper(), "DLQ")
        logger.info(f"[INCIDENT_ROUTER] Incident {incident_id}: {current_status} -> {next_state}")
        return next_state
