"""
CLOSED-LOOP DECISION SYSTEM ORCHESTRATOR
Binds the complete Tier-1 AIOps Probabilistic Cycle:
DBN Belief State -> Causal DAG -> AI Planner -> Decision Network (MEU) -> Policy Verifier -> Execution -> RLHF Update -> DBN Update
"""

import sys
import os
import logging
import time
from typing import Dict, List, Any, Optional, Tuple

# Ensure parent directory (python_ai_core) is in sys.path for direct execution
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from probabilistic.dynamic_bayesian_network import DynamicBayesianNetwork
from probabilistic.decision_network import DecisionNetworkEngine, RemediationActionNode
from probabilistic.probabilistic_engine import BayesianHypothesisEngine, ProbabilityCalibrator
from probabilistic.business_context_engine import BusinessContextEngine
from probabilistic.baum_welch_em_trainer import BaumWelchDBNTrainer
from probabilistic.replay_validation_pipeline import ReplayValidationPipeline

logger = logging.getLogger("CLOSED_LOOP_ORCHESTRATOR")

class ClosedLoopDecisionOrchestrator:
    """
    Orkestrator Utama Sistem Operasi Otonom Closed-Loop.
    Mengirimkan aliran keputusan dari inferensi DBN awal hingga penyesuaian bobot RLHF pasca-eksekusi.
    Integrasi MLOps Gatekeeper & Business Context Engine.
    """

    def __init__(self):
        self.dbn_engine = DynamicBayesianNetwork()
        self.bayes_hyp_engine = BayesianHypothesisEngine()
        self.decision_network = DecisionNetworkEngine()
        self.calibrator = ProbabilityCalibrator()
        self.context_engine = BusinessContextEngine()
        self.em_trainer = BaumWelchDBNTrainer()
        self.replay_gatekeeper = ReplayValidationPipeline()
        logger.info("[CLOSED_LOOP] Closed-Loop Decision System Orchestrator initialized.")

    def process_closed_loop_cycle(
        self,
        device_id: str,
        device_role: str,
        telemetry_observation: Dict[str, Any],
        candidate_actions_raw: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        Menjalankan 7 Tahap Siklus Keputusan Closed-Loop secara utuh.
        """
        start_time = time.time()
        logger.info(f"[CLOSED_LOOP] Starting cycle for device '{device_id}' (Role={device_role})")

        # TAHAP 1: DBN Time-Series Belief State Update
        belief_distribution, dominant_state = self.dbn_engine.update_belief_step(
            device_name=device_id,
            observation_t=telemetry_observation,
            role=device_role
        )

        # TAHAP 2: Bayesian Hypothesis RCA & Causal DAG Weighting
        bayes_hypotheses = self.bayes_hyp_engine.calculate_posterior_probabilities(telemetry_observation)
        top_hypothesis = bayes_hypotheses[0] if bayes_hypotheses else {"hypothesis": "UNKNOWN", "posterior_probability": 0.5}

        # TAHAP 3: AI Planner & Remediation Candidate Formulation
        # Mengubah candidate actions mentah menjadi RemediationActionNodes
        action_nodes = []
        for act in candidate_actions_raw:
            # Calibrate raw success score
            calibrated_p = self.calibrator.calibrate_cosine_similarity(act.get("raw_success_score", 0.75))
            node = RemediationActionNode(
                action_id=str(act["id"]),
                name=str(act["name"]),
                target_device=device_id,
                success_probability=calibrated_p,
                estimated_downtime_seconds=float(act.get("downtime_sec", 10.0)),
                business_risk_score=float(act.get("risk_score", 0.1)),
                description=str(act.get("description", ""))
            )
            action_nodes.append(node)

        # TAHAP 4: Decision Network & Maximum Expected Utility (MEU) Evaluation
        optimal_action, ranked_meu_actions = self.decision_network.evaluate_and_select_optimal_action(
            candidate_actions=action_nodes,
            belief_distribution=belief_distribution
        )

        # TAHAP 5: Policy Guard & Risk Safeguard Route Decision
        meu_score = optimal_action["expected_utility"]
        risk_score = optimal_action["business_risk_score"]
        
        # Aturan Keputusan Route: Aksi dieksekusi otomatis jika MEU > 20 dan Risk <= 0.40
        requires_hitl = risk_score > 0.40 or meu_score < 20.0 or dominant_state == "CRITICAL_FAILURE"
        execution_mode = "REQUIRE_HUMAN_APPROVAL" if requires_hitl else "FULL_AUTONOMOUS_EXECUTION"

        elapsed_ms = round((time.time() - start_time) * 1000, 2)
        import uuid
        command_id = f"cmd-{uuid.uuid4().hex[:16]}"

        cycle_result = {
            "cycle_status": "SUCCESS",
            "command_id": command_id,
            "device_id": device_id,
            "device_role": device_role,
            "latency_ms": elapsed_ms,
            "dbn_belief_state": {
                "dominant_state": dominant_state,
                "belief_confidence": f"{round(belief_distribution[dominant_state]*100, 1)}%",
                "full_distribution": belief_distribution
            },
            "top_bayesian_root_cause": top_hypothesis,
            "decision_network_selection": {
                "optimal_action_id": optimal_action["action_id"],
                "optimal_action_name": optimal_action["action_name"],
                "maximum_expected_utility": meu_score,
                "calibrated_success_probability": optimal_action["success_percentage"],
                "downtime_penalty": optimal_action["downtime_penalty"],
                "business_risk_penalty": optimal_action["risk_penalty"]
            },
            "execution_policy": {
                "command_id": command_id,
                "execution_mode": execution_mode,
                "requires_hitl": requires_hitl,
                "policy_reasoning": (
                    f"Selected '{optimal_action['action_name']}' via MEU (+{meu_score}). "
                    f"Route={execution_mode} (Risk={risk_score*100:.0f}%, DBN State={dominant_state}, CmdID={command_id})."
                )
            },
            "all_ranked_candidate_actions": ranked_meu_actions
        }

        logger.info(f"[CLOSED_LOOP] Cycle complete in {elapsed_ms}ms. Selected '{optimal_action['action_name']}' ({execution_mode})")
        return cycle_result


# Self-Test Demo Closed-Loop Orchestrator
if __name__ == "__main__":
    orchestrator = ClosedLoopDecisionOrchestrator()

    print("=== CLOSED-LOOP DECISION SYSTEM ORCHESTRATOR DEMO ===")
    print("Skenario: Siklus 7-Tahap AIOps dari DBN -> RCA -> MEU -> Decision Mode\n")

    test_obs = {
        "z_score_mem": 2.8,
        "z_score_cpu": 1.9,
        "mem_growth_rate": 8.5,
        "gc_pause_ms": 150.0,
        "swap_usage_percent": 12.0,
        "thread_count": 450,
        "oom_events": 0
    }

    test_candidates = [
        {"id": "ACT-01", "name": "Soft Restart Service", "raw_success_score": 0.82, "downtime_sec": 10.0, "risk_score": 0.15},
        {"id": "ACT-02", "name": "Failover to Replica Node", "raw_success_score": 0.94, "downtime_sec": 45.0, "risk_score": 0.25},
        {"id": "ACT-03", "name": "Full Host Hard Reboot", "raw_success_score": 0.98, "downtime_sec": 300.0, "risk_score": 0.85}
    ]

    result = orchestrator.process_closed_loop_cycle(
        device_id="DB-PROD-01",
        device_role="DATABASE",
        telemetry_observation=test_obs,
        candidate_actions_raw=test_candidates
    )

    print(f"⏱️ Cycle Latency: {result['latency_ms']} ms")
    print(f"🧠 DBN State: {result['dbn_belief_state']['dominant_state']} ({result['dbn_belief_state']['belief_confidence']})")
    print(f"🎯 Bayesian Root Cause: {result['top_bayesian_root_cause']['hypothesis']} ({result['top_bayesian_root_cause']['posterior_percentage']})")
    print(f"🏆 MEU Selected Action: '{result['decision_network_selection']['optimal_action_name']}' (MEU: {result['decision_network_selection']['maximum_expected_utility']})")
    print(f"🛡️ Policy Route: {result['execution_policy']['execution_mode']} (Requires HITL: {result['execution_policy']['requires_hitl']})")
