"""
Phase 4: Orchestrator Hardening — Deterministic State Machine
NOC IT AI v3.0

Defines:
- Valid states
- Allowed transitions (adjacency matrix)
- Transition guards (invariant checks)
- Invalid transition rejection with logging
"""
import logging
from typing import Optional, Dict, Set, Tuple

logger = logging.getLogger("STATE_MACHINE")

# ─────────────────────────────────────────────────────────────
# 1. CANONICAL STATE DEFINITIONS
# ─────────────────────────────────────────────────────────────
class IncidentState:
    NEW               = "NEW"
    OPEN              = "OPEN"           # alias NEW for legacy compatibility
    ANALYZING         = "ANALYZING"
    APPROVAL_PENDING  = "APPROVAL_PENDING"
    WAITING_APPROVAL  = "WAITING_APPROVAL"  # alias APPROVAL_PENDING
    APPROVED          = "APPROVED"
    EXECUTING         = "EXECUTING"
    WAITING_VERIFICATION = "WAITING_VERIFICATION"
    VERIFYING         = "VERIFYING"
    SUCCESS           = "SUCCESS"
    ROLLBACK_PENDING  = "ROLLBACK_PENDING"
    ROLLED_BACK       = "ROLLED_BACK"
    FAILED            = "FAILED"
    DLQ               = "DLQ"
    ESCALATED         = "ESCALATED"
    RESOLVED          = "RESOLVED"

# Canonical set
VALID_STATES: Set[str] = {
    IncidentState.NEW,
    IncidentState.OPEN,
    IncidentState.ANALYZING,
    IncidentState.APPROVAL_PENDING,
    IncidentState.WAITING_APPROVAL,
    IncidentState.APPROVED,
    IncidentState.EXECUTING,
    IncidentState.WAITING_VERIFICATION,
    IncidentState.VERIFYING,
    IncidentState.SUCCESS,
    IncidentState.ROLLBACK_PENDING,
    IncidentState.ROLLED_BACK,
    IncidentState.FAILED,
    IncidentState.DLQ,
    IncidentState.ESCALATED,
    IncidentState.RESOLVED,
}

# ─────────────────────────────────────────────────────────────
# 2. TRANSITION MATRIX
# Maps: from_state -> set of allowed to_states
# ─────────────────────────────────────────────────────────────
ALLOWED_TRANSITIONS: Dict[str, Set[str]] = {
    IncidentState.NEW: {
        IncidentState.ANALYZING,
        IncidentState.DLQ,
    },
    IncidentState.OPEN: {
        IncidentState.ANALYZING,
        IncidentState.WAITING_APPROVAL,
        IncidentState.APPROVAL_PENDING,
        IncidentState.ESCALATED,
        IncidentState.DLQ,
        IncidentState.RESOLVED,
    },
    IncidentState.ANALYZING: {
        IncidentState.OPEN,
        IncidentState.APPROVAL_PENDING,
        IncidentState.WAITING_APPROVAL,
        IncidentState.EXECUTING,
        IncidentState.FAILED,
        IncidentState.DLQ,
    },
    IncidentState.APPROVAL_PENDING: {
        IncidentState.APPROVED,
        IncidentState.FAILED,
        IncidentState.DLQ,
        IncidentState.ESCALATED,
    },
    IncidentState.WAITING_APPROVAL: {
        IncidentState.APPROVED,
        IncidentState.FAILED,
        IncidentState.DLQ,
        IncidentState.ESCALATED,
    },
    IncidentState.APPROVED: {
        IncidentState.EXECUTING,
        IncidentState.FAILED,
    },
    IncidentState.EXECUTING: {
        IncidentState.WAITING_VERIFICATION,
        IncidentState.VERIFYING,
        IncidentState.ROLLBACK_PENDING,
        IncidentState.FAILED,
        IncidentState.DLQ,
    },
    IncidentState.WAITING_VERIFICATION: {
        IncidentState.VERIFYING,
        IncidentState.FAILED,
        IncidentState.DLQ,
        IncidentState.ESCALATED,
    },
    IncidentState.VERIFYING: {
        IncidentState.RESOLVED,
        IncidentState.SUCCESS,
        IncidentState.ROLLBACK_PENDING,
        IncidentState.FAILED,
        IncidentState.ESCALATED,
    },
    IncidentState.ROLLBACK_PENDING: {
        IncidentState.ROLLED_BACK,
        IncidentState.FAILED,
    },
    IncidentState.ROLLED_BACK: {
        IncidentState.OPEN,       # re-open for reanalysis
        IncidentState.FAILED,
    },
    # Terminal states — no further transitions
    IncidentState.SUCCESS:    set(),
    IncidentState.FAILED:     {IncidentState.DLQ, IncidentState.OPEN},
    IncidentState.DLQ:        {IncidentState.OPEN},   # allow retry
    IncidentState.ESCALATED:  {IncidentState.RESOLVED, IncidentState.ANALYZING},
    IncidentState.RESOLVED:   set(),
}

