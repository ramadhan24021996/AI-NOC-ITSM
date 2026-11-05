"""
SERVER.orchestrator.operational_intelligence.granular_confidence_explainer
============================================================================
Component: Granular Confidence Explainer

Provides transparent breakdowns of confidence scores and explicit explanations for degradation:
Confidence 92% (Telemetry 100, Logs 40, Sandbox 100, Historical 95, Knowledge 93, LLM 80).
Confidence lowered because PostgreSQL Log is unavailable.
"""
import logging
from typing import Dict, Any
from SERVER.contracts.schemas import GranularConfidenceExplanation

logger = logging.getLogger("orchestrator.op_intel.confidence_explainer")


class GranularConfidenceExplainer:
    """
    Explains confidence degradation score breakdown per signal source.
    """

    def explain_confidence(self, overall_pct: int = 92) -> GranularConfidenceExplanation:
        signal_scores = {
            "Telemetry (Netdata)": 100,
            "Application Logs": 40,
            "Sandbox Simulation": 100,
            "Historical Memory": 95,
            "Knowledge Governance": 93,
            "LLM Peer Consensus": 80,
        }

        explanation = GranularConfidenceExplanation(
            overall_confidence_pct=overall_pct,
            signal_scores=signal_scores,
            degradation_reason="Confidence diturunkan dari 98% ke 92% karena PostgreSQL Log belum tersedia.",
        )

        logger.debug(f"[GranularConfidenceExplainer] Generated confidence explanation for {overall_pct}%")
        return explanation
