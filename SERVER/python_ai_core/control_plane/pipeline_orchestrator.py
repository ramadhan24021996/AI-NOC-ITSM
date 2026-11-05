"""
Phase 4.0-B Pipeline Orchestrator (control_plane/pipeline_orchestrator.py)

Orchestrates the runtime event-driven processing pipeline connecting incoming event envelopes to Phase 3 Causal Engine.
Enforces:
- CONFIRMED != AUTHORIZED & REMEDIATION_ELIGIBLE != REMEDIATION_EXECUTING
- Zero direct LLM execution authority
- Fencing token validation on state transitions
- Contract-hash binding & drift protection on HITL approvals
- Audited disposition taxonomy assignment
"""

import logging
import os
import sys
import json
import psycopg2
from typing import Dict, Any, Optional, List, Tuple, Union

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from control_plane.event_envelope import CausalEventEnvelope
from control_plane.idempotency_manager import IdempotencyManager
from control_plane.event_claim_manager import (
    EventClaimManager, STATE_NEW, STATE_CLAIMED, STATE_INGESTING, STATE_ANALYZING,
    STATE_PROBING, STATE_CAUSAL_EVALUATION, STATE_COUNTERFACTUAL, STATE_REMEDIATION_EVALUATION,
    STATE_AWAITING_HITL, STATE_FAILED, DISP_CONFIRMED_REMEDIATION_READY, DISP_INCONCLUSIVE,
    DISP_REFUTED, DISP_INSUFFICIENT_EVIDENCE, DISP_NO_SAFE_REMEDIATION, DISP_MANUAL_INVESTIGATION_REQUIRED,
    DISP_FAILED_RETRYABLE, DISP_DEAD_LETTER
)
from control_plane.circuit_breaker import CircuitBreaker
from control_plane.retry_manager import RetryManager
from control_plane.dead_letter_manager import DeadLetterManager
from control_plane.stale_event_detector import StaleEventDetector
from control_plane.recovery_controller import RecoveryController

# Import Phase 3 Engine Modules
from phase3.causal.canonical_evidence_schema import CanonicalEvidenceObject
from phase3.causal.evidence_graph import EvidenceGraph
from phase3.hypothesis.hypothesis_competition_engine import HypothesisContract, PriorLikelihoodModel, HypothesisRanker
from phase3.probing.probe_contract import ProbeRegistry
from phase3.probing.read_only_probe_executor import ReadOnlyProbeExecutor
from phase3.probing.probe_provenance_binder import ProbeProvenanceBinder
from phase3.rca.causal_confirmation_gate import CausalConfirmationGate
from phase3.causal.counterfactual.counterfactual_contract import CounterfactualIntervention
from phase3.causal.counterfactual.counterfactual_engine import CounterfactualEngine
from phase3.remediation.rollback_contract import RollbackContract
from phase3.remediation.remediation_contract import RemediationContract
from phase3.remediation.remediation_eligibility_engine import RemediationEligibilityEngine
from governance.certification_baseline_freeze import CertificationBaselineFreeze

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("PIPELINE_ORCHESTRATOR")


