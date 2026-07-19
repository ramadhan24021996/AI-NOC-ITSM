import time
import json
from typing import Dict, Any, List

import os
import psycopg2

class MemoryEngine:
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

    def store_incident(self, incident_data: Dict[str, Any]):
        conn = self._get_conn()
        if not conn: return
        try:
            with conn.cursor() as cur:
                # Insert into ai_audit_trail
                cur.execute("""
                    INSERT INTO ai_audit_trail (incident_id, ai_confidence, reasoning_log, created_at)
                    VALUES (%s, %s, %s, NOW())
                    ON CONFLICT (incident_id) DO UPDATE SET 
                        ai_confidence = EXCLUDED.ai_confidence,
                        reasoning_log = EXCLUDED.reasoning_log
                """, (
                    incident_data.get("id", "UNKNOWN"),
                    incident_data.get("confidence", 0.0),
                    json.dumps(incident_data)
                ))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    def retrieve_incident(self, incident_id: str) -> Dict[str, Any]:
        conn = self._get_conn()
        if not conn: return dict()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT reasoning_log FROM ai_audit_trail WHERE incident_id = %s", (incident_id,))
                row = cur.fetchone()
                if row and row[0]:
                    if isinstance(row[0], str):
                        return json.loads(row[0])
                    return row[0]
        except Exception:
            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
        finally:
            conn.close()
        return dict()

    def update_trust_score(self, incident_id: str, trust_score: float):
        conn = self._get_conn()
        if not conn: return
        try:
            with conn.cursor() as cur:
                # Update agent trust scores based on incident success
                # Need the agent associated with this incident, but since we don't have it here,
                # we just update ai_confidence in audit trail as a proxy
                cur.execute("""
                    UPDATE ai_audit_trail 
                    SET ai_confidence = %s
                    WHERE incident_id = %s
                """, (trust_score, incident_id))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()