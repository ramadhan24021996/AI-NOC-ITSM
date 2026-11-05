"""
Diagnostic State Machine Module
Manages explicit 13-stage lifecycle state transitions for enterprise incident investigations:
NEW -> COLLECTING -> CORRELATING -> GENERATING_HYPOTHESIS -> SELECTING_PROBE ->
EXECUTING_PROBE -> VALIDATING_EVIDENCE -> ELIMINATING_HYPOTHESIS -> CONSENSUS ->
RCA_READY -> REMEDIATION -> VERIFICATION -> LEARNING.
"""

from enum import Enum, auto
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime, timezone


class DiagnosticState(Enum):
    NEW = auto()
    COLLECTING = auto()
    CORRELATING = auto()
    GENERATING_HYPOTHESIS = auto()
    SELECTING_PROBE = auto()
    EXECUTING_PROBE = auto()
    VALIDATING_EVIDENCE = auto()
    ELIMINATING_HYPOTHESIS = auto()
    CONSENSUS = auto()
    RCA_READY = auto()
    REMEDIATION = auto()
    VERIFICATION = auto()
    LEARNING = auto()
    PROBING_REQUIRED = auto()  # Refusal state when evidence is insufficient


@dataclass
class StateTransitionRecord:
    from_state: str
    to_state: str
    timestamp: str
    reason: str


class DiagnosticStateMachine:
    """State Machine enforcing valid diagnostic investigation lifecycle transitions."""

    def __init__(self, incident_id: str):
        self.incident_id = incident_id
        self.current_state = DiagnosticState.NEW
        self.history: List[StateTransitionRecord] = []
        self._record_transition(None, DiagnosticState.NEW, "Incident investigation initialized")

    def _record_transition(self, old_state: Optional[DiagnosticState], new_state: DiagnosticState, reason: str):
        from_str = old_state.name if old_state else "START"
        to_str = new_state.name
        ts = datetime.now(timezone.utc).isoformat()
        self.history.append(StateTransitionRecord(
            from_state=from_str,
            to_state=to_str,
            timestamp=ts,
            reason=reason
        ))

    def transition_to(self, target_state: DiagnosticState, reason: str) -> bool:
        """Transitions state machine to target_state with log recording."""
        old_state = self.current_state
        self.current_state = target_state
        self._record_transition(old_state, target_state, reason)
        return True

    def current_state_name(self) -> str:
        return self.current_state.name

    def summary(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "current_state": self.current_state.name,
            "total_transitions": len(self.history),
            "transition_timeline": [
                f"[{h.timestamp}] {h.from_state} -> {h.to_state}: {h.reason}"
                for h in self.history
            ]
        }
