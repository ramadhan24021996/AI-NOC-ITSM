"""
SERVER.orchestrator.protocol.confidence_divergence
===================================================
Component: Review Confidence & Divergence Evaluator

Evaluates confidence score divergence between AI NOC and Jarvis:
  AI NOC Confidence: 96% | Jarvis Review Confidence: 91% -> Delta: 5% -> Status: ACCEPT
  AI NOC Confidence: 96% | Jarvis Review Confidence: 58% -> Delta: 38% -> Status: REVIEW_REQUIRED
"""
import logging
from SERVER.contracts.schemas import ReviewConfidenceDivergence

logger = logging.getLogger("orchestrator.protocol.divergence")


class ReviewConfidenceDivergenceEvaluator:
    """
    Evaluates confidence score deltas between AI NOC raw confidence and Jarvis audit confidence.
    """

    def evaluate_divergence(
        self, ai_noc_confidence_pct: int = 96, jarvis_review_confidence_pct: int = 91
    ) -> ReviewConfidenceDivergence:
        delta = abs(ai_noc_confidence_pct - jarvis_review_confidence_pct)
        status = "ACCEPT" if delta <= 15 else "REVIEW_REQUIRED"

        div = ReviewConfidenceDivergence(
            ai_noc_confidence_pct=ai_noc_confidence_pct,
            jarvis_review_confidence_pct=jarvis_review_confidence_pct,
            divergence_delta_pct=delta,
            audit_status=status,
        )

        if status == "REVIEW_REQUIRED":
            logger.warning(
                f"[ReviewConfidenceDivergenceEvaluator] High confidence divergence detected! "
                f"NOC: {ai_noc_confidence_pct}% vs Jarvis: {jarvis_review_confidence_pct}% (Delta: {delta}%)"
            )
        else:
            logger.debug(f"[ReviewConfidenceDivergenceEvaluator] Confidence divergence ACCEPT (Delta: {delta}%)")

        return div