# ─────────────────────────────────────────────────────────────
# 3. REJECTION MATRIX
# Explicit hard-forbidden transitions with reason
# ─────────────────────────────────────────────────────────────
FORBIDDEN_TRANSITIONS: Dict[Tuple[str, str], str] = {
    (IncidentState.WAITING_VERIFICATION, IncidentState.EXECUTING): "Cannot go back to EXECUTING from WAITING_VERIFICATION",
    (IncidentState.VERIFYING,  IncidentState.EXECUTING):  "VERIFYING cannot precede EXECUTING",
    (IncidentState.SUCCESS,    IncidentState.WAITING_VERIFICATION): "SUCCESS before WAITING_VERIFICATION is invalid",
    (IncidentState.SUCCESS,    IncidentState.VERIFYING):  "SUCCESS before VERIFYING is invalid",
    (IncidentState.SUCCESS,    IncidentState.EXECUTING):  "SUCCESS before EXECUTING is invalid",
    (IncidentState.APPROVED,   IncidentState.ANALYZING):  "Cannot re-analyze after APPROVED",
    (IncidentState.ROLLED_BACK,IncidentState.EXECUTING):  "Cannot EXECUTE after ROLLED_BACK without re-approval",
    (IncidentState.RESOLVED,   IncidentState.EXECUTING):  "RESOLVED incidents cannot be executed",
    (IncidentState.RESOLVED,   IncidentState.ANALYZING):  "RESOLVED incidents cannot be re-analyzed",
}

# ─────────────────────────────────────────────────────────────
# 4. STATE MACHINE ENGINE
# ─────────────────────────────────────────────────────────────
from dataclasses import dataclass
from typing import Optional, Dict, Set, Tuple
import datetime

@dataclass
class TransitionResult:
    success: bool
    from_state: str
    to_state: str
    reason: str
    timestamp: str

class IncidentStateMachine:
    """
    Deterministic state machine for incident lifecycle.
    Purely logic-based; manages current state, target state, and validation.
    Does NOT contain business logic or external dependencies (No DB, no LLM, no NATS).
    """

    def __init__(self):
        pass

    def can_transition(self, from_state: str, to_state: str) -> Tuple[bool, str]:
        """
        Check if a transition is valid.
        Returns (allowed: bool, reason: str).
        """
        # 1. Validate state names
        if from_state not in VALID_STATES:
            return False, f"Unknown source state: '{from_state}'"
        if to_state not in VALID_STATES:
            return False, f"Unknown target state: '{to_state}'"

        # 2. No-op transition (idempotent)
        if from_state == to_state:
            return True, "NO_OP"

        # 3. Check explicit forbidden transitions
        forbidden_reason = FORBIDDEN_TRANSITIONS.get((from_state, to_state))
        if forbidden_reason:
            return False, f"FORBIDDEN: {forbidden_reason}"

        # 4. Check allowed transition matrix
        allowed = ALLOWED_TRANSITIONS.get(from_state, set())
        if to_state not in allowed:
            return False, f"ILLEGAL_TRANSITION: {from_state} -> {to_state} not in allowed set {sorted(allowed)}"

        return True, "ALLOWED"

    def transition(self, from_state: str, to_state: str) -> TransitionResult:
        """
        Attempt a state transition with full guard logic.
        Returns a TransitionResult object.
        """
        allowed, reason = self.can_transition(from_state, to_state)

        result = TransitionResult(
            success=allowed,
            from_state=from_state,
            to_state=to_state if allowed else from_state,
            reason=reason,
            timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat()
        )

        if not allowed:
            logger.error(f"[STATE_MACHINE] REJECTED transition: {from_state} -> {to_state} | Reason: {reason}")
        elif reason == "NO_OP":
            logger.debug(f"[STATE_MACHINE] NO_OP transition: {from_state}")
        else:
            logger.info(f"[STATE_MACHINE] VALIDATED transition: {from_state} -> {to_state}")

        return result

    @staticmethod
    def get_transition_matrix() -> dict:
        """Return full transition matrix for observability/UI."""
        return {
            "states": sorted(VALID_STATES),
            "transitions": {k: sorted(v) for k, v in ALLOWED_TRANSITIONS.items()},
            "forbidden": {f"{k[0]}->{k[1]}": v for k, v in FORBIDDEN_TRANSITIONS.items()},
        }

