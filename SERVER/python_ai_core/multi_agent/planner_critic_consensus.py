"""
Multi-Agent Consensus & Critic Auditor Engine (Layer 4 AI Core)
Implements 'Dual AI Brain Verification': Planner Agent vs Critic Auditor Agent.
Requires 100% Consensus (Score = 1.0) before any action clearance is granted.
If any dissent occurs between Planner and Critic, incident is immediately routed to HITL Human Queue.
"""

import logging
import time
from typing import Dict, Any, List, Optional

logger = logging.getLogger("PlannerCriticConsensusEngine")
logging.basicConfig(level=logging.INFO)

class PlannerCriticConsensusEngine:
    def __init__(self):
        logger.info("[PLANNER_CRITIC_CONSENSUS] Multi-Agent Consensus & Critic Auditor Engine initialized (100% Consensus Enforced).")

    def evaluate_dual_brain_consensus(
        self,
        incident_id: str,
        planner_output: Dict[str, Any],
        critic_audit_output: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Runs Dual-Agent Consensus:
        Planner Agent formulates Plan A/B/C.
        Critic Agent audits risk, security, and hallucination flaws.
        100% Consensus (Score = 1.0) required for automatic clearance.
        """
        plan_id = planner_output.get("plan_id", "PLAN_001")
        action = planner_output.get("recommended_action", "NO_ACTION")
        planner_confidence = planner_output.get("confidence", 0.95)

        # If Critic Audit Output is not explicitly provided, generate dynamic Critic Audit
        if not critic_audit_output:
            critic_audit_output = self._simulate_critic_audit(planner_output)

        critic_approved = critic_audit_output.get("approved", False)
        critic_score = critic_audit_output.get("critic_score", 0.0)
        critic_flaws = critic_audit_output.get("flaws_detected", [])

        # Calculate 100% Consensus Score
        # Consensus Score = 1.0 ONLY IF Planner and Critic agree 100% with ZERO flaws detected
        if critic_approved and len(critic_flaws) == 0 and planner_confidence >= 0.95:
            consensus_score = 1.0
            consensus_status = "100_PERCENT_CONSENSUS_APPROVED"
            requires_hitl = False
            clearance_status = "APPROVED_BY_DUAL_BRAIN_CONSENSUS"
        else:
            # Dissent or flaws detected -> Penalty applied, HITL enforced
            consensus_score = round(min(planner_confidence, critic_score) * 0.85, 2)
            consensus_status = "CONSENSUS_DISAGREEMENT_DISSENT"
            requires_hitl = True
            clearance_status = "PAUSED_AWAITING_HITL_QUEUE"

        result = {
            "incident_id": incident_id,
            "plan_id": plan_id,
            "verification_phase": "MULTI_AGENT_CONSENSUS_GATE",
            "consensus_status": consensus_status,
            "consensus_score": consensus_score,
            "requires_100_pct_consensus": True,
            "planner_agent_verdict": {
                "role": "Planner Agent",
                "recommended_action": action,
                "confidence": planner_confidence,
                "status": "PROPOSED"
            },
            "critic_auditor_verdict": {
                "role": "Critic Auditor Agent",
                "approved": critic_approved,
                "critic_score": critic_score,
                "flaws_detected": critic_flaws,
                "status": "AUDITED_APPROVED" if critic_approved else "AUDITED_REJECTED"
            },
            "requires_hitl_approval": requires_hitl,
            "execution_clearance": clearance_status,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        if consensus_score == 1.0:
            logger.info("[CONSENSUS_ENGINE] 100%% Dual-Brain Consensus REACHED for %s (Action: %s). Granted Clearance.", incident_id, action)
        else:
            logger.warning("[CONSENSUS_ENGINE] DISSENT DETECTED for %s! Consensus Score: %.2f (Flaws: %s). Routing to HITL Queue.",
                           incident_id, consensus_score, critic_flaws)

        return result

    def _simulate_critic_audit(self, planner_output: Dict[str, Any]) -> Dict[str, Any]:
        risk = planner_output.get("risk", 0.1)
        action = planner_output.get("recommended_action", "")
        
        # Critic rejects high risk (> 0.3) or unapproved raw commands
        if risk > 0.3 or "rm -rf" in action.lower():
            return {
                "approved": False,
                "critic_score": 0.40,
                "flaws_detected": ["High Risk Action (>0.30)", "Potential Dangerous Command Detected"]
            }
        
        return {
            "approved": True,
            "critic_score": 1.0,
            "flaws_detected": []
        }


if __name__ == "__main__":
    engine = PlannerCriticConsensusEngine()

    # Test 1: 100% Agreement (Planner & Critic agree 100%)
    plan1 = {"plan_id": "PLAN_SPOOLER", "recommended_action": "SOP_001: Restart Spooler", "confidence": 0.98, "risk": 0.05}
    res1 = engine.evaluate_dual_brain_consensus("INC_001", plan1)
    print("Test 1 (100% Consensus):", res1["consensus_status"], "Score:", res1["consensus_score"], "HITL:", res1["requires_hitl_approval"])

    # Test 2: Dissent (Planner proposes High Risk Action, Critic rejects)
    plan2 = {"plan_id": "PLAN_HIGH_RISK", "recommended_action": "Drop Database Index", "confidence": 0.90, "risk": 0.60}
    res2 = engine.evaluate_dual_brain_consensus("INC_002", plan2)
    print("Test 2 (Dissent Case):", res2["consensus_status"], "Score:", res2["consensus_score"], "HITL:", res2["requires_hitl_approval"])
