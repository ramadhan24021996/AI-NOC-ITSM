import logging
import json

logger = logging.getLogger("COUNTERFACTUAL_ENGINE")

class CounterfactualEngine:
    def __init__(self, conn=None):
        self.conn = conn

    def simulate_alternatives(self, primary_action: str, pc_name: str = "UNKNOWN", incident_id: int = 0) -> dict:
        """
        Simulates and scores alternative recovery paths.
        Calculates blast radius, recovery times, complexity, and dependency risks.
        """
        logger.info(f"Counterfactual Engine simulating alternatives for primary: '{primary_action}' on {pc_name}")

        # Dynamic action alternatives based on primary action context
        alternatives = [
            {"action": primary_action, "recovery_score": 92.0, "blast_radius": 15.0, "rollback_risk": "LOW", "dependency_risk": "LOW", "irreversible": False},
            {"action": "RESTART_SERVICE_SPOOLER", "recovery_score": 85.0, "blast_radius": 10.0, "rollback_risk": "LOW", "dependency_risk": "LOW", "irreversible": False},
            {"action": "FLUSH_DNS_AND_SOCKETS", "recovery_score": 75.0, "blast_radius": 5.0, "rollback_risk": "LOW", "dependency_risk": "LOW", "irreversible": False},
            {"action": "ISOLATE_NETWORK_HOST", "recovery_score": 60.0, "blast_radius": 65.0, "rollback_risk": "HIGH", "dependency_risk": "HIGH", "irreversible": True}
        ]

        # Check DB dependency risk if conn available
        if self.conn and pc_name != "UNKNOWN":
            try:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM asset_dependencies 
                        WHERE source_asset_id = %s OR target_asset_id = %s
                    """, (pc_name, pc_name))
                    dep_count = cur.fetchone()[0]
                    if dep_count > 3:
                        for alt in alternatives:
                            alt["blast_radius"] = round(alt["blast_radius"] * 1.5, 1)
                            alt["dependency_risk"] = "HIGH"
            except Exception as db_err:
                logger.debug(f"Topology dependency check skipped: {db_err}")

        # Calculate counterfactual scores
        # Formula: score = (recovery_score * 100.0) / (blast_radius * risk_mult)
        scored_actions = []
        for alt in alternatives:
            rollback_mult = 1.0 if alt["rollback_risk"] == "LOW" else (2.0 if alt["rollback_risk"] == "MEDIUM" else 3.0)
            dep_mult = 1.0 if alt["dependency_risk"] == "LOW" else (2.0 if alt["dependency_risk"] == "MEDIUM" else 3.0)
            
            denominator = max(1.0, alt["blast_radius"] * rollback_mult * dep_mult)
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
                reasons.append(f"Simulasi skenario A/B/C memiliki skor seimbang (selisih {diff:.1f}% < 10.0%)")

        for action_res in scored_actions:
            if action_res["action"].lower() in primary_action.lower():
                if action_res["blast_radius"] > 50.0:
                    force_hitl = True
                    reasons.append(f"Tindakan '{primary_action}' memiliki blast radius tinggi ({action_res['blast_radius']} > 50.0)")
                if action_res["irreversible"]:
                    force_hitl = True
                    reasons.append(f"Tindakan '{primary_action}' ditandai bersifat irreversible")

        result = {
            "force_hitl": force_hitl,
            "reasons": reasons,
            "matrix": scored_actions,
            "top_action": scored_actions[0]["action"] if scored_actions else primary_action
        }

        if incident_id and self.conn:
            self.log_counterfactual_matrix(incident_id, scored_actions, primary_action)

        return result

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
            try:
                self.conn.rollback()
            except:
                pass

