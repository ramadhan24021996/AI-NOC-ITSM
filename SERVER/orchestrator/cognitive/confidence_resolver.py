"""
SERVER.orchestrator.cognitive.confidence_resolver
==================================================
Component: Confidence Resolver

Aggregates individual detector scores into a unified ConfidenceScorecard and gauge indicator:
  - GREEN: overall >= 0.85 (85%)
  - YELLOW: overall 0.60 - 0.84 (60-84%)
  - RED: overall < 0.60 (< 60%)
"""
import logging
from SERVER.contracts.schemas import ConfidenceScorecard, AIConfidenceGauge

logger = logging.getLogger("orchestrator.cognitive.confidence")


class ConfidenceResolver:
    """
    Computes system-wide overall confidence score and gauge state.
    """

    def resolve(
        self,
        intent_confidence: float = 0.98,
        tool_confidence: float = 0.95,
        knowledge_confidence: float = 0.85,
        evidence_primary_weight: float = 0.95,
    ) -> ConfidenceScorecard:
        # Weighted arithmetic mean
        overall = (
            (intent_confidence * 0.30)
            + (tool_confidence * 0.25)
            + (knowledge_confidence * 0.25)
            + (evidence_primary_weight * 0.20)
        )

        overall = max(0.10, min(0.99, overall))

        if overall >= 0.85:
            level = "GREEN"
        elif overall >= 0.60:
            level = "YELLOW"
        else:
            level = "RED"

        card = ConfidenceScorecard(
            overall_confidence=round(overall, 2),
            intent_confidence=round(intent_confidence, 2),
            tool_confidence=round(tool_confidence, 2),
            knowledge_confidence=round(knowledge_confidence, 2),
            level_label=level,
        )

        logger.debug(f"[ConfidenceResolver] Resolved overall={card.overall_confidence} | level={level}")
        return card

    def get_gauge(self, scorecard: ConfidenceScorecard) -> AIConfidenceGauge:
        pct = int(scorecard.overall_confidence * 100)
        return AIConfidenceGauge(score_pct=pct, color_indicator=scorecard.level_label)
