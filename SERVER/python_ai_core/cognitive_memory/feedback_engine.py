import os
import json
import psycopg2
from typing import Dict, Any

class FeedbackEngine:
    def __init__(self):
        self.db_host = os.environ.get("DB_HOST", "postgres")
        self.db_port = os.environ.get("DB_PORT", "5432")
        self.db_name = os.environ.get("DB_NAME", "osi_system")
        self.db_user = os.environ.get("DB_USER", "postgres")
        self.db_password = os.environ.get("DB_PASSWORD", "postgres")

    def _get_conn(self):
        try:
            return psycopg2.connect(
                host=self.db_host, port=self.db_port, dbname=self.db_name, 
                user=self.db_user, password=self.db_password
            )
        except Exception:
            return None

    def process_feedback(self, engineer_id: str, action: str, incident_id: str, details: Dict[str, Any]):
        conn = self._get_conn()
        if not conn: return
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO incident_feedback (incident_id, engineer_id, feedback_action, feedback_details, created_at)
                    VALUES (%s, %s, %s, %s, NOW())
                """, (incident_id, engineer_id, action, json.dumps(details)))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()