"""
Hypothesis Elimination Matrix Module
Tracks candidate hypotheses across probe iterations.
Maintains documented evidence, missing evidence, probe results, and status decisions:
ACCEPTED, REJECTED, UNKNOWN.
Rejected hypotheses are preserved in audit records (never silently discarded).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum


class HypothesisStatus(Enum):
    UNKNOWN = "UNKNOWN"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"


@dataclass
class HypothesisRecord:
    hypothesis_id: str
    variable_name: str
    description: str
    status: HypothesisStatus = HypothesisStatus.UNKNOWN
    supporting_evidence: List[str] = field(default_factory=list)
    missing_evidence: List[str] = field(default_factory=list)
    probes_executed: List[str] = field(default_factory=list)
    probe_results: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.50
    elimination_reason: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "hypothesis_id": self.hypothesis_id,
            "variable_name": self.variable_name,
            "description": self.description,
            "status": self.status.value,
            "supporting_evidence": self.supporting_evidence,
            "missing_evidence": self.missing_evidence,
            "probes_executed": self.probes_executed,
            "confidence": round(self.confidence, 3),
            "elimination_reason": self.elimination_reason
        }


class HypothesisEliminationMatrix:
    """Manages active hypotheses and enforces evidence-based elimination logic."""

    def __init__(self):
        self.matrix: Dict[str, HypothesisRecord] = {}

    def register_hypothesis(self, hypothesis_id: str, variable_name: str, description: str, missing_evidence: List[str]):
        if hypothesis_id not in self.matrix:
            self.matrix[hypothesis_id] = HypothesisRecord(
                hypothesis_id=hypothesis_id,
                variable_name=variable_name,
                description=description,
                missing_evidence=list(missing_evidence)
            )

    def record_probe_result(
        self,
        hypothesis_id: str,
        probe_id: str,
        probe_status: str,
        details: Dict[str, Any]
    ):
        record = self.matrix.get(hypothesis_id)
        if not record:
            return

        record.probes_executed.append(probe_id)
        record.probe_results.append({
            "probe_id": probe_id,
            "status": probe_status,
            "details": details
        })

        # Update evidence status
        if probe_status == "PASSED":
            # Normal probe execution confirms absence of anomaly or clears hypothesis
            record.status = HypothesisStatus.REJECTED
            record.confidence = 0.05
            record.elimination_reason = f"Diagnostic probe {probe_id} PASSED (normal execution confirmed; anomaly disproved)."
            record.supporting_evidence.append(f"Probe {probe_id} PASSED")
        elif probe_status == "FAILED":
            # Failed probe confirms anomaly
            record.status = HypothesisStatus.ACCEPTED
            record.confidence = 0.96
            record.supporting_evidence.append(f"Probe {probe_id} FAILED ({details.get('failure_reason', 'Anomaly detected')})")
            if probe_id in record.missing_evidence:
                record.missing_evidence.remove(probe_id)

    def get_accepted_hypotheses(self) -> List[HypothesisRecord]:
        return [h for h in self.matrix.values() if h.status == HypothesisStatus.ACCEPTED]

    def get_rejected_hypotheses(self) -> List[HypothesisRecord]:
        return [h for h in self.matrix.values() if h.status == HypothesisStatus.REJECTED]

    def get_unknown_hypotheses(self) -> List[HypothesisRecord]:
        return [h for h in self.matrix.values() if h.status == HypothesisStatus.UNKNOWN]

    def elimination_matrix_dict(self) -> Dict[str, Any]:
        return {
            "total_hypotheses": len(self.matrix),
            "accepted_count": len(self.get_accepted_hypotheses()),
            "rejected_count": len(self.get_rejected_hypotheses()),
            "unknown_count": len(self.get_unknown_hypotheses()),
            "matrix": [h.to_dict() for h in self.matrix.values()]
        }
