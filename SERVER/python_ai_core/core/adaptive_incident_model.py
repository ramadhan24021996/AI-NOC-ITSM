"""
adaptive_incident_model.py
===========================
Adaptive Closed-Loop Incident State Machine & Dynamic IncidentContext Model.
Mendukung 16 State Machine Canonical dan 28 Field Context Adaptif.
"""

import time
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Set

logger = logging.getLogger("AdaptiveIncidentModel")


class IncidentState:
    """16 Canonical States untuk Dynamic Incident Lifecycle."""
    NEW = "NEW"
    OBSERVING = "OBSERVING"
    CLASSIFYING = "CLASSIFYING"
    DIAGNOSING = "DIAGNOSING"
    SOP_MATCHED = "SOP_MATCHED"
    PLAN_GENERATED = "PLAN_GENERATED"
    WAITING_HITL = "WAITING_HITL"
    APPROVED = "APPROVED"
    EXECUTING = "EXECUTING"
    VERIFYING = "VERIFYING"
    RECOVERY_PARTIAL = "RECOVERY_PARTIAL"
    RECOVERY_FAILED = "RECOVERY_FAILED"
    ESCALATING = "ESCALATING"
    RESOLVED = "RESOLVED"
    CLOSED = "CLOSED"
    LEARNING = "LEARNING"


# Transitions Adjacency Matrix
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    IncidentState.NEW: {IncidentState.OBSERVING, IncidentState.CLASSIFYING},
    IncidentState.OBSERVING: {IncidentState.CLASSIFYING, IncidentState.DIAGNOSING},
    IncidentState.CLASSIFYING: {IncidentState.DIAGNOSING, IncidentState.ESCALATING},
    IncidentState.DIAGNOSING: {IncidentState.SOP_MATCHED, IncidentState.PLAN_GENERATED, IncidentState.ESCALATING},
    IncidentState.SOP_MATCHED: {IncidentState.PLAN_GENERATED, IncidentState.WAITING_HITL, IncidentState.APPROVED, IncidentState.EXECUTING},
    IncidentState.PLAN_GENERATED: {IncidentState.WAITING_HITL, IncidentState.APPROVED, IncidentState.EXECUTING, IncidentState.ESCALATING},
    IncidentState.WAITING_HITL: {IncidentState.APPROVED, IncidentState.PLAN_GENERATED, IncidentState.ESCALATING},
    IncidentState.APPROVED: {IncidentState.EXECUTING},
    IncidentState.EXECUTING: {IncidentState.VERIFYING, IncidentState.RECOVERY_FAILED},
    IncidentState.VERIFYING: {IncidentState.RESOLVED, IncidentState.RECOVERY_PARTIAL, IncidentState.RECOVERY_FAILED},
    IncidentState.RECOVERY_PARTIAL: {IncidentState.DIAGNOSING, IncidentState.ESCALATING, IncidentState.RESOLVED},
    IncidentState.RECOVERY_FAILED: {IncidentState.DIAGNOSING, IncidentState.ESCALATING, IncidentState.PLAN_GENERATED},
    IncidentState.ESCALATING: {IncidentState.WAITING_HITL, IncidentState.DIAGNOSING, IncidentState.CLOSED},
    IncidentState.RESOLVED: {IncidentState.CLOSED, IncidentState.LEARNING},
    IncidentState.CLOSED: {IncidentState.LEARNING},
    IncidentState.LEARNING: set()
}


@dataclass
class IncidentContext:
    """
    28 Field Adaptive Incident Context Model.
    """
    incident_id: str
    device_id: str
    device_type: str = "GENERAL"
    service: str = "UNKNOWN"
    os: str = "LINUX"
    timestamp: float = field(default_factory=time.time)
    severity: str = "WARNING"                 # INFO | WARNING | CRITICAL
    business_impact: str = "MEDIUM"          # LOW | MEDIUM | HIGH | CRITICAL
    current_state: str = IncidentState.NEW
    osi_layers: List[str] = field(default_factory=list)
    symptoms: List[str] = field(default_factory=list)
    telemetry: Dict[str, Any] = field(default_factory=dict)
    evidence: List[Dict[str, Any]] = field(default_factory=list)
    root_cause_candidates: List[Dict[str, Any]] = field(default_factory=list)
    probabilities: Dict[str, float] = field(default_factory=dict)
    matched_sops: List[Dict[str, Any]] = field(default_factory=list)
    selected_sop: Optional[Dict[str, Any]] = None
    current_action: Optional[Dict[str, Any]] = None
    previous_actions: List[Dict[str, Any]] = field(default_factory=list)
    failed_actions: List[Dict[str, Any]] = field(default_factory=list)
    verification_result: Optional[Dict[str, Any]] = None
    confidence: float = 0.85
    risk_score: float = 0.1
    blast_radius: float = 0.1
    hitl_status: str = "NONE"                # NONE | PENDING | APPROVED | REJECTED | MODIFIED
    escalation_level: int = 0                # 0..5
    attempt_count: int = 0
    next_action: Optional[Dict[str, Any]] = None
    resolution_status: str = "OPEN"          # OPEN | RESOLVED | UNRESOLVED | ESCALATED

    def transition_to(self, new_state: str, reason: str = "") -> bool:
        """Transisi state dengan validasi Adjacency Matrix."""
        allowed = ALLOWED_TRANSITIONS.get(self.current_state, set())
        if new_state not in allowed and new_state != self.current_state:
            logger.warning(
                f"[IncidentModel] Invalid state transition: {self.current_state} -> {new_state} "
                f"for incident {self.incident_id}. Reason: {reason}"
            )
            self.current_state = new_state
            return True

        logger.info(f"[IncidentModel] State transition: {self.current_state} -> {new_state} ({reason})")
        self.current_state = new_state
        return True

    def add_evidence(self, key: str, value: Any, source: str = "TELEMETRY") -> None:
        item = {
            "key": key,
            "value": value,
            "source": source,
            "timestamp": time.time()
        }
        self.evidence.append(item)

    def record_action_failure(self, action: Dict[str, Any], failure_reason: str) -> None:
        self.attempt_count += 1
        failed_entry = {
            "action": action,
            "failure_reason": failure_reason,
            "attempt": self.attempt_count,
            "timestamp": time.time()
        }
        self.failed_actions.append(failed_entry)
        self.previous_actions.append(failed_entry)

        self.add_evidence(
            key=f"Failure({action.get('name', 'UNKNOWN_ACTION')})",
            value=failure_reason,
            source="EXECUTION_VERIFICATION"
        )
        logger.info(f"[FailureAdaptation] Recorded Failure({action.get('name')}) | Attempt Count: {self.attempt_count}")
