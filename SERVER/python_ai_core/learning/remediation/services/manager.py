"""
Remediation Learning Manager — Production-hardened (pool-backed connections).
Uses PGConnection context manager for every operation instead of persistent self.conn.
"""
import logging
from typing import Dict, Any, List
from datetime import datetime, timezone

from SERVER.shared.db_pool import PGConnection

_log = logging.getLogger("learning.remediation.manager")


class RemediationManager:
    """Manages remediation learning lifecycle backed by PostgreSQL connection pool."""

    def register_remediation(self, payload: dict) -> str:
        with PGConnection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO remediation_registry
                    (remediation_id, incident_id, tenant_id, device_id, action_name, executor,
                     execution_time, rollback_available, execution_status, confidence_before)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    ON CONFLICT (remediation_id) DO NOTHING
                """, (
                    payload["remediation_id"], payload["incident_id"],
                    payload["tenant_id"], payload["device_id"],
                    payload["action_name"], payload["executor"],
                    payload.get("execution_time", datetime.now(timezone.utc)),
                    payload.get("rollback_available", False),
                    payload["execution_status"],
                    payload.get("confidence_before", 0.0),
                ))
                cur.execute(
                    "INSERT INTO remediation_audit (remediation_id, event, reason) VALUES (%s, %s, %s)",
                    (payload["remediation_id"], "REGISTERED", "Initial Registration"),
                )
        return payload["remediation_id"]

    def log_evidence_and_result(
        self, remediation_id: str, action_name: str, result: dict, confidence_before: float
    ):
        """Calculates Success Score and Updates Confidence dynamically."""
        if not result.get("evidence"):
            raise ValueError("Evidence is strictly required for Remediation Learning.")

        resolution_time = result.get("resolution_time_ms", 999999)
        error_count = result.get("error_count", 0)
        rollback = result.get("rollback_needed", False)

        score = 1.0
        if rollback: score -= 0.5
        if error_count > 0: score -= 0.1 * error_count
        if resolution_time > 60000: score -= 0.2
        if result.get("manual_intervention"): score -= 0.3
        score = max(0.0, score)

        confidence_delta = 0.05 if score > 0.7 else -0.05
        new_confidence = min(1.0, max(0.0, confidence_before + confidence_delta))

        with PGConnection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO remediation_results
                    (remediation_id, resolution_time_ms, rollback_needed, service_restored,
                     manual_intervention, error_count, downtime_ms, failure_type, failure_cause, evidence)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    remediation_id, resolution_time, rollback,
                    result.get("service_restored", False),
                    result.get("manual_intervention", False),
                    error_count, result.get("downtime_ms", 0),
                    result.get("failure_type"), result.get("failure_cause"),
                    result.get("evidence"),
                ))
                cur.execute("""
                    INSERT INTO remediation_scores (remediation_id, action_name, success_score, confidence_delta)
                    VALUES (%s, %s, %s, %s)
                """, (remediation_id, action_name, score, confidence_delta))
                cur.execute(
                    "UPDATE remediation_registry SET confidence_after = %s WHERE remediation_id = %s",
                    (new_confidence, remediation_id),
                )
                cur.execute(
                    "INSERT INTO remediation_audit (remediation_id, event, reason) VALUES (%s, %s, %s)",
                    (remediation_id, "EVALUATED", f"Score: {score}, Delta: {confidence_delta}"),
                )
                self._update_rankings(action_name, cur)
        return score, new_confidence

    def log_hitl_feedback(self, remediation_id: str, engineer_id: str, action: str, comments: str):
        with PGConnection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO remediation_feedback (remediation_id, engineer_id, action_taken, comments)
                    VALUES (%s, %s, %s, %s)
                """, (remediation_id, engineer_id, action, comments))
                cur.execute(
                    "INSERT INTO remediation_audit (remediation_id, event, reason) VALUES (%s, %s, %s)",
                    (remediation_id, f"HITL_{action}", comments),
                )

    def _update_rankings(self, action_name: str, cur) -> None:
        """Recalculates average success score for an action."""
        cur.execute(
            "SELECT AVG(success_score) FROM remediation_scores WHERE action_name = %s",
            (action_name,),
        )
        # avg_score = cur.fetchone()[0] or 0.0
        # In production: update materialized view or rankings table here.

    def get_action_ranking(self) -> List[Dict[str, Any]]:
        with PGConnection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT action_name, AVG(success_score) as avg_score, COUNT(*) as exec_count
                    FROM remediation_scores
                    GROUP BY action_name
                    ORDER BY avg_score DESC, exec_count DESC
                """)
                return [
                    {"action_name": row[0], "avg_score": row[1], "rank": i + 1}
                    for i, row in enumerate(cur.fetchall())
                ]
