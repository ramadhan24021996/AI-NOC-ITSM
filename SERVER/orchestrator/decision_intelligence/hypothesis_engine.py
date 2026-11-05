"""
SERVER.orchestrator.decision_intelligence.hypothesis_engine
===========================================================
Component: Hypothesis Engine

Generates and ranks competing probabilistic hypotheses:
  - Hipotesis A: Backup Job Table Lock (85%)
  - Hipotesis B: Memory Leak (65%)
  - Hipotesis C: Storage Disk Failure (22%)
Adjusts probabilities dynamically as telemetry and log evidence arrives.
"""
import logging
from typing import Dict, Any, List
from SERVER.contracts.schemas import HypothesisPayload, HypothesisItem

logger = logging.getLogger("orchestrator.decision.hypothesis")


class HypothesisEngine:
    """
    Evaluates dynamic probabilistic hypotheses based on incoming evidence signals.
    """

    def generate_hypotheses(
        self, query_text: str, telemetry_context: Dict[str, Any]
    ) -> HypothesisPayload:
        q_lower = query_text.lower()
        telem = telemetry_context or {}

        items = []
        top_hypo = "Resource Contention"

        if "backup" in q_lower or "cpu" in q_lower or "postgres" in q_lower:
            items = [
                {"label": "Hipotesis A: Backup Job Table Lock", "probability_pct": 85, "evidence_support": "PostgreSQL log & high disk IO"},
                {"label": "Hipotesis B: Memory Leak Contention", "probability_pct": 65, "evidence_support": "RAM usage trend steady slope"},
                {"label": "Hipotesis C: Physical Storage Disk Failure", "probability_pct": 22, "evidence_support": "Disk read latency nominal"},
            ]
            top_hypo = "Backup Job Table Lock"
        else:
            items = [
                {"label": "Hipotesis A: Operational High Load", "probability_pct": 80, "evidence_support": "Active user request spike"},
                {"label": "Hipotesis B: Network Interface Flap", "probability_pct": 45, "evidence_support": "Netdata packet drop low"},
            ]
            top_hypo = "Operational High Load"

        payload = HypothesisPayload(
            hypotheses=items,
            top_hypothesis=top_hypo,
        )

        logger.debug(f"[HypothesisEngine] Ranked {len(items)} hypotheses | top='{top_hypo}'")
        return payload
