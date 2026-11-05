"""
closed_loop_orchestrator.py
============================
CLOSED-LOOP DECISION SYSTEM ORCHESTRATOR
Sistem Operasi Otonom Closed-Loop Adaptif Sesuai Spesifikasi ccloude.md.
"""

import sys
import os
import logging
import time
import uuid
from typing import Dict, List, Any, Optional

current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from core.adaptive_incident_model import IncidentContext, IncidentState
from core.osi_classifier import OSI7LayerAdaptiveClassifier
from governance.dynamic_sop_engine import DynamicSOPEngine
from planning.adaptive_action_planner import AdaptiveActionPlanner
from execution.verification_engine import VerificationEngine
from governance.human_escalation_engine import HumanEscalationChain
from governance.human_review_queue import HumanReviewQueue, ReviewDecisionOption
from core.agent_tray_formatter import AgentTrayContextFormatter

from probabilistic.dynamic_bayesian_network import DynamicBayesianNetwork
from probabilistic.decision_network import DecisionNetworkEngine
from probabilistic.probabilistic_engine import BayesianHypothesisEngine

logger = logging.getLogger("CLOSED_LOOP_ORCHESTRATOR")


class ClosedLoopDecisionOrchestrator:
    """
    Orkestrator Utama Closed-Loop Incident Response Engine Adaptif.
    """

    def __init__(self):
        self.osi_classifier = OSI7LayerAdaptiveClassifier()
        self.sop_engine = DynamicSOPEngine()
        self.planner = AdaptiveActionPlanner()
        self.verifier = VerificationEngine()
        self.escalator = HumanEscalationChain()
        self.hitl_queue = HumanReviewQueue()
        self.tray_formatter = AgentTrayContextFormatter()
        self.dbn_engine = DynamicBayesianNetwork()
        self.bayes_hyp_engine = BayesianHypothesisEngine()
        self.decision_network = DecisionNetworkEngine()
        logger.info("[CLOSED_LOOP] Adaptive Closed-Loop Decision Orchestrator initialized.")

    def run_closed_loop_cycle(
        self,
        incident_context: IncidentContext,
        telemetry_post_execution: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Menjalankan Siklus Keputusan Closed-Loop Adaptif.
        """
        start_time = time.time()
        logger.info(f"[CLOSED_LOOP] Processing cycle for incident '{incident_context.incident_id}' (State: {incident_context.current_state})")

        # 1. State: OBSERVING & CLASSIFYING -> OSI 7-Layer
        if incident_context.current_state in [IncidentState.NEW, IncidentState.RECOVERY_FAILED]:
            incident_context.transition_to(IncidentState.OBSERVING, "Ingesting telemetry & symptoms")
            incident_context.transition_to(IncidentState.CLASSIFYING, "Running OSI 7-Layer Classification")

        osi_result = self.osi_classifier.classify_incident(
            symptoms=incident_context.symptoms,
            telemetry=incident_context.telemetry,
            evidence=incident_context.evidence
        )
        incident_context.osi_layers = [osi_result["primary_layer"]] + osi_result["secondary_layers"]

        # 2. State: DIAGNOSING -> DBN & Bayesian Hypothesis
        incident_context.transition_to(IncidentState.DIAGNOSING, "Running DBN & RCA Inference")
        belief_dist, dominant_state = self.dbn_engine.update_belief_step(
            device_name=incident_context.device_id,
            observation_t=incident_context.telemetry,
            role=incident_context.device_type
        )
        bayes_hypotheses = self.bayes_hyp_engine.calculate_posterior_probabilities(incident_context.telemetry)
        
        if bayes_hypotheses:
            top_prob = float(bayes_hypotheses[0].get("posterior_probability", 0.50))
            if top_prob > 0.50:
                incident_context.confidence = top_prob

        # Apply failure penalty to confidence
        penalty = len(incident_context.failed_actions) * 0.15
        incident_context.confidence = max(0.10, round(incident_context.confidence - penalty, 2))

        # 3. State: SOP_MATCHED -> Dynamic SOP Retrieval
        incident_context.transition_to(IncidentState.SOP_MATCHED, "Matching contextual SOP Decision Tree")
        matched_sops = self.sop_engine.match_sop_contextual(incident_context)
        incident_context.matched_sops = matched_sops

        # 4. State: PLAN_GENERATED -> Adaptive Action Planner (Failure-Aware)
        incident_context.transition_to(IncidentState.PLAN_GENERATED, "Formulating Adaptive Execution Plan")
        plan_result = self.planner.generate_adaptive_plan(incident_context)

        if plan_result.get("requires_escalation") or not plan_result.get("recommended_action"):
            incident_context.transition_to(IncidentState.ESCALATING, "Planner requested escalation or no SOP actions left")
            esc_info = self.escalator.determine_escalation_level(incident_context)
            incident_context.resolution_status = "ESCALATED"
            
            return {
                "cycle_status": "ESCALATED",
                "incident_id": incident_context.incident_id,
                "current_state": incident_context.current_state,
                "escalation_info": esc_info,
                "agent_tray_payload": self.tray_formatter.format_agent_tray_payload(incident_context)
            }

        recommended_action = plan_result["recommended_action"]
        incident_context.current_action = recommended_action
        incident_context.next_action = recommended_action

        # 5. Risk & Policy Check -> HITL Decision Gate
        raw_risk = recommended_action.get("risk_score") if recommended_action else None
        risk_score = float(raw_risk) if raw_risk is not None else 0.1
        incident_context.risk_score = risk_score

        # Action is pre-approved if risk <= 0.40 and confidence >= 0.60 and not CRITICAL
        is_pos_active_trx = incident_context.telemetry.get("pos_active_transaction", False)
        requires_hitl = (risk_score > 0.40 or incident_context.confidence < 0.60 or incident_context.severity == "CRITICAL" or is_pos_active_trx) and (incident_context.hitl_status != "APPROVED")
        
        if requires_hitl:
            incident_context.transition_to(IncidentState.WAITING_HITL, "High risk or low confidence requires HITL approval")
            hitl_item = self.hitl_queue.enqueue_action_for_review(incident_context, recommended_action)
            
            return {
                "cycle_status": "WAITING_HITL",
                "incident_id": incident_context.incident_id,
                "hitl_item_id": hitl_item.item_id,
                "proposed_action": recommended_action,
                "agent_tray_payload": self.tray_formatter.format_agent_tray_payload(incident_context)
            }

        # 6. State: APPROVED -> EXECUTING
        action_name = recommended_action.get("name", "UNNAMED_ACTION") if recommended_action else "UNNAMED_ACTION"
        if incident_context.current_state != IncidentState.APPROVED:
            incident_context.transition_to(IncidentState.APPROVED, "Policy passed / HITL approved")
        incident_context.transition_to(IncidentState.EXECUTING, f"Executing action '{action_name}'")

        # Simulate / Perform Execution
        exec_result = {
            "success": True,
            "exit_code": 0,
            "output": f"Executed {action_name} successfully."
        }

        # 7. State: VERIFYING -> Empirical Independent Verification Engine
        incident_context.transition_to(IncidentState.VERIFYING, "Running independent post-action verification")
        
        post_telemetry = telemetry_post_execution or incident_context.telemetry
        action_id = recommended_action.get("id", "ACT_001") if recommended_action else "ACT_001"
        verif_result = self.verifier.verify_remediation(
            action_id=action_id,
            verification_steps=["spooler_running", "queue_cleared"],
            target_asset=incident_context.device_id,
            execution_result=exec_result,
            post_telemetry=post_telemetry
        )
        incident_context.verification_result = verif_result

        # 8. Check Resolved vs Failure Adaptation Loop
        if verif_result["all_verified"]:
            incident_context.transition_to(IncidentState.RESOLVED, "Verification PASSED - Incident Resolved")
            incident_context.resolution_status = "RESOLVED"
            incident_context.transition_to(IncidentState.CLOSED, "Incident closed")
            incident_context.transition_to(IncidentState.LEARNING, "Recording closed-loop outcome for calibration")

            # Auto-Distill Resolution into Continuous Learning RAG Base
            try:
                from engines.rag_engine import get_rag_engine
                rag = get_rag_engine()
                primary_layer_str = incident_context.osi_layers[0] if incident_context.osi_layers else incident_context.service
                issue_text = f"Incident on {incident_context.device_id} ({incident_context.device_type}): {primary_layer_str}"
                solution_text = f"Action: {action_name}. Verified outcome: {verif_result.get('outcome_id', 'SUCCESS')}"
                rag.ingest_incremental_resolution(
                    issue=issue_text,
                    root_cause=f"Resolved via verified adaptive plan ({action_id})",
                    solution=solution_text,
                    success_rate=1.0
                )
                logger.info(f"[ContinuousLearning] Successfully distilled verified incident '{incident_context.incident_id}' into RAG knowledge memory.")
            except Exception as rag_learn_err:
                logger.debug(f"[ContinuousLearning] RAG knowledge update deferred: {rag_learn_err}")

            return {
                "cycle_status": "RESOLVED",
                "incident_id": incident_context.incident_id,
                "final_state": incident_context.current_state,
                "executed_action": recommended_action,
                "verification_result": verif_result,
                "agent_tray_payload": self.tray_formatter.format_agent_tray_payload(incident_context)
            }

        else:
            # FAILURE ADAPTATION PRINCIPLE: Action execution OK but verification failed!
            incident_context.transition_to(IncidentState.RECOVERY_FAILED, "Verification FAILED")
            incident_context.record_action_failure(
                action=recommended_action or {},
                failure_reason=", ".join(verif_result.get("failure_reasons", []))
            )

            # Re-determine escalation level if attempts exceed threshold
            esc_info = self.escalator.determine_escalation_level(incident_context)

            logger.warning(
                f"[FailureAdaptation] Verification FAILED for action '{action_name}'! "
                f"Attempt count now: {incident_context.attempt_count}. Mutating plan."
            )

            return {
                "cycle_status": "RECOVERY_FAILED",
                "incident_id": incident_context.incident_id,
                "failed_action": recommended_action,
                "attempt_count": incident_context.attempt_count,
                "verification_result": verif_result,
                "escalation_info": esc_info,
                "agent_tray_payload": self.tray_formatter.format_agent_tray_payload(incident_context)
            }
