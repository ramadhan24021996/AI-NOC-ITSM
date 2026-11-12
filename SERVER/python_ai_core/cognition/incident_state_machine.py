"""
Enterprise Incident State Machine
Tracks formal state transitions for incident auditing:
NEW -> VALIDATING -> GRAPH_BUILT -> RANKING -> RAG_RUNNING -> LLM_RUNNING ->
EVIDENCE_CHECK -> HITL_PENDING -> APPROVED -> AUTO_REMEDIATE -> VERIFIED -> LEARNING -> CLOSED
"""

import logging
import time
from typing import Dict, List, Any, Optional

logger = logging.getLogger("INCIDENT_STATE_MACHINE")

VALID_STATES = {
    "NEW", "VALIDATING", "QUARANTINED", "GRAPH_BUILT", "RANKING", "RAG_RUNNING",
    "LLM_RUNNING", "EVIDENCE_CHECK", "HITL_PENDING", "APPROVED",
    "AUTO_REMEDIATE", "VERIFIED", "LEARNING", "CLOSED"
}

class IncidentStateMachine:
    """
    Enterprise Incident State Machine
    Maintains audit trail of all incident state transitions.
    """

    def __init__(self):
        self.history: Dict[str, List[Dict[str, Any]]] = {}

    def transition(self, incident_id: str, new_state: str, metadata: Optional[Dict[str, Any]] = None) -> bool:
        """Transitions incident to new state and records timestamp."""
        if new_state not in VALID_STATES:
            logger.error("[STATE MACHINE] Invalid state transition attempt: %s", new_state)
            return False

        if incident_id not in self.history:
            self.history[incident_id] = []

        entry = {
            "state": new_state,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "metadata": metadata or {}
        }
        self.history[incident_id].append(entry)
        logger.info("[STATE MACHINE] Incident %s transitioned -> %s", incident_id, new_state)
        return True

    def get_current_state(self, incident_id: str) -> str:
        """Returns active state of incident."""
        if incident_id in self.history and self.history[incident_id]:
            return self.history[incident_id][-1]["state"]
        return "NEW"

    def get_history(self, incident_id: str) -> List[Dict[str, Any]]:
        """Returns state audit history for incident."""
        return self.history.get(incident_id, [])
