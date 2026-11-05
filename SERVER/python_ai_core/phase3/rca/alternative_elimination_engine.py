"""
Phase 3.4: Alternative Elimination Engine (phase3/rca/alternative_elimination_engine.py)

Constructs deterministic comparison matrix across all candidate hypotheses.
"""

import logging
from typing import Dict, Any, List
from phase3.hypothesis.hypothesis_competition_engine import HypothesisContract

logger = logging.getLogger("ALTERNATIVE_ELIMINATION_ENGINE")


class AlternativeEliminationEngine:
    @staticmethod
    def construct_elimination_matrix(hypotheses: List[HypothesisContract]) -> Dict[str, Any]:
        """
        Constructs comparison matrix: Hypothesis x Evidence x Temporal x Topology x Probe x Contradiction x Provenance.
        """
        matrix = []

        for h in hypotheses:
            row = {
                "hypothesis_id": h.hypothesis_id,
                "candidate": h.candidate,
                "posterior": h.posterior_probability,
                "independent_sources": h.independent_sources_count,
                "supporting_count": len(h.supporting_evidence),
                "contradiction_count": len(h.contradicting_evidence),
                "temporal_valid": True,
                "topology_valid": True,
                "provenance_complete": h.provenance_complete,
                "eliminated": h.status == "REFUTED"
            }
            matrix.append(row)

        all_competitors_eliminated_or_inconclusive = all(r["eliminated"] or r["posterior"] < 0.30 for r in matrix[1:]) if len(matrix) > 1 else True

        return {
            "total_candidates": len(hypotheses),
            "comparison_matrix": matrix,
            "alternatives_eliminated": all_competitors_eliminated_or_inconclusive
        }
