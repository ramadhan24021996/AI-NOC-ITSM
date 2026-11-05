"""
SERVER.orchestrator.decision_intelligence.evidence_weighter
===========================================================
Component: Evidence Weight Engine

Enforces strict empirical evidence weighting to eliminate LLM hallucinations:
  - Sandbox PASS: 40%
  - Netdata Telemetry: 30%
  - Go Host Agent: 15%
  - Historical Incident: 10%
  - LLM Reasoning: 5%
"""
import logging
from typing import Dict, Any
from SERVER.contracts.schemas import WeightedEvidencePayload

logger = logging.getLogger("orchestrator.decision.weighter")


class EvidenceWeightEngine:
    """
    Computes weighted confidence score based on strict empirical evidence hierarchy.
    """

    def compute_weighted_confidence(
        self,
        sandbox_pass: bool = True,
        netdata_active: bool = True,
        agent_active: bool = True,
        historical_match: bool = True,
        llm_confidence: float = 0.90,
    ) -> WeightedEvidencePayload:
        sandbox_pct = 40 if sandbox_pass else 0
        netdata_pct = 30 if netdata_active else 0
        agent_pct = 15 if agent_active else 0
        history_pct = 10 if historical_match else 0
        llm_pct = int(llm_confidence * 5)

        total_confidence = sandbox_pct + netdata_pct + agent_pct + history_pct + llm_pct

        payload = WeightedEvidencePayload(
            sandbox_weight_pct=40,
            netdata_weight_pct=30,
            agent_weight_pct=15,
            historical_weight_pct=10,
            llm_weight_pct=5,
            calculated_confidence_pct=total_confidence,
        )

        logger.debug(f"[EvidenceWeightEngine] Weighted confidence calculated: {total_confidence}% (LLM weight: {llm_pct}%)")
        return payload
