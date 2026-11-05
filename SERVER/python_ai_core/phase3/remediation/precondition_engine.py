"""
Phase 3.6: Precondition Engine (phase3/remediation/precondition_engine.py)

Enforces Invariant #23 (Precondition Required & Validated).
Evaluates system preconditions before execution authorization can be granted.
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger("PRECONDITION_ENGINE")


class PreconditionEngine:
    @staticmethod
    def evaluate_preconditions(preconditions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Evaluates precondition rules.
        """
        if not preconditions:
            logger.error("[PRECONDITION ERROR] No preconditions provided! DENIED.")
            return {"status": "FAILED", "all_passed": False, "failed_conditions": ["NO_PRECONDITIONS_PROVIDED"]}

        failed = []
        for cond in preconditions:
            name = cond.get("name", "UNNAMED_COND")
            val = cond.get("check_value", True)
            expected = cond.get("expected_value", True)

            if val != expected:
                failed.append(f"Precondition '{name}' check failed: actual '{val}' != expected '{expected}'")

        all_passed = (len(failed) == 0)
        return {
            "status": "PASS" if all_passed else "PRECONDITION_FAILED",
            "all_passed": all_passed,
            "failed_conditions": failed
        }
