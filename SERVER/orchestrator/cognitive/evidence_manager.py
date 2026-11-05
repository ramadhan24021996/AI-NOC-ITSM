"""
SERVER.orchestrator.cognitive.evidence_manager
===============================================
Component: Evidence Manager

Ranks and weights evidence sources (Telemetry, Memory, RAG, Conversation) to ensure
LLM consistency:
  - Telemetry: confidence 0.98
  - Memory: confidence 0.91
  - RAG: confidence 0.72
  - Conversation: confidence 0.60
Outputs EvidenceSummary.
"""
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List
from SERVER.contracts.schemas import EvidenceSummary

logger = logging.getLogger("orchestrator.cognitive.evidence")


class EvidenceManager:
    """
    Evaluates evidence sources and constructs weighted EvidenceSummary.
    """

    def evaluate(
        self,
        has_telemetry: bool,
        has_memory: bool,
        has_rag: bool,
        has_conversation: bool,
        rag_relevance: float = 0.72,
    ) -> EvidenceSummary:
        weights: Dict[str, float] = {}

        if has_telemetry:
            weights["Telemetry"] = 0.98
        if has_memory:
            weights["Memory"] = 0.91
        if has_rag:
            weights["RAG"] = max(0.40, min(0.95, rag_relevance))
        if has_conversation:
            weights["Conversation"] = 0.60

        if not weights:
            return EvidenceSummary(
                primary_evidence="Conversation",
                secondary_evidence="None",
                ignored_sources=[],
                weight_map={"Conversation": 0.50},
            )

        # Sort sources by weight descending
        sorted_sources = sorted(weights.items(), key=lambda x: x[1], reverse=True)
        primary = sorted_sources[0][0]
        secondary = sorted_sources[1][0] if len(sorted_sources) > 1 else "None"

        # Mark sources with weight < 0.50 as ignored
        ignored = [src for src, w in sorted_sources if w < 0.50]

        summary = EvidenceSummary(
            primary_evidence=primary,
            secondary_evidence=secondary,
            ignored_sources=ignored,
            weight_map=weights,
        )

        logger.debug(f"[EvidenceManager] Evaluated primary={primary} | secondary={secondary} | weights={weights}")
        return summary
