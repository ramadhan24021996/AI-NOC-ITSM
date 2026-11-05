"""
Confidence Engine Module
Calculates multi-factor confidence scores for root cause hypotheses and ranks candidates.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Dict, Any
from .event_normalizer import NormalizedEvent
from .causal_inference import CausalChain


@dataclass
class HypothesisRank:
    rank: int
    candidate_event: NormalizedEvent
    confidence_score: float      # e.g. 0.96 (96%)
    reasoning: str


class ConfidenceEngine:
    def rank_hypotheses(self, causal_chain: CausalChain, events: List[NormalizedEvent]) -> List[HypothesisRank]:
        """
        Ranks root cause hypothesis candidates based on multi-factor scores.
        """
        ranks: List[HypothesisRank] = []
        sorted_events = sorted(events, key=lambda x: x.timestamp)

        for idx, evt in enumerate(sorted_events):
            m_val = evt.modality.value if isinstance(evt.modality, Enum) else str(evt.modality)
            base_score = 0.50

            # Factor 1: Earliest in timeline bonus (+0.25 max)
            if idx == 0:
                base_score += 0.25
            elif idx == 1:
                base_score += 0.15

            # Factor 2: Low-level layer precedence bonus (Hardware/Network/OS)
            if m_val in ["HARDWARE", "NETWORK"]:
                base_score += 0.20
            elif m_val in ["OS", "SECURITY"]:
                base_score += 0.10

            # Factor 3: Match with causal chain root event
            if evt.event_id == causal_chain.root_cause_event.event_id:
                base_score += 0.15

            final_conf = min(0.99, round(base_score, 2))
            reason = f"Ranked #{idx+1} based on temporal precedence (Time: {evt.timestamp[11:19]}), modality [{m_val}], and layer [{evt.layer}]."

            ranks.append(HypothesisRank(
                rank=idx + 1,
                candidate_event=evt,
                confidence_score=final_conf,
                reasoning=reason
            ))

        # Sort by confidence score descending
        ranks.sort(key=lambda x: x.confidence_score, reverse=True)
        for i, r in enumerate(ranks, start=1):
            r.rank = i

        return ranks
