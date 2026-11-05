"""
Phase 3.6: Postcondition Verification Engine (phase3/remediation/postcondition_engine.py)

Enforces Invariant #28: Postcondition Failure != Success.
Exit code 0 DOES NOT constitute successful remediation if postconditions fail!
"""

import logging
from typing import Dict, Any, List

logger = logging.getLogger("POSTCONDITION_ENGINE")


class PostconditionEngine:
    @staticmethod
    def verify_postconditions(exit_code: int, postconditions: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Enforces Invariant #28: Checks exit_code and postcondition verification rules.
        """
        if exit_code != 0:
            logger.error(f"[POSTCONDITION FAILED] Execution exit code is {exit_code} != 0. Remediation FAILED.")
            return {"status": "FAILED", "success": False, "reason": f"NON_ZERO_EXIT_CODE_{exit_code}"}

        failed = []
        for post in postconditions:
            metric = post.get("metric_name", "UNNAMED_METRIC")
            actual = post.get("actual_value")
            target = post.get("target_value")

            if actual != target:
                failed.append(f"Postcondition metric '{metric}' failed: actual '{actual}' != target '{target}'")

        if failed:
            logger.error(f"[INVARIANT 28 VIOLATION DETECTED] Exit code was 0, BUT postcondition metrics failed: {failed}")
            return {
                "status": "FAILED",
                "success": False,
                "reason": "POSTCONDITION_METRIC_VERIFICATION_FAILED",
                "failed_postconditions": failed
            }

        logger.info("[POSTCONDITION PASSED] All postcondition metrics verified successfully!")
        return {
            "status": "SUCCESS",
            "success": True,
            "failed_postconditions": []
        }
