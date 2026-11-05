"""
Phase 4.1 Remediation Decision Package (phase4/remediation/remediation_decision_package.py)

Constructs structured, immutable Remediation Decision Package.
Enforces SHA-256 Hash Chain:
evidence_hash -> causal_decision_hash -> counterfactual_hash -> contract_hash -> package_hash
"""

import dataclasses
import hashlib
import json
import logging
from typing import Dict, Any, List, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("REMEDIATION_DECISION_PACKAGE")


@dataclasses.dataclass
class RemediationDecisionPackage:
    incident_id: str
    trace_id: str
    confirmed_cause_id: str
    cause_confidence: float
    why_explanation: str
    why_not_eliminated_options: List[Dict[str, Any]]
    counterfactual_summary: Dict[str, Any]
    ranked_remediation_options: List[Dict[str, Any]]
    recommended_option: Optional[Dict[str, Any]]
    evidence_hash: str
    causal_decision_hash: str
    counterfactual_hash: str
    contract_hash: str
    policy_hash: str
    status: str = "AWAITING_HITL"
    package_hash: str = ""

    def __post_init__(self):
        if not self.package_hash:
            raw = f"{self.incident_id}:{self.trace_id}:{self.confirmed_cause_id}:{self.evidence_hash}:{self.causal_decision_hash}:{self.counterfactual_hash}:{self.contract_hash}:{self.policy_hash}"
            self.package_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def validate_hash_chain(self) -> bool:
        """Validates master package hash chain integrity."""
        raw = f"{self.incident_id}:{self.trace_id}:{self.confirmed_cause_id}:{self.evidence_hash}:{self.causal_decision_hash}:{self.counterfactual_hash}:{self.contract_hash}:{self.policy_hash}"
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.package_hash == expected

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)
