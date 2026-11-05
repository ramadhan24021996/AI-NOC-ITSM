"""
Phase 3.4: Forensic Why-Not Engine (phase3/rca/why_not_engine.py)

Generates machine-verifiable explanation for WHY each material alternative hypothesis was NOT confirmed.
Enforces Invariant #8 (INCONCLUSIVE != REFUTED) & Invariant #9 (REFUTED != CONFIRMED).
"""

import logging
from typing import Dict, Any, List
from phase3.hypothesis.hypothesis_competition_engine import HypothesisContract

logger = logging.getLogger("WHY_NOT_ENGINE")


class WhyNotEngine:
    @staticmethod
    def generate_why_not_explanations(alternatives: List[HypothesisContract], primary_posterior: float) -> List[Dict[str, Any]]:
        """
        Generates structured WHY-NOT explanations for each alternative candidate.
        Possible statuses: REFUTED, INCONCLUSIVE, SUPPORTED, INSUFFICIENT_EVIDENCE.
        """
        explanations = []

        for alt in alternatives:
            reason = []
            alt_status = alt.status

            if alt.status == "REFUTED":
                reason.append(f"Contradicting evidence count ({len(alt.contradicting_evidence)}) exceeded supporting evidence")
            elif alt.independent_sources_count < 2:
                alt_status = "INSUFFICIENT_EVIDENCE"
                reason.append(f"Independent evidence sources ({alt.independent_sources_count}) below minimum threshold (2)")
            elif alt.posterior_probability < 0.70:
                alt_status = "INCONCLUSIVE"
                reason.append(f"Posterior probability ({alt.posterior_probability}) below confirmation threshold (0.70)")
            else:
                margin = round(primary_posterior - alt.posterior_probability, 4)
                if margin < 0.30:
                    alt_status = "INCONCLUSIVE"
                    reason.append(f"Causal margin against primary candidate ({margin}) below threshold (0.30)")

            explanations.append({
                "hypothesis_id": alt.hypothesis_id,
                "candidate": alt.candidate,
                "posterior_probability": alt.posterior_probability,
                "status": alt_status,
                "independent_sources": alt.independent_sources_count,
                "supporting_count": len(alt.supporting_evidence),
                "contradicting_count": len(alt.contradicting_evidence),
                "reasons": reason
            })

        return explanations
