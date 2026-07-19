import logging
import psycopg2
from typing import Dict, Any, List
import json
import os

logger = logging.getLogger("GoldDatasetEngine")

class GoldDatasetEngine:
    def __init__(self, db_conn=None):
        self.conn = db_conn
        if not self.conn:
            self.db_host = os.getenv("DB_HOST", "127.0.0.1")
            self.db_port = os.getenv("DB_PORT", "5432")
            self.db_name = os.getenv("DB_NAME", "osi_system")
            self.user = os.getenv("DB_USER", "postgres")
            self.password = os.getenv("DB_PASSWORD", "postgres")
            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.user,
                password=self.password
            )

    def extract_incident_to_gold(self, incident_id: str):
        """
        Takes a resolved incident and promotes it to the Gold Dataset.
        Only called if the incident was successfully resolved by humans or AI.
        """
        if not self.conn: return False
        try:
            with self.conn.cursor() as cur:
                # Fetch full incident details (Simplified)
                cur.execute("SELECT raw_data FROM incidents WHERE incident_id = %s", (incident_id,))
                row = cur.fetchone()
                if not row:
                    return False
                
                raw_data = row[0]
                
                cur.execute("""
                    INSERT INTO ai_gold_dataset (
                        incident_data, final_rca, engineer_action, outcome
                    ) VALUES (%s, %s, %s, %s)
                """, (
                    json.dumps(raw_data), 
                    "Extract from RCA DB", 
                    "Extract from Audit DB", 
                    "SUCCESS"
                ))
            self.conn.commit()
            logger.info(f"Incident {incident_id} promoted to Gold Dataset.")
            return True
        except Exception as e:
            logger.error(f"Failed to promote to Gold Dataset: {e}")
            self.conn.rollback()
            return False

    def run_regression_test(self, new_ai_logic_func) -> Dict[str, Any]:
        """
        Runs the new AI logic (e.g. updated prompt or causal engine)
        against all Gold Datasets to prevent regressions.
        """
        if not self.conn: return {"status": "ERROR", "error": "No DB connection"}
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT id, incident_data, final_rca FROM ai_gold_dataset")
                datasets = cur.fetchall()

            total = len(datasets)
            if total == 0:
                return {"status": "NO_DATA"}

            passed = 0
            for ds in datasets:
                inc_data = ds[1]
                expected_rca = ds[2]
                
                # synthetic invocation of new logic
                ai_output = new_ai_logic_func(inc_data)
                
                # Compare similarity (Basic string match for this example)
                if expected_rca.lower() in ai_output.get("rca", "").lower():
                    passed += 1

            accuracy = (passed / total) * 100
            logger.info(f"Regression Test Complete. Accuracy: {accuracy:.1f}%")
            return {
                "total_datasets": total,
                "passed": passed,
                "accuracy": accuracy,
                "status": "PASSED" if accuracy > 90.0 else "FAILED_REGRESSION"
            }
        except Exception as e:
            logger.error(f"Regression test failed: {e}")
            return {"status": "ERROR", "error": str(e)}
