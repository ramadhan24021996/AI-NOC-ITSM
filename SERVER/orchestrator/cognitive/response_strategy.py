"""
SERVER.orchestrator.cognitive.response_strategy
================================================
Component: Response Strategy Manager

Manages persona framing and prompt management for output presentation:
  - Persona "Senior Engineer" -> In-depth technical breakdown & RCA
  - Persona "Executive" -> High-level executive summary & business impact
"""
import logging
from typing import Dict, Any

logger = logging.getLogger("orchestrator.cognitive.response_strategy")


class ResponseStrategyManager:
    """
    Applies persona strategy to format final user responses.
    """

    def apply_persona(self, answer_text: str, user_role: str = "NOC Engineer") -> str:
        role_lower = user_role.lower()

        if "executive" in role_lower or "manager" in role_lower or "c-level" in role_lower:
            persona_prefix = "[EXECUTIVE SUMMARY]\n"
            formatted = f"{persona_prefix}{answer_text}"
        else:
            # Default to Senior Systems Engineer persona
            persona_prefix = "[SENIOR ENGINEER ANALYSIS]\n"
            formatted = f"{persona_prefix}{answer_text}"

        logger.debug(f"[ResponseStrategyManager] Applied persona for role={user_role}")
        return formatted
