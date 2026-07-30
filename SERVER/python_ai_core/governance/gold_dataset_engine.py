"""
Gold Dataset Engine — Phase 4 Learning Pipeline.

Promotes successfully resolved incidents to the auditable Gold Dataset
so they can be used for regression testing and AI model improvement.
"""

import logging
import json
import os
import psycopg2
from typing import Dict, Any, List

logger = logging.getLogger("GoldDatasetEngine")


class GoldDatasetEngine:
    def __init__(self, db_conn=None):
        self.conn = db_conn
        if not self.conn:
            self.conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "127.0.0.1"),
                port=int(os.getenv("DB_PORT", "5432")),
                database=os.getenv("DB_NAME", "osi_system"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "postgres"),
            )

    # ──────────────────────────────────────────────────────────────────────────
    # PUBLIC API
    # ──────────────────────────────────────────────────────────────────────────

    def extract_incident_to_gold(self, incident_id: str) -> bool:
        """
        Promotes a resolved incident to the Gold Dataset.
        Fetches real RCA from incident_post_mortems and engineer actions
        from hitl_audit_logs / incident_feedback.
        Returns True on success, False otherwise.
        """
        if not self.conn:
            return False
        try:
            with self.conn.cursor() as cur:
                # 1. Fetch raw incident data
                cur.execute(
                    "SELECT raw_data FROM incidents WHERE incident_id = %s",
                    (incident_id,),
                )
                row = cur.fetchone()
                if not row:
                    logger.warning(f"[GoldDataset] Incident {incident_id} not found.")
                    return False
                raw_data = row[0]

                # 2. Fetch real RCA from post-mortem (preferred) or ai_audit_trail
                cur.execute(
                    """
                    SELECT root_cause, resolution, ai_confidence
                    FROM   incident_post_mortems
                    WHERE  incident_id = %s
                    ORDER  BY created_at DESC
                    LIMIT  1
                    """,
                    (incident_id,),
                )
                pm_row = cur.fetchone()
                if pm_row:
                    final_rca = f"{pm_row[0]} | Resolution: {pm_row[1]} | Confidence: {pm_row[2]}"
                else:
                    # Fallback: first AI audit trail action
                    cur.execute(
                        """
                        SELECT action_executed FROM ai_audit_trail
                        WHERE  incident_id::text = %s
                        ORDER  BY created_at ASC
                        LIMIT  1
                        """,
                        (incident_id,),
                    )
                    at_row = cur.fetchone()
                    final_rca = at_row[0] if at_row else "UNKNOWN_RCA"

                # 3. Fetch engineer action from hitl_audit_logs or incident_feedback
                cur.execute(
                    """
                    SELECT action_name FROM hitl_audit_logs
                    WHERE  incident_id = %s
                    ORDER  BY id DESC
                    LIMIT  1
                    """,
                    (incident_id,),
                )
                hitl_row = cur.fetchone()
                if hitl_row:
                    engineer_action = hitl_row[0]
                else:
                    cur.execute(
                        """
                        SELECT feedback_action FROM incident_feedback
                        WHERE  incident_id = %s
                        ORDER  BY created_at DESC
                        LIMIT  1
                        """,
                        (incident_id,),
                    )
                    fb_row = cur.fetchone()
                    engineer_action = fb_row[0] if fb_row else "NO_ENGINEER_ACTION"

                # 4. Determine outcome from incident_states
                cur.execute(
                    """
                    SELECT status FROM incident_states
                    WHERE  incident_id = %s
                    ORDER  BY created_at DESC
                    LIMIT  1
                    """,
                    (incident_id,),
                )
                st_row = cur.fetchone()
                outcome = st_row[0] if st_row else "UNKNOWN"

                # 5. Insert into Gold Dataset
                cur.execute(
                    """
                    INSERT INTO ai_gold_dataset
                        (incident_data, final_rca, engineer_action, outcome)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT DO NOTHING
                    """,
                    (
                        json.dumps(raw_data),
                        final_rca,
                        engineer_action,
                        outcome,
                    ),
                )

            self.conn.commit()
            logger.info(f"[GoldDataset] Incident {incident_id} promoted → outcome={outcome}")
            return True

        except Exception as e:
            logger.error(f"[GoldDataset] Failed to promote incident {incident_id}: {e}")
            self.conn.rollback()
            return False

    # ──────────────────────────────────────────────────────────────────────────

    def run_regression_test(self, new_ai_logic_func) -> Dict[str, Any]:
        """
        Runs new AI logic against all Gold Dataset entries to detect regressions.
        Returns accuracy stats and PASSED / FAILED_REGRESSION status.
        """
        if not self.conn:
            return {"status": "ERROR", "error": "No DB connection"}
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, incident_data, final_rca FROM ai_gold_dataset")
                datasets = cur.fetchall()

            total = len(datasets)
            if total == 0:
                return {"status": "NO_DATA", "total_datasets": 0}

            passed = 0
            for ds in datasets:
                inc_data = ds[1]
                expected_rca = ds[2] or ""
                try:
                    ai_output = new_ai_logic_func(inc_data)
                    ai_rca = ai_output.get("rca", "") if isinstance(ai_output, dict) else str(ai_output)
                    # Fuzzy string match: RCA keyword must appear in AI output
                    key_token = expected_rca.split("|")[0].strip().lower()
                    if key_token and key_token in ai_rca.lower():
                        passed += 1
                except Exception as e:
                    logger.warning(f"[GoldDataset] Regression sub-test error: {e}")

            accuracy = (passed / total) * 100
            status = "PASSED" if accuracy > 90.0 else "FAILED_REGRESSION"
            logger.info(f"[GoldDataset] Regression Test: accuracy={accuracy:.1f}% ({passed}/{total}) → {status}")
            return {
                "total_datasets": total,
                "passed": passed,
                "accuracy": round(accuracy, 2),
                "status": status,
            }

        except Exception as e:
            logger.error(f"[GoldDataset] Regression test error: {e}")
            return {"status": "ERROR", "error": str(e)}
