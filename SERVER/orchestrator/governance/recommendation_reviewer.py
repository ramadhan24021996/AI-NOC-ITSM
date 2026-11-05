"""
SERVER.orchestrator.governance.recommendation_reviewer
======================================================
Component: Recommendation Reviewer

Conducts pre-flight review of recommendations checking safety, speed, and downtime reduction.
"""
import logging
from typing import Dict, Any, List
from SERVER.contracts.schemas import SolutionCandidate

logger = logging.getLogger("orchestrator.governance.reviewer")


class RecommendationReviewer:
    """
    Audits recommendations for downtime minimization and safety.
    """

    def review_recommendations(
        self, candidates: List[SolutionCandidate]
    ) -> List[SolutionCandidate]:
        reviewed = []
        for c in candidates:
            # Downgrade unsafe or high downtime options
            if c.risk_level == "HIGH" or c.eta_seconds > 180:
                c.confidence_pct = max(10, c.confidence_pct - 30)
            reviewed.append(c)

        logger.debug(f"[RecommendationReviewer] Reviewed {len(reviewed)} candidate recommendations.")
        return sorted(reviewed, key=lambda x: x.confidence_pct, reverse=True)
