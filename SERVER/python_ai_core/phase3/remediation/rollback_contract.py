"""
Phase 3.6: Rollback Contract (phase3/remediation/rollback_contract.py)

Enforces Invariant #26 (Rollback Bound): Every mutating remediation contract MUST have a valid rollback strategy.
"""

import logging
import hashlib
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List

logger = logging.getLogger("ROLLBACK_CONTRACT")


@dataclass
class RollbackContract:
    rollback_id: str
    rollback_strategy: str  # AUTOMATIC_REVERT, STATE_RESTORE, MANUAL_ESCALATION
    rollback_action: str
    rollback_precondition: str
    rollback_verification: str
    is_reversible: bool = True
    rollback_hash: str = field(init=False)

    def __post_init__(self):
        raw = f"{self.rollback_id}:{self.rollback_strategy}:{self.rollback_action}:{self.rollback_verification}:{self.is_reversible}"
        self.rollback_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
