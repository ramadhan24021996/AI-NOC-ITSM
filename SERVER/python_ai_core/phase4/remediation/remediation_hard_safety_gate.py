"""
Phase 4.1 Remediation Hard Safety Gate (phase4/remediation/remediation_hard_safety_gate.py)

Enforces INVARIANT #29 (Safety Precedes Optimization).
Evaluates 9 Hard Safety Checks BEFORE scoring:
1. Confirmed Cause
2. Registered Action
3. Valid Contract
4. Preconditions Defined
5. Risk <= 0.80
6. Blast Radius <= Policy
7. Rollback Contract Available (Pure Safety Requirement!)
8. Postconditions Defined
9. Provenance Complete

If any check fails, candidate status is set to ELIMINATED with an explicit elimination_reason.
"""

import logging
from typing import Dict, Any, Tuple, List, Optional
from phase3.remediation.remediation_contract import RemediationContract
from phase4.remediation.remediation_scoring_policy import RemediationScoringPolicy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("REMEDIATION_HARD_SAFETY_GATE")


class RemediationHardSafetyGate:
    def __init__(self, policy: Optional[RemediationScoringPolicy] = None):
        self.policy = policy or RemediationScoringPolicy()

    def evaluate_safety_gate(self, contract: RemediationContract, action_registered: bool = True) -> Tuple[bool, str, List[str]]:
        """
        Evaluates 9 Hard Safety Checks on a remediation candidate BEFORE scoring.
        Returns: (pass_safety, safety_status, list_of_violations)
        """
        violations = []

        # 1. Confirmed Cause Status Check
        if contract.cause_status != "CONFIRMED":
            violations.append(f"Cause status '{contract.cause_status}' != CONFIRMED")

        # 2. Registered Action ID Check
        if not action_registered:
            violations.append("Action ID is NOT registered in ActionRegistry")

        # 3. Valid Contract Schema Check
        if not contract.contract_id or not contract.action_definition:
            violations.append("Invalid contract schema (Missing ID or action definition)")

        # 4. Preconditions Defined Check
        if not contract.preconditions:
            violations.append("Preconditions list is EMPTY")

        # 5. Risk Score Limit Check (Max: 0.80)
        if contract.risk_score > self.policy.max_risk:
            violations.append(f"Risk score '{contract.risk_score}' > policy max '{self.policy.max_risk}'")

        # 6. Blast Radius Limit Check
        affected = contract.blast_radius.get("max_affected_nodes", 1)
        if affected > self.policy.max_blast_radius:
            violations.append(f"Blast radius affected nodes '{affected}' > policy max '{self.policy.max_blast_radius}'")

        # 7. Rollback Contract Available Check (Pure Safety Requirement!)
        if not contract.rollback_contract or not contract.reversibility:
            violations.append("Rollback contract unavailable or action irreversibility flag set to False")

        # 8. Postconditions Defined Check
        if not contract.postconditions:
            violations.append("Postconditions list is EMPTY")

        # 9. Provenance Complete Check
        if not contract.trace_id or not contract.incident_id:
            violations.append("Missing trace_id or incident_id in contract provenance")

        if violations:
            reason = f"SAFETY_GATE_FAILED: {'; '.join(violations)}"
            logger.warning(f"[HARD SAFETY REJECT] Candidate '{contract.contract_id}' ELIMINATED! Violations: {violations}")
            return False, "ELIMINATED", violations

        logger.info(f"[HARD SAFETY PASS] Candidate '{contract.contract_id}' PASSED all 9 Hard Safety Checks!")
        return True, "PASS_SAFETY", []
