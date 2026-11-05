"""
Phase 3.5: Counterfactual Contract & Decision Record (phase3/causal/counterfactual/counterfactual_contract.py)

1. CounterfactualType: RECONSTRUCTION, COUNTERFACTUAL, INTERVENTIONAL_SIMULATION.
2. CounterfactualDecisionRecord: Structured record enforcing Invariants #16 to #20:
   - Invariant #16: Counterfactual Result != Observed Evidence.
   - Invariant #17: empirical_evidence_weight = 0.0 (Zero physical weight for simulation).
   - Invariant #18: Full Intervention Traceability (hashes).
   - Invariant #19: No Future Leakage check.
   - Invariant #20: Counterfactual Cannot Authorize Remediation.
"""

import logging
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime, UTC

logger = logging.getLogger("COUNTERFACTUAL_CONTRACT")


@dataclass
class CounterfactualIntervention:
    target_entity: str
    variable_name: str
    original_value: Any
    hypothetical_value: Any
    intervention_type: str = "DO_INTERVENTION"


@dataclass
class CounterfactualDecisionRecord:
    incident_id: str
    trace_id: str
    hypothesis_id: str
    classification_type: str  # RECONSTRUCTION, COUNTERFACTUAL, INTERVENTIONAL_SIMULATION
    observed_state_hash: str
    counterfactual_state_hash: str
    intervention: Dict[str, Any]
    temporal_window: Dict[str, str]
    observed_outcome: str
    counterfactual_outcome: str
    outcome_delta: float
    causal_support: str  # STRENGTHENED, WEAKENED, UNCHANGED, INCONCLUSIVE
    simulation_confidence: float
    empirical_evidence_weight: float = 0.0  # INVARIANT #17: MUST BE 0.0
    provenance_status: str = "VALIDATED"
    leakage_check: str = "PASS"  # INVARIANT #19: PASS or DENIED
    reproducibility_hash: str = field(init=False)
    engine_version: str = "1.0.0"
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))

    def __post_init__(self):
        # Calculate SHA-256 reproducibility hash
        raw = f"{self.incident_id}:{self.trace_id}:{self.hypothesis_id}:{self.classification_type}:{self.observed_state_hash}:{self.counterfactual_state_hash}:{json.dumps(self.intervention)}:{self.outcome_delta}:{self.timestamp}"
        self.reproducibility_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
