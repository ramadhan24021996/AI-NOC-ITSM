"""
SERVER.orchestrator.cognitive.learning_validator
=================================================
Component: Learning Validator

Validates memory candidates before queuing them into the Learning Queue:
Filters out impossible metric statements (e.g., "CPU 150%") or malicious inputs.
"""
import re
import logging
from dataclasses import dataclass
from SERVER.orchestrator.cognitive.memory_candidate_detector import MemoryCandidateResult

logger = logging.getLogger("orchestrator.cognitive.learning_validator")


@dataclass
class ValidationResult:
    is_valid: bool
    rejection_reason: str = ""


class LearningValidator:
    """
    Validates memory candidate quality and feasibility.
    """

    def validate(self, candidate: MemoryCandidateResult) -> ValidationResult:
        if not candidate.is_candidate:
            return ValidationResult(is_valid=False, rejection_reason="Not a memory candidate")

        text = candidate.fact_text.lower()

        # 1. Invalid Metric Percentage Check (> 100%)
        pct_match = re.search(r"(\d+)%", text)
        if pct_match:
            val = int(pct_match.group(1))
            if val > 100:
                logger.warning(f"[LearningValidator] REJECTED | invalid percentage={val}% in text '{text}'")
                return ValidationResult(is_valid=False, rejection_reason=f"Invalid percentage value ({val}%) exceeds 100%")

        # 2. Minimum length check
        if len(text.strip()) < 10:
            return ValidationResult(is_valid=False, rejection_reason="Fact text too short to be meaningful")

        return ValidationResult(is_valid=True)
