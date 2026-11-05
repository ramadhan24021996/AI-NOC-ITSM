"""
SERVER.orchestrator.governance.cross_validator
===============================================
Component: Cross Validation Engine

Cross-validates evidence signals across 6 independent sources:
Netdata, Go Agent, Docker, Sandbox, Knowledge, and LLM.
Calculates consensus % (e.g., 97% vs 52%).
"""
import logging
from typing import Dict, Any, List
from SERVER.contracts.schemas import CrossValidationMatrix

logger = logging.getLogger("orchestrator.governance.cross_validator")


class CrossValidationEngine:
    """
    Validates signal agreement across multiple empirical and AI data sources.
    """

    def validate_signals(
        self,
        netdata_yes: bool = True,
        agent_yes: bool = True,
        docker_yes: bool = True,
        sandbox_yes: bool = True,
        knowledge_yes: bool = True,
        llm_yes: bool = True,
    ) -> CrossValidationMatrix:
        sources = ["Netdata", "Go Agent", "Docker", "Sandbox", "Knowledge", "LLM"]
        signals = [netdata_yes, agent_yes, docker_yes, sandbox_yes, knowledge_yes, llm_yes]

        matches = sum(1 for s in signals if s)
        consensus_pct = int((matches / len(signals)) * 100)

        has_conflict = consensus_pct < 70
        status = "VERIFIED" if consensus_pct >= 85 else ("NEED_INVESTIGATION" if has_conflict else "PARTIAL_MATCH")

        matrix = CrossValidationMatrix(
            sources_checked=sources,
            consensus_pct=consensus_pct,
            has_conflict=has_conflict,
            validation_status=status,
        )

        logger.debug(f"[CrossValidationEngine] Cross validation consensus: {consensus_pct}% | status={status}")
        return matrix