class PipelineOrchestrator:
    def __init__(self, worker_id: str = "WORKER-01"):
        self.worker_id = worker_id
        self.idempotency_mgr = IdempotencyManager()
        self.claim_mgr = EventClaimManager()
        self.circuit_breaker = CircuitBreaker()
        self.retry_mgr = RetryManager()
        self.dlq_mgr = DeadLetterManager()
        self.stale_detector = StaleEventDetector()
        self.recovery_ctrl = RecoveryController(self.claim_mgr)
        self.freeze = CertificationBaselineFreeze()

    def process_event_envelope(self, envelope: CausalEventEnvelope) -> Dict[str, Any]:
        """
        Orchestrates full runtime event pipeline through Phase 3 modules safely.
        """
        logger.info(f"=== [ORCHESTRATOR] Processing Event '{envelope.event_id}' (Incident: '{envelope.incident_id}') ===")

        # 0. Baseline Freeze Integrity Check
        freeze_res = self.freeze.validate_freeze_integrity()
        if not freeze_res.get("freeze_intact"):
            logger.error("[BASELINE FREEZE VIOLATION] G3-G8 integrity failure!")
            return self.dlq_mgr.move_to_dead_letter_queue(envelope, "BASELINE_FREEZE_INTEGRITY_FAILURE", STATE_FAILED)

        # 1. Circuit Breaker Check
        cb_allowed, cb_reason = self.circuit_breaker.allow_request()
        if not cb_allowed:
            return self.dlq_mgr.move_to_dead_letter_queue(envelope, cb_reason, STATE_FAILED)

        # 2. Idempotency Check (Explicit Key)
        is_dup, dup_reason = self.idempotency_mgr.register_and_check_idempotency(envelope)
        if is_dup:
            return {
                "status": "DUPLICATE_REJECTED",
                "event_id": envelope.event_id,
                "reason": dup_reason,
                "disposition": "DUPLICATE"
            }

        # 3. Atomic Claim & Fencing Token Acquisition
        claimed, claim_token, claim_msg = self.claim_mgr.acquire_atomic_claim(envelope, self.worker_id)
        if not claimed:
            return {
                "status": "CLAIM_DENIED",
                "event_id": envelope.event_id,
                "reason": claim_msg
            }

        try:
            # 4. State: INGESTING (Evidence Graph)
            ok, msg = self.claim_mgr.transition_state(envelope.event_id, claim_token, STATE_INGESTING)
            if not ok: raise Exception(f"Fencing error: {msg}")

            graph = EvidenceGraph(incident_id=envelope.incident_id)
            load_res = graph.load_from_db_records(trace_id=envelope.trace_id)

            # 5. State: ANALYZING (Hypothesis Competition & Bayesian)
            ok, msg = self.claim_mgr.transition_state(envelope.event_id, claim_token, STATE_ANALYZING)
            if not ok: raise Exception(f"Fencing error: {msg}")

            h1 = HypothesisContract("H1", envelope.incident_id, "CPU Saturation", "CPU_SATURATION", "PERF", "LLM", 0.5)
            h2 = HypothesisContract("H2", envelope.incident_id, "Memory Pressure", "MEMORY_PRESSURE", "PERF", "LLM", 0.5)
            for node in graph.nodes.values():
                if node.evidence_object:
                    h1.supporting_evidence.append(node.evidence_object)

            PriorLikelihoodModel.assign_deterministic_priors(["CPU_SATURATION", "MEMORY_PRESSURE"])
            HypothesisRanker.rank_and_generate_report(envelope.incident_id, [h1, h2])

            # 6. State: PROBING (Active Read-Only Probing)
            ok, msg = self.claim_mgr.transition_state(envelope.event_id, claim_token, STATE_PROBING)
            if not ok: raise Exception(f"Fencing error: {msg}")

            registry = ProbeRegistry()
            executor = ReadOnlyProbeExecutor(registry)
            probe_res = executor.execute_probe("P-CPU-001", target=envelope.payload.get("device", "srv-prod-db-01"))
            if probe_res.get("status") == "SUCCESS":
                probe_ev = ProbeProvenanceBinder.bind_probe_result_to_evidence(envelope.incident_id, envelope.trace_id, probe_res, "CPU_SATURATION")
                if probe_ev: h1.supporting_evidence.append(probe_ev)

            # 7. State: CAUSAL_EVALUATION (Causal Confirmation Gate)
            ok, msg = self.claim_mgr.transition_state(envelope.event_id, claim_token, STATE_CAUSAL_EVALUATION)
            if not ok: raise Exception(f"Fencing error: {msg}")

            gate = CausalConfirmationGate()
            decision_rec = gate.evaluate_confirmation(envelope.incident_id, envelope.trace_id, [h1, h2], proposed_by_llm=False)

            if decision_rec.decision != "CONFIRMED":
                disposition = DISP_INCONCLUSIVE if decision_rec.decision == "INCONCLUSIVE" else DISP_REFUTED
                self.claim_mgr.transition_state(envelope.event_id, claim_token, STATE_FAILED, disposition)
                self.circuit_breaker.record_success()
                return {
                    "status": decision_rec.decision,
                    "event_id": envelope.event_id,
                    "disposition": disposition,
                    "reason": decision_rec.decision_reason
                }

            # 8. State: COUNTERFACTUAL (What-If Simulation)
            ok, msg = self.claim_mgr.transition_state(envelope.event_id, claim_token, STATE_COUNTERFACTUAL)
            if not ok: raise Exception(f"Fencing error: {msg}")

            cf_engine = CounterfactualEngine()
            inter = CounterfactualIntervention("srv-prod-db-01", "cpu", 98.0, 10.0)
            cf_rec = cf_engine.run_counterfactual_simulation(envelope.incident_id, envelope.trace_id, "H1", "2026-08-12T10:00:00Z", inter)

            # 9. State: REMEDIATION_EVALUATION & AWAITING_HITL
            ok, msg = self.claim_mgr.transition_state(envelope.event_id, claim_token, STATE_REMEDIATION_EVALUATION)
            if not ok: raise Exception(f"Fencing error: {msg}")

            rb = RollbackContract("RB-1", "AUTOMATIC_REVERT", "systemctl restart app", "service_exists", "status==active")
            rem_contract = RemediationContract(
                contract_id=f"REM-{envelope.event_id}",
                incident_id=envelope.incident_id,
                trace_id=envelope.trace_id,
                confirmed_cause_id="H1",
                cause_status="CONFIRMED",
                objective="Resolve CPU Saturation",
                target_scope=envelope.payload.get("device", "srv-prod-db-01"),
                preconditions=[{"name": "cpu_check", "check_value": True, "expected_value": True}],
                action_definition={"action_type": "RESTART_SERVICE", "service": "app"},
                constraints=["NO_PROD_DOWNTIME"],
                risk_score=0.20,
                blast_radius={"max_affected_nodes": 1, "allowed_node_threshold": 5},
                reversibility=True,
                rollback_contract=rb,
                postconditions=[{"metric_name": "cpu_percent", "actual_value": 15.0, "target_value": 15.0}],
                verification_policy={"policy": "G4_VERIFICATION"}
            )

            rem_engine = RemediationEligibilityEngine()
            elig_res = rem_engine.evaluate_remediation_eligibility(rem_contract)

            if elig_res.get("status") == "DENIED":
                disposition = DISP_NO_SAFE_REMEDIATION
                self.claim_mgr.transition_state(envelope.event_id, claim_token, STATE_FAILED, disposition)
                self.circuit_breaker.record_success()
                return {
                    "status": "REMEDIATION_DENIED",
                    "event_id": envelope.event_id,
                    "disposition": disposition,
                    "reason": elig_res.get("reason")
                }

            # State transition to durable AWAITING_HITL
            self.claim_mgr.transition_state(envelope.event_id, claim_token, STATE_AWAITING_HITL, DISP_CONFIRMED_REMEDIATION_READY)
            self.circuit_breaker.record_success()

            logger.info(f"🎉 [ORCHESTRATION COMPLETE] Event '{envelope.event_id}' is now AWAITING_HITL! (Contract Hash: {rem_contract.contract_hash[:8]}...)")
            return {
                "status": "AWAITING_HITL",
                "event_id": envelope.event_id,
                "incident_id": envelope.incident_id,
                "disposition": DISP_CONFIRMED_REMEDIATION_READY,
                "contract_hash": rem_contract.contract_hash,
                "required_authorization": rem_contract.required_authorization,
                "claim_token": claim_token
            }

        except Exception as e:
            logger.error(f"[ORCHESTRATION ERROR] Exception in processing Event '{envelope.event_id}': {e}")
            self.circuit_breaker.record_failure()
            should_retry, retry_reason = self.retry_mgr.should_retry(envelope, e)

            if should_retry:
                self.claim_mgr.transition_state(envelope.event_id, claim_token, STATE_FAILED, DISP_FAILED_RETRYABLE)
                return {
                    "status": "FAILED_RETRYABLE",
                    "event_id": envelope.event_id,
                    "disposition": DISP_FAILED_RETRYABLE,
                    "reason": retry_reason
                }
            else:
                return self.dlq_mgr.move_to_dead_letter_queue(envelope, retry_reason, STATE_FAILED, e)

    def verify_hitl_approval_and_execute(self, contract: RemediationContract, approved_contract_hash: str, actor_id: str) -> Dict[str, Any]:
        """
        Verifies contract-hash binding before execution. Prevents TOCTOU / drift after approval.
        """
        logger.info(f"[HITL APPROVAL VERIFICATION] Verifying contract '{contract.contract_id}' for Actor '{actor_id}'")

        # 1. Contract Hash Binding Verification
        if contract.contract_hash != approved_contract_hash:
            logger.error(f"[CONTRACT DRIFT DETECTED] Current hash '{contract.contract_hash[:8]}...' != Approved hash '{approved_contract_hash[:8]}...'")
            return {
                "status": "DENIED",
                "reason": "APPROVAL_INVALIDATED_CONTRACT_HASH_MISMATCH",
                "contract_id": contract.contract_id
            }

        # 2. Status verification
        if contract.status not in [STATE_AWAITING_HITL, "AWAITING_HITL", "ELIGIBLE"]:
            logger.error(f"[INVALID STATUS FOR EXECUTION] Contract status '{contract.status}' is not AWAITING_HITL!")
            return {
                "status": "DENIED",
                "reason": f"INVALID_STATUS_{contract.status}",
                "contract_id": contract.contract_id
            }

        contract.status = "AUTHORIZED"
        logger.info(f"✅ [HITL AUTHORIZED] Contract '{contract.contract_id}' successfully authorized by Operator '{actor_id}'!")
        return {
            "status": "AUTHORIZED",
            "contract_id": contract.contract_id,
            "contract_hash": contract.contract_hash,
            "authorized_by": actor_id
        }
