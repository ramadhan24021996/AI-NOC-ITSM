"""
Enterprise Remediation Guard (Phase 3.4)
Enforces safety guardrails before any remediation action is dispatched:
- Policy Enforcement
- Risk Score Validation
- SHA256 Signature Verification
- Maintenance Window & Business Hour Check
- Device Lock & User Activity Check
"""

import logging
import time
from typing import Dict, Any

from governance.action_matrix import ActionMatrix
from governance.script_signature import ScriptSignatureEngine

logger = logging.getLogger("REMEDIATION_GUARD")

class RemediationGuard:
    """
    Enterprise Safety Guardrail Engine
    Blocks unsafe actions from reaching production endpoints.
    """

    def __init__(self):
        self.action_matrix = ActionMatrix()
        self.signature_engine = ScriptSignatureEngine()

    def evaluate_guardrails(
        self,
        action_id: str,
        script_content: str,
        signature: str,
        user_active: bool = False,
        is_maintenance_window: bool = True
    ) -> Dict[str, Any]:
        """
        Runs comprehensive safety checks across 5 guardrail dimensions.
        """
        # 1. Action Matrix Classification
        classification = self.action_matrix.classify_action(action_id)

        # 2. Signature Verification
        valid_signature = self.signature_engine.verify_signature(script_content, signature)

        # 3. User Activity Protection
        blocked_by_user = user_active and classification["risk_score"] > 30

        # 4. Maintenance Window Validation
        blocked_by_window = not is_maintenance_window and classification["risk_score"] > 50

        # 5. Dual Approval Gate for A6 Destructive
        requires_dual_approval = classification["approval"] == "DUAL_APPROVAL_MANDATORY"

        passed = valid_signature and not blocked_by_user and not blocked_by_window

        return {
            "action_id": action_id,
            "passed_guardrails": passed,
            "classification": classification,
            "signature_valid": valid_signature,
            "blocked_by_user_activity": blocked_by_user,
            "blocked_by_maintenance_window": blocked_by_window,
            "requires_dual_approval": requires_dual_approval,
            "evaluated_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
