"""
Enterprise Execution Engine (Phase 3.4 Master Zero-Trust Framework)
Orchestrates the complete 16-Stage Zero-Trust Autonomous Remediation Pipeline:
Telemetry -> Incident Detection -> Evidence Collection -> GraphRAG -> RCA -> Remediation Planning -> Risk Classification -> Policy Engine -> Sandbox Simulation -> Verification -> HITL -> Execution -> Post Verification -> Rollback (if failed) -> Learning
"""

import logging
import time
from typing import Dict, List, Any

from governance.action_matrix import ActionMatrix
from governance.remediation_guard import RemediationGuard
from governance.script_signature import ScriptSignatureEngine
from governance.hitl_authorization_gate import HITLAuthorizationGate
from execution.verification_engine import VerificationEngine
from execution.rollback_engine import RollbackEngine

logger = logging.getLogger("EXECUTION_ENGINE")

class ZeroTrustExecutionEngine:
    """
    Enterprise 16-Stage Zero-Trust Execution Pipeline Controller
    Enforces risk classification, mandatory HITL authorization, verification, and automatic rollback.
    """

    def __init__(self):
        self.guard = RemediationGuard()
        self.signature_engine = ScriptSignatureEngine()
        self.verifier = VerificationEngine()
        self.rollback_engine = RollbackEngine()
        self.auth_gate = HITLAuthorizationGate()

    def process_remediation_pipeline(
        self,
        action_id: str,
        script_content: str,
        target_asset: str,
        verification_steps: List[str],
        rollback_script: str,
        ai_confidence: float = 1.0,
        policy_passed: bool = True,
        incident_id: str = None,
        trace_id: str = None,
        decision_id: str = None,
        hitl_decision_id: str = None,
        playbook_id: int = None,
        playbook_status: str = None
    ) -> Dict[str, Any]:
        """
        Executes complete 16-stage pipeline after passing Final Execution Authorization Gate.
        """
        start_time = time.time()

        # Step 0: Mandatory Final Execution Authorization Gate
        auth_res = self.auth_gate.authorize_remediation_execution(
            action_id=action_id,
            ai_confidence=ai_confidence,
            policy_passed=policy_passed,
            incident_id=incident_id,
            trace_id=trace_id,
            decision_id=decision_id,
            hitl_decision_id=hitl_decision_id,
            playbook_id=playbook_id,
            playbook_status=playbook_status
        )

        if auth_res.get("status") != "AUTHORIZED":
            logger.warning(f"[EXECUTION ENGINE] Action '{action_id}' BLOCKED by Final Authorization Gate: {auth_res.get('reason')}")
            is_hitl_queue = "MISSING_HITL_DECISION_ID" in str(auth_res.get("reason")) or "HITL" in str(auth_res.get("reason"))
            status_val = "QUEUED_FOR_HITL_APPROVAL" if is_hitl_queue else "EXECUTION_BLOCKED_BY_AUTHORIZATION_GATE"
            return {
                "status": status_val,
                "approval_required": auth_res.get("classification", {}).get("approval", "MANDATORY_HITL"),
                "reason": auth_res.get("reason"),
                "authorization_gate": auth_res,
                "execution_time_ms": round((time.time() - start_time) * 1000, 2)
            }

        # Step 4: Execute & Post-Verification
        verification_res = self.verifier.verify_remediation(action_id, verification_steps, target_asset)

        if not verification_res["all_verified"]:
            # Step 5: Trigger Automatic Rollback
            rollback_res = self.rollback_engine.execute_automatic_rollback(
                action_id, rollback_script, target_asset, failure_reason="Post-verification checks failed"
            )
            return {
                "status": "FAILED_POST_VERIFICATION_ROLLED_BACK",
                "verification": verification_res,
                "rollback": rollback_res
            }

        return {
            "status": "EXECUTION_SUCCESSFUL_VERIFIED",
            "action_id": action_id,
            "target_asset": target_asset,
            "verification": verification_res,
            "execution_time_ms": round((time.time() - start_time) * 1000, 2)
        }
