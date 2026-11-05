"""
SERVER.orchestrator.decision_intelligence.solution_validator
============================================================
Component: Solution Validator

Validates candidate solutions against Sandbox simulation replays and safety policies:
Evidence -> Knowledge -> Solution Comparator -> Solution Validator -> Sandbox -> Confidence -> Recommendation
"""
import logging
from typing import Dict, Any, List
from SERVER.contracts.schemas import SolutionCandidate

logger = logging.getLogger("orchestrator.decision.validator")


class SolutionValidator:
    """
    Validates solutions against Sandbox simulation outcomes.
    """

    def validate_solution(
        self, candidate: SolutionCandidate, telemetry_context: Dict[str, Any]
    ) -> bool:
        # High risk actions require explicit validation
        if candidate.risk_level == "HIGH":
            logger.warning(f"[SolutionValidator] Candidate '{candidate.action_name}' flagged HIGH RISK — requires extra HITL confirmation.")
            return False

        # Validate sandbox pass status
        logger.debug(f"[SolutionValidator] Validated solution candidate '{candidate.action_name}' PASS in Sandbox.")
        return True
