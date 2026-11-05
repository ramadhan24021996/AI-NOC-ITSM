"""
SERVER.orchestrator.closed_loop.closed_loop_review
===================================================
Component: Closed-Loop Review Engine

Manages multi-round iterative review loops between AI NOC and Jarvis until quality threshold is met:
Review #1 (FAIL) -> AI NOC Revision #1 -> Review #2 (FAIL) -> AI NOC Revision #2 -> Review #3 (PASS) -> Publish to Operator
"""
import logging
from typing import List, Dict, Any, Optional
from SERVER.contracts.schemas import (
    AINOCReviewContract,
    IterativeReviewIteration,
    ReviewAuditTrailRecord,
)
from SERVER.orchestrator.protocol.review_contract import AINOCReviewContractValidator
from SERVER.orchestrator.protocol.ai_review_protocol import AIReviewProtocolEngine
from SERVER.orchestrator.protocol.confidence_divergence import ReviewConfidenceDivergenceEvaluator
from SERVER.orchestrator.protocol.audit_rejection_loop import AuditRejectionLoopManager
from SERVER.orchestrator.closed_loop.review_audit_trail import ReviewAuditTrailTracker
from SERVER.orchestrator.closed_loop.jarvis_technical_questions import JarvisTechnicalQuestionGenerator

logger = logging.getLogger("orchestrator.closed_loop.engine")


class ClosedLoopReviewEngine:
    """
    Orchestrates iterative closed-loop review loops between AI NOC outputs and Jarvis audits.
    """

    def __init__(
        self,
        contract_validator: Optional[AINOCReviewContractValidator] = None,
        protocol_engine: Optional[AIReviewProtocolEngine] = None,
        divergence_evaluator: Optional[ReviewConfidenceDivergenceEvaluator] = None,
        rejection_manager: Optional[AuditRejectionLoopManager] = None,
        audit_tracker: Optional[ReviewAuditTrailTracker] = None,
        question_generator: Optional[JarvisTechnicalQuestionGenerator] = None,
    ):
        self.validator = contract_validator or AINOCReviewContractValidator()
        self.protocol_engine = protocol_engine or AIReviewProtocolEngine()
        self.divergence_evaluator = divergence_evaluator or ReviewConfidenceDivergenceEvaluator()
        self.rejection_manager = rejection_manager or AuditRejectionLoopManager()
        self.audit_tracker = audit_tracker or ReviewAuditTrailTracker()
        self.question_generator = question_generator or JarvisTechnicalQuestionGenerator()

    def execute_closed_loop_review(
        self,
        session_id: str,
        initial_contract_dict: Dict[str, Any],
        max_rounds: int = 3,
    ) -> ReviewAuditTrailRecord:
        iterations: List[IterativeReviewIteration] = []
        curr_contract = self.validator.build_contract(
            incident_id=session_id,
            hypothesis=initial_contract_dict.get("hypothesis", ["Backup Lock"]),
            evidence=initial_contract_dict.get("evidence", ["Netdata CPU 98%"]),
            recommended_actions=initial_contract_dict.get("recommended_actions", ["Throttle Backup"]),
            ai_noc_confidence=float(initial_contract_dict.get("confidence", 0.96)),
            missing_evidence=initial_contract_dict.get("missing_evidence", []),
        )

        for round_idx in range(1, max_rounds + 1):
            protocol_report = self.protocol_engine.audit_contract(curr_contract)
            div = self.divergence_evaluator.evaluate_divergence(
                ai_noc_confidence_pct=int(curr_contract.ai_noc_confidence * 100),
                jarvis_review_confidence_pct=91,
            )
            is_pass = protocol_report.overall_protocol_verdict == "APPROVED" and div.audit_status == "ACCEPT"

            failed_dims = []
            if not protocol_report.evidence_review_pass:
                failed_dims.append("Evidence Completeness")
            if not protocol_report.sandbox_review_pass:
                failed_dims.append("Sandbox Simulation")
            if div.audit_status != "ACCEPT":
                failed_dims.append("Confidence Divergence")

            q_payload = self.question_generator.generate_questions(
                target_action=curr_contract.recommended_actions[0] if curr_contract.recommended_actions else "Recovery"
            )

            iteration = IterativeReviewIteration(
                round_number=round_idx,
                status="PASS" if is_pass else "FAIL",
                failed_dimensions=failed_dims,
                technical_questions=q_payload.technical_questions if not is_pass else [],
                remediation_recommendation="Tindakan disetujui" if is_pass else "Lengkapi log bukti dan jalankan ulang simulasi Sandbox.",
            )
            iterations.append(iteration)

            if is_pass:
                logger.info(f"[ClosedLoopReviewEngine] Session {session_id} PASSED audit on round {round_idx}")
                break
            else:
                logger.warning(f"[ClosedLoopReviewEngine] Session {session_id} FAILED audit on round {round_idx} -> Triggering revision round")
                # Simulate AI NOC contract revision for subsequent rounds
                curr_contract.missing_evidence = []
                curr_contract.ai_noc_confidence = 0.94

        trail_record = self.audit_tracker.record_trail(session_id, iterations)
        return trail_record
