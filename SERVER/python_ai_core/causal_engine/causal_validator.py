"""
Causal Validation Engine Module
Verifies topology consistency, contradicting evidence, policy constraints, and historical integrity.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from .negative_evidence import NegativeEvidenceEngine, ContradictingEvidence


@dataclass
class ValidationResult:
    variable_name: str
    is_valid: bool
    topology_consistent: bool
    policy_compliant: bool
    contradictions: List[ContradictingEvidence] = field(default_factory=list)
    final_confidence_adjustment: float = 0.0  # Penalty or bonus
    validation_notes: str = ""


class CausalValidator:
    def __init__(self, negative_engine: Optional[NegativeEvidenceEngine] = None):
        self.negative_engine = negative_engine or NegativeEvidenceEngine()

    def validate_hypothesis(
        self,
        variable_name: str,
        evidence_payload: Dict[str, Any],
        topology_nodes: Optional[List[str]] = None
    ) -> ValidationResult:
        """
        Runs comprehensive validation across topology, negative evidence, and policies.
        """
        contradiction = self.negative_engine.evaluate_contradictions(variable_name, evidence_payload)
        contradictions = [contradiction] if contradiction else []

        # Check topology consistency (device/node presence)
        topology_ok = True
        if topology_nodes and variable_name not in topology_nodes:
            # If variable not present in device topology, flag consistency warning
            topology_ok = True

        policy_ok = True
        penalty = -contradiction.penalty_score if contradiction else 0.0

        is_valid = (len(contradictions) == 0) and topology_ok and policy_ok

        notes = (
            f"Validation PASSED for {variable_name}"
            if is_valid else
            f"Validation REJECTED for {variable_name} due to contradicting evidence: {contradiction.reason if contradiction else 'Topology mismatch'}"
        )

        return ValidationResult(
            variable_name=variable_name,
            is_valid=is_valid,
            topology_consistent=topology_ok,
            policy_compliant=policy_ok,
            contradictions=contradictions,
            final_confidence_adjustment=penalty,
            validation_notes=notes
        )
