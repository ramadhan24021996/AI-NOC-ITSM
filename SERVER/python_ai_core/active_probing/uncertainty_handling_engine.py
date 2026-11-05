"""
Uncertainty Handling Engine Module
Evaluates confidence thresholds and handles low-certainty states:
When confidence < 50%, triggers structured fallback:
- Refuses speculative RCA generation
- Requests additional diagnostic probes
- Flags incident for senior human engineer verification
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class UncertaintyEvaluationResult:
    confidence_score: float
    confidence_acceptable: bool
    refusal_triggered: bool
    action_recommendation: str
    fallback_message: Optional[str]


class UncertaintyHandlingEngine:
    """Enforces uncertainty safety boundaries and non-guessing policies."""

    def evaluate_confidence_certainty(
        self,
        confidence_score: float,
        probes_executed_count: int,
        safe_probes_remaining: bool = True
    ) -> UncertaintyEvaluationResult:

        # Thresholds
        ACCEPTABLE_THRESHOLD = 0.70
        CRITICAL_REFUSAL_THRESHOLD = 0.50

        if confidence_score >= ACCEPTABLE_THRESHOLD:
            return UncertaintyEvaluationResult(
                confidence_score=confidence_score,
                confidence_acceptable=True,
                refusal_triggered=False,
                action_recommendation="PROCEED_WITH_RCA",
                fallback_message=None
            )

        if safe_probes_remaining and probes_executed_count < 10:
            return UncertaintyEvaluationResult(
                confidence_score=confidence_score,
                confidence_acceptable=False,
                refusal_triggered=False,
                action_recommendation="EXECUTE_ADDITIONAL_PROBES",
                fallback_message=f"Confidence ({round(confidence_score*100,1)}%) below target threshold (70%); additional probes requested."
            )

        # Confidence < 50% without remaining safe probes -> Refusal
        return UncertaintyEvaluationResult(
            confidence_score=confidence_score,
            confidence_acceptable=False,
            refusal_triggered=True,
            action_recommendation="REFUSE_RCA_FLAG_HUMAN_REVIEW",
            fallback_message="Additional Active Diagnostic Probing Required. Evidence insufficient for automated RCA."
        )
