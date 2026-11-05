"""
Phase 3.6: Remediation Contract (phase3/remediation/remediation_contract.py)

Standardized Remediation Contract enforcing Invariants #21 to #28.
"""

import logging
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime, UTC
from phase3.remediation.rollback_contract import RollbackContract

logger = logging.getLogger("REMEDIATION_CONTRACT")

VALID_REMEDIATION_STATUSES = {
    "DRAFT", "VALIDATING", "ELIGIBLE", "PRECONDITION_FAILED",
    "AWAITING_HITL", "AUTHORIZED", "EXECUTING", "VERIFYING",
    "SUCCESS", "FAILED", "ROLLBACK_REQUIRED"
}


@dataclass
class RemediationContract:
    contract_id: str
    incident_id: str
    trace_id: str
    confirmed_cause_id: str
    cause_status: str  # MUST BE "CONFIRMED" (Invariant #21)
    objective: str
    target_scope: str
    preconditions: List[Dict[str, Any]]  # Invariant #23
    action_definition: Dict[str, Any]  # Invariant #22
    constraints: List[str]
    risk_score: float  # Scale 0.0 - 1.0
    blast_radius: Dict[str, Any]  # Invariant #25
    reversibility: bool
    rollback_contract: Optional[RollbackContract]  # Invariant #26
    postconditions: List[Dict[str, Any]]  # Invariant #24
    verification_policy: Dict[str, Any]
    required_authorization: str = "G5_HITL_REQUIRED"
    status: str = "DRAFT"
    created_at: str = field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    contract_hash: str = field(init=False)

    def __post_init__(self):
        rollback_dict = self.rollback_contract.to_dict() if self.rollback_contract else {}
        raw = f"{self.contract_id}:{self.incident_id}:{self.trace_id}:{self.confirmed_cause_id}:{self.cause_status}:{json.dumps(self.action_definition)}:{json.dumps(self.blast_radius)}:{json.dumps(rollback_dict)}:{self.created_at}"
        self.contract_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def validate_contract_integrity(self) -> Dict[str, Any]:
        """
        Validates contract completeness against Invariants #21 to #26.
        """
        violations = []
        # Invariant #21: Cause MUST be CONFIRMED
        if self.cause_status != "CONFIRMED":
            violations.append(f"Invariant #21 Violation: Cause status '{self.cause_status}' is NOT 'CONFIRMED'")

        # Invariant #22: Action Definition Required
        if not self.action_definition or not self.action_definition.get("action_type"):
            violations.append("Invariant #22 Violation: Missing structured action definition")

        # Invariant #23: Preconditions Required
        if not self.preconditions:
            violations.append("Invariant #23 Violation: Missing preconditions list")

        # Invariant #24: Postconditions Required
        if not self.postconditions:
            violations.append("Invariant #24 Violation: Missing postconditions list")

        # Invariant #25: Blast Radius Bound Required
        if not self.blast_radius or not self.blast_radius.get("max_affected_nodes"):
            violations.append("Invariant #25 Violation: Missing blast radius boundaries")

        # Invariant #26: Rollback Contract Required for Reversible Mutating Actions
        if not self.rollback_contract:
            violations.append("Invariant #26 Violation: Missing rollback contract")

        is_valid = (len(violations) == 0)
        return {
            "is_valid": is_valid,
            "violations_count": len(violations),
            "violations": violations
        }

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        if self.rollback_contract:
            d["rollback_contract"] = self.rollback_contract.to_dict()
        return d
