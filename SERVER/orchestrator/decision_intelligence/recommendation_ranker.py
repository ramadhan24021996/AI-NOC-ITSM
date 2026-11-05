"""
SERVER.orchestrator.decision_intelligence.recommendation_ranker
===============================================================
Component: Recommendation Ranker

Ranks candidate recommendations with confidence % and risk levels:
  1. Stop Backup (97%, Risk LOW)
  2. Throttle Backup (92%, Risk LOW)
  3. Restart PostgreSQL (64%, Risk MEDIUM)
  4. Restart Server (35%, Risk HIGH)
"""
import logging
from typing import List, Dict, Any
from SERVER.contracts.schemas import RecommendationRankedList, SolutionCandidate

logger = logging.getLogger("orchestrator.decision.ranker")


class RecommendationRanker:
    """
    Ranks solution candidates into a structured list for Dashboard UI presentation.
    """

    def rank_candidates(
        self, candidates: List[SolutionCandidate]
    ) -> RecommendationRankedList:
        sorted_cand = sorted(candidates, key=lambda c: (c.confidence_pct, -c.rank), reverse=True)

        item_dicts = []
        for c in sorted_cand:
            item_dicts.append({
                "rank": c.rank,
                "action_name": c.action_name,
                "confidence_pct": c.confidence_pct,
                "risk_level": c.risk_level,
                "has_rollback": c.has_rollback,
                "eta_seconds": c.eta_seconds,
            })

        primary_title = sorted_cand[0].action_name if sorted_cand else "No Recommendation"

        payload = RecommendationRankedList(
            candidates=item_dicts,
            primary_recommendation=primary_title,
        )

        logger.debug(f"[RecommendationRanker] Ranked {len(sorted_cand)} candidates | top='{primary_title}'")
        return payload
