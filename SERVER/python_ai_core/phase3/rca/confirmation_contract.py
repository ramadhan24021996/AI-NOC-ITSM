"""
Phase 3.4: Confirmation Contract & Forensic Decision Record (phase3/rca/confirmation_contract.py)

1. CausalConfirmationStatus: Mandatory status model (HYPOTHESIS, SUPPORTED, INCONCLUSIVE, REFUTED, CONFIRMED).
2. ConfirmationContract: Mandatory conditions for confirmation gate.
3. ForensicCausalDecisionRecord: Immutable decision record with SHA-256 integrity hash calculation.
"""

import logging
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime, UTC

logger = logging.getLogger("CONFIRMATION_CONTRACT")

VALID_STATUSES = {"HYPOTHESIS", "SUPPORTED", "INCONCLUSIVE", "REFUTED", "CONFIRMED"}


@dataclass
class ForensicCausalDecisionRecord:
    incident_id: str
    trace_id: str
    hypothesis_id: str
    candidate: str
    decision: str  # CONFIRMED, DENIED, INCONCLUSIVE, REFUTED
    decision_reason: str
    evidence_ids: List[str]
    independent_source_groups: List[str]
    temporal_analysis: Dict[str, Any]
    topology_analysis: Dict[str, Any]
    probe_results: List[Dict[str, Any]]
    contradictions: List[Dict[str, Any]]
    alternative_hypotheses: List[Dict[str, Any]]
    why_explanation: Dict[str, Any]
    why_not_explanation: Dict[str, Any]
    posterior_distribution: Dict[str, float]
    causal_margin: float
    counterfactual_status: str
    gate_results: Dict[str, bool]
    provenance_chain: Dict[str, Any]
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"))
    integrity_hash: str = field(init=False)

    def __post_init__(self):
        # Calculate SHA-256 integrity hash over all critical fields
        raw_payload = f"{self.incident_id}:{self.trace_id}:{self.hypothesis_id}:{self.candidate}:{self.decision}:{self.causal_margin}:{self.timestamp}:{json.dumps(self.evidence_ids)}:{json.dumps(self.independent_source_groups)}"
        self.integrity_hash = hashlib.sha256(raw_payload.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ConfirmationContract:
    hypothesis_id: str
    candidate: str
    effective_independent_sources: int
    provenance_complete: bool
    temporal_valid: bool
    topology_valid: bool
    contradiction_count: int
    posterior_probability: float
    causal_margin: float
    probes_satisfied: bool
    counterfactual_passed: bool

    def validate_mandatory_conditions(self) -> Dict[str, bool]:
        return {
            "C1_min_independent_sources": self.effective_independent_sources >= 2,
            "C2_provenance_complete": self.provenance_complete,
            "C3_temporal_precedence_valid": self.temporal_valid,
            "C4_topology_consistent": self.topology_valid,
            "C5_zero_material_contradiction": self.contradiction_count == 0,
            "C6_posterior_threshold": self.posterior_probability >= 0.70,
            "C7_causal_margin_threshold": self.causal_margin >= 0.30,
            "C8_diagnostic_probes_satisfied": self.probes_satisfied,
            "C9_counterfactual_satisfied": self.counterfactual_passed
        }
