"""
Causal Explainer Module
Generates human-understandable natural language explanations for NOC operators
based on counterfactual simulation results.
"""

from typing import List, Dict, Any
from .causal_score import HypothesisScore


class CausalExplainer:
    @staticmethod
    def explain(top_score: HypothesisScore, all_scores: List[HypothesisScore]) -> str:
        """
        Generates human explanation comparing top hypothesis vs rejected hypotheses.
        """
        lines = [
            f"=== ENTERPRISE CAUSAL REASONING EXPLANATION ===",
            f"Primary Root Cause Identified: [{top_score.variable_name}] (Confidence: {top_score.confidence_pct}%)",
            f"Investigating Agent: {top_score.agent_name}",
            f"Rationale: If [{top_score.variable_name}] is set to NORMAL via do-operator intervention, downstream application/POS errors resolve completely.",
            "",
            "Counterfactual Comparison:"
        ]

        for s in all_scores:
            status = "CONFIRMED ROOT CAUSE" if s.is_root_cause else "REJECTED (Secondary Symptom / Non-Causal)"
            lines.append(f"  • [{s.variable_name}] ({s.agent_name}): Confidence {s.confidence_pct}% -> {status}")

        lines.append("")
        lines.append("Recommendation: Focus remediation on restoring " + top_score.variable_name + " rather than downstream application/printer components.")

        return "\n".join(lines)
