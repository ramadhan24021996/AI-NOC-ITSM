"""
Phase 4.1 Remediation Scoring Policy (phase4/remediation/remediation_scoring_policy.py)

Policy-controlled scoring weights fingerprint with SHA-256 policy_hash.
Prevents direct LLM override or alteration of scoring weights.
"""

import dataclasses
import hashlib
import json
import logging
from typing import Dict, Any

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("REMEDIATION_SCORING_POLICY")


@dataclasses.dataclass
class RemediationScoringPolicy:
    policy_version: str = "1.0.0"
    w_causal_fit: float = 0.30
    w_evidence_support: float = 0.25
    w_historical_success: float = 0.20
    w_counterfactual_delta: float = 0.15
    w_risk: float = 0.05
    w_blast_radius: float = 0.05
    max_risk: float = 0.80
    max_blast_radius: int = 5
    min_score: float = 0.40
    policy_hash: str = ""

    def __post_init__(self):
        if not self.policy_hash:
            raw = f"{self.policy_version}:{self.w_causal_fit}:{self.w_evidence_support}:{self.w_historical_success}:{self.w_counterfactual_delta}:{self.w_risk}:{self.w_blast_radius}:{self.max_risk}:{self.max_blast_radius}:{self.min_score}"
            self.policy_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def validate_policy_hash(self) -> bool:
        raw = f"{self.policy_version}:{self.w_causal_fit}:{self.w_evidence_support}:{self.w_historical_success}:{self.w_counterfactual_delta}:{self.w_risk}:{self.w_blast_radius}:{self.max_risk}:{self.max_blast_radius}:{self.min_score}"
        expected = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return self.policy_hash == expected
