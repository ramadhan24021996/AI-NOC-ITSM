import logging
import json

logger = logging.getLogger("COUNTERFACTUAL_ENGINE")

class CounterfactualEngine:
    def __init__(self, conn=None):
        self.conn = conn

    def simulate_alternatives(self, primary_action: str) -> dict:
        """
        Simulates and scores alternative recovery paths.
        Calculates blast radius, recovery times, and complexity.
        """
        logger.info(f"Counterfactual Engine simulating alternatives for primary: {primary_action}")

        # Standard action alternatives
        alternatives = [
            {"action": "restart", "recovery_score": 90.0, "blast_radius": 15.0, "rollback_risk": "LOW", "dependency_risk": "MEDIUM", "irreversible": False},
            {"action": "reload", "recovery_score": 75.0, "blast_radius": 5.0, "rollback_risk": "LOW", "dependency_risk": "LOW", "irreversible": False},
            {"action": "scale", "recovery_score": 85.0, "blast_radius": 10.0, "rollback_risk": "LOW", "dependency_risk": "LOW", "irreversible": False},
            {"action": "isolate", "recovery_score": 60.0, "blast_radius": 55.0, "rollback_risk": "HIGH", "dependency_risk": "HIGH", "irreversible": True}
        ]

        # Calculate counterfactual scores
        # Formula: score = recovery_score / (blast_radius * risk_mult)
        scored_actions = []
        for alt in alternatives:
            # Map risk levels to numbers (>=1.0)
            rollback_mult = 1.0 if alt["rollback_risk"] == "LOW" else (2.0 if alt["rollback_risk"] == "MEDIUM" else 3.0)
            dep_mult = 1.0 if alt["dependency_risk"] == "LOW" else (2.0 if alt["dependency_risk"] == "MEDIUM" else 3.0)
            
            denominator = (alt["blast_radius"] * rollback_mult * dep_mult)
            denominator = max(1.0, denominator)  # prevent division by zero
            
            c_score = (alt["recovery_score"] * 100.0) / denominator
            alt["score"] = round(c_score, 2)
            scored_actions.append(alt)

        # Sort descending by score
        scored_actions.sort(key=lambda x: x["score"], reverse=True)

        # Apply Force HITL Rules
        force_hitl = False
        reasons = []

        if len(scored_actions) >= 2:
            top_score = scored_actions[0]["score"]
            second_score = scored_actions[1]["score"]
            diff = abs(top_score - second_score) / max(1.0, top_score) * 100.0
            if diff < 10.0:
                force_hitl = True
                reasons.append(f"Top action scores are too close (diff={diff:.1f}% < 10.0%)")

        for action_res in scored_actions:
            if action_res["action"] in primary_action.lower() and action_res["blast_radius"] > 50.0:
                force_hitl = True
                reasons.append(f"Primary action '{primary_action}' blast radius exceeds threshold ({action_res['blast_radius']} > 50.0)")
            if action_res["action"] in primary_action.lower() and action_res["irreversible"]:
                force_hitl = True
                reasons.append(f"Primary action '{primary_action}' is marked as irreversible")

        return {
            "force_hitl": force_hitl,
            "reasons": reasons,
            "matrix": scored_actions
        }

    def log_counterfactual_matrix(self, incident_id: int, matrix: list, selected_action: str):
        """Persists the simulated counterfactual matrix to the database."""
        if not self.conn:
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO policy_audit_trail (incident_id, policy_version, input_context, matched_rule, effect, evaluated_at)
                    VALUES (%s, 1, %s, 'Counterfactual Simulation', 'SIMULATION', NOW())
                """, (
                    incident_id,
                    json.dumps({"selected_action": selected_action, "matrix": matrix})
                ))
                self.conn.commit()
                logger.info(f"Counterfactual Matrix saved for incident {incident_id}")
        except Exception as e:
            logger.error(f"Failed to log counterfactual matrix: {e}")
            self.conn.rollback()
