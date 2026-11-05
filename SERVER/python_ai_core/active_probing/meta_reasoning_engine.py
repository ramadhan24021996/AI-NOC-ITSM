"""
Meta-Reasoning Engine Module
Self-reflective AI reasoning evaluator:
Evaluates reasoning process for bias, overconfidence, over-reliance on GraphRAG, or insufficient diagnostic evidence.
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class MetaReasoningAuditReport:
    is_reasoning_sound: bool
    bias_detected: bool
    overconfidence_flag: bool
    graphrag_dominance_pct: float
    reflection_summary: str


class MetaReasoningEngine:
    """Evaluates the internal reasoning process to detect bias and prevent overconfidence."""

    def evaluate_reasoning_quality(
        self,
        hypothesis_confidence: float,
        probes_executed_count: int,
        graphrag_similarity_weight: float
    ) -> MetaReasoningAuditReport:

        bias = False
        overconfidence = False

        # Overconfidence check: High confidence with zero active probes executed
        if hypothesis_confidence > 0.90 and probes_executed_count == 0:
            overconfidence = True
            bias = True

        # GraphRAG dominance check
        if graphrag_similarity_weight > 0.85 and probes_executed_count == 0:
            bias = True

        sound = not (overconfidence or (hypothesis_confidence > 0.85 and graphrag_similarity_weight > 0.85 and probes_executed_count == 0))

        summary = (
            f"Meta-Reasoning Self-Reflection: Soundness={'VALIDATED' if sound else 'BIAS_DETECTED'}. "
            f"Overconfidence={'YES (Probing Required)' if overconfidence else 'NO'}. "
            f"GraphRAG Dominance={round(graphrag_similarity_weight*100,1)}%."
        )

        return MetaReasoningAuditReport(
            is_reasoning_sound=sound,
            bias_detected=bias,
            overconfidence_flag=overconfidence,
            graphrag_dominance_pct=round(graphrag_similarity_weight * 100.0, 1),
            reflection_summary=summary
        )
