"""
Causal Scorer Module
Calculates causal evidence scores and ranks hypotheses based on counterfactual impact.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any
from .intervention import AgentIntervention


@dataclass
class HypothesisScore:
    rank: int
    variable_name: str
    agent_name: str
    confidence_pct: float     # e.g. 96.0 (96%)
    is_root_cause: bool
    explanation: str


class CausalScorer:
    def score_and_rank(self, interventions: List[AgentIntervention]) -> List[HypothesisScore]:
        """
        Ranks hypotheses by counterfactual impact score and primary symptom resolution.
        """
        scores: List[HypothesisScore] = []

        for item in interventions:
            res = item.result
            base_conf = 50.0

            if res.primary_symptom_resolved:
                base_conf += 35.0

            base_conf += (res.impact_score * 15.0)

            final_conf = min(99.0, round(base_conf, 1))

            expl = (
                f"Virtual intervention on [{item.target_variable}] by {item.agent_name} "
                f"resolved primary symptom (Resolved: {res.primary_symptom_resolved}, Impact: {int(res.impact_score * 100)}%)."
            )

            scores.append(HypothesisScore(
                rank=1,
                variable_name=item.target_variable,
                agent_name=item.agent_name,
                confidence_pct=final_conf,
                is_root_cause=res.is_root_cause_candidate,
                explanation=expl
            ))

        # Sort by confidence descending
        scores.sort(key=lambda x: x.confidence_pct, reverse=True)
        for idx, s in enumerate(scores, start=1):
            s.rank = idx

        return scores
