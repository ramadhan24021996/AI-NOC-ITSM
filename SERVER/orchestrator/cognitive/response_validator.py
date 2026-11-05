"""
SERVER.orchestrator.cognitive.response_validator
================================================
Component: Response Validator

Pre-output validation gate before output display or TTS generation:
Ensures LLM does not claim actions were performed when tools were not executed.
"""
import re
import logging
from dataclasses import dataclass

logger = logging.getLogger("orchestrator.cognitive.response_validator")


@dataclass
class ResponseValidationResult:
    is_valid: bool
    validated_response: str
    action_intercepted: bool = False


class ResponseValidator:
    """
    Validates output text against actual execution status.
    """

    def validate(self, response_text: str, tools_executed: bool = False) -> ResponseValidationResult:
        text = response_text

        # Check if text asserts action execution (e.g., "telah direstart", "telah dieksekusi", "restarted")
        execution_patterns = [
            r"\b(telah|sudah)\s+(direstart|dieksekusi|diclear|dibersihkan|diisolasi)\b",
            r"\b(successfully|telah berhasil)\s+(restarted|executed|cleared)\b",
        ]

        has_execution_claim = any(re.search(p, text.lower()) for p in execution_patterns)

        if has_execution_claim and not tools_executed:
            logger.warning("[ResponseValidator] Intercepted false action claim in response text.")

            # Rewrite false assertion to recommendation waiting for approval
            rewritten = (
                "Saya merekomendasikan tindakan tersebut. Tindakan belum dilakukan dan menunggu approval operator."
            )
            return ResponseValidationResult(
                is_valid=False,
                validated_response=rewritten,
                action_intercepted=True,
            )

        return ResponseValidationResult(is_valid=True, validated_response=text)
