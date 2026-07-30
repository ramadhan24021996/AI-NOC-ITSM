"""
AI Planning Engine (L4_Planner) - Autonomous AI Ops Plan Formulator
Formulates candidate remediation plans (Plan A, B, C) with risk assessment,
success probability, estimated duration, and recommended plan selection.
"""

import logging
import time
from typing import Dict, List, Any, Optional

logger = logging.getLogger("AI_PLANNER")

class AIPlanningEngine:
    def __init__(self):
        logger.info("[AI_PLANNER] AI Planning Engine initialized.")

    def formulate_remediation_plan(
        self,
        incident_id: str,
        symptom: str,
        root_cause: str,
        blast_radius: Dict[str, Any],
        trust_score: float = 0.95,
        dbn_belief_state: Optional[Dict[str, float]] = None
    ) -> Dict[str, Any]:
        """
        Generates candidate plans for an incident based on diagnostic inputs and DBN belief state thresholds.
        Mutates candidate action plans dynamically based on DBN belief state evolution.
        """
        logger.info(f"[AI_PLANNER] Formulating plans for incident={incident_id}, root_cause={root_cause}")

        # 1. Base Candidate Plans
        plans = [
            {
                "id": "plan_a",
                "action": "restart_affected_service",
                "label": f"Soft Restart of Affected Service ({root_cause})",
                "risk": 0.10,
                "success_probability": 0.75,
                "duration_sec": 20,
                "impact_scope": "local_service",
                "requires_hitl": False
            },
            {
                "id": "plan_b",
                "action": "failover_cluster_node",
                "label": "Failover Traffic to Redundant Cluster Node",
                "risk": 0.18,
                "success_probability": 0.92,
                "duration_sec": 40,
                "impact_scope": "cluster_wide",
                "requires_hitl": False
            },
            {
                "id": "plan_c",
                "action": "scale_out_deployment",
                "label": "Auto Scale-out Microservices Deployment (+2 Replicas)",
                "risk": 0.05,
                "success_probability": 0.96,
                "duration_sec": 120,
                "impact_scope": "resource_pool",
                "requires_hitl": True
            }
        ]

        # 2. DBN Belief-Driven Plan Mutation (Dynamic Action Plan Adaptation)
        if dbn_belief_state:
            leak_prob = dbn_belief_state.get("PROGRESSIVE_LEAK", 0.0)
            crit_prob = dbn_belief_state.get("CRITICAL_FAILURE", 0.0)

            if leak_prob > 0.50 and crit_prob < 0.30:
                # Moderate Leak: Mutate Plan A to Non-Intrusive Heap Dump & Profiling Action
                plans[0] = {
                    "id": "plan_diag",
                    "action": "heap_dump_and_profiling",
                    "label": f"Trigger Heap Dump & Diagnostic Profiling ({root_cause})",
                    "risk": 0.02,
                    "success_probability": 0.85,
                    "duration_sec": 5,
                    "impact_scope": "non_intrusive_diagnostic",
                    "requires_hitl": False
                }
                logger.info(f"[AI_PLANNER] Mutated plan to 'plan_diag' due to moderate DBN Progressive Leak ({leak_prob*100:.1f}%)")
            elif crit_prob >= 0.75:
                # Critical Failure: Mutate Plan A to Aggressive Hard Kill & Restart
                plans[0] = {
                    "id": "plan_emergency",
                    "action": "emergency_hard_restart",
                    "label": f"Emergency Process Hard Kill & Immediate Restart ({root_cause})",
                    "risk": 0.35,
                    "success_probability": 0.95,
                    "duration_sec": 15,
                    "impact_scope": "host_wide",
                    "requires_hitl": True
                }
                logger.info(f"[AI_PLANNER] Mutated plan to 'plan_emergency' due to high DBN Critical Failure ({crit_prob*100:.1f}%)")

        # Select recommendation using Decision Network & Maximum Expected Utility (MEU) Engine
        try:
            from probabilistic.decision_network import DecisionNetworkEngine, RemediationActionNode
            dn_engine = DecisionNetworkEngine()
            
            action_nodes = []
            for p in plans:
                node = RemediationActionNode(
                    action_id=str(p["id"]),
                    name=str(p["label"]),
                    target_device=str(incident_id),
                    success_probability=float(p["success_probability"]),
                    estimated_downtime_seconds=float(p["duration_sec"]),
                    business_risk_score=float(p["risk"])
                )
                action_nodes.append(node)

            optimal_action_dict, ranked_meu_list = dn_engine.evaluate_and_select_optimal_action(action_nodes)
            recommended_plan_id = optimal_action_dict["action_id"]
            recommended_plan = next(p for p in plans if p["id"] == recommended_plan_id)
            
            # Attach MEU metrics to candidate plans
            for p in plans:
                matching_meu = next((item for item in ranked_meu_list if item["action_id"] == p["id"]), None)
                if matching_meu:
                    p["expected_utility"] = matching_meu["expected_utility"]
                    p["base_utility"] = matching_meu["base_utility"]
                    p["downtime_penalty"] = matching_meu["downtime_penalty"]
        except Exception as e:
            logger.warning(f"[AI_PLANNER] Decision Network fallback: {e}")
            recommended_plan = max(plans, key=lambda p: p["success_probability"] / (p["risk"] + 0.01))
            recommended_plan_id = recommended_plan["id"]

        response = {
            "incident_id": incident_id,
            "goal": f"Pulihkan layanan dari masalah: {root_cause}",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "diagnostic_context": {
                "symptom": symptom,
                "root_cause": root_cause,
                "blast_radius_level": blast_radius.get("level", "MEDIUM"),
                "trust_score": trust_score
            },
            "candidate_plans": plans,
            "recommended_plan_id": recommended_plan_id,
            "recommendation_reasoning": (
                f"Selected '{recommended_plan_id}' ({recommended_plan['label']}) "
                f"based on Maximum Expected Utility (MEU = {recommended_plan.get('expected_utility', 'N/A')}), "
                f"balancing success probability ({recommended_plan['success_probability']*100:.0f}%) "
                f"against downtime duration ({recommended_plan['duration_sec']}s) and business risk."
            )
        }

        logger.info(f"[AI_PLANNER] Recommended plan: {recommended_plan['id']} ({recommended_plan['action']})")
        return response

# Global instance
ai_planner_engine = AIPlanningEngine()
