"""
Shadow Mode Module
Evaluates AI recommendations silently against human operator actions without executing automated remediation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone


@dataclass
class ShadowEvaluationRecord:
    incident_id: str
    timestamp: str
    ai_root_cause: str
    ai_confidence: float
    human_operator_root_cause: Optional[str] = None
    matches_human_decision: bool = False


class ShadowModeEngine:
    def __init__(self):
        self.records: List[ShadowEvaluationRecord] = []

    def log_recommendation(self, incident_id: str, ai_root_cause: str, ai_confidence: float) -> ShadowEvaluationRecord:
        """
        Logs silent shadow recommendation.
        """
        rec = ShadowEvaluationRecord(
            incident_id=incident_id,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            ai_root_cause=ai_root_cause,
            ai_confidence=ai_confidence
        )
        self.records.append(rec)
        return rec

    def compare_with_operator(self, incident_id: str, human_root_cause: str) -> Optional[ShadowEvaluationRecord]:
        """
        Compares AI recommendation with human operator's actual resolution.
        """
        for rec in self.records:
            if rec.incident_id == incident_id:
                rec.human_operator_root_cause = human_root_cause
                rec.matches_human_decision = (rec.ai_root_cause == human_root_cause)
                return rec
        return None

    def get_shadow_precision_rate(self) -> float:
        """
        Calculates precision rate (% match with human operator decisions).
        """
        evaluated = [r for r in self.records if r.human_operator_root_cause is not None]
        if not evaluated:
            return 100.0
        matches = [r for r in evaluated if r.matches_human_decision]
        return round(float(len(matches)) / float(len(evaluated)) * 100.0, 1)
