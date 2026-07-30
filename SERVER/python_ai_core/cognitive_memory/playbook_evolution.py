import os
import json
import psycopg2
from typing import Dict, Any, List

class PlaybookEvolution:
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

    def evaluate_playbook(self, playbook_id: str, execution_data: Dict[str, Any]):
        conn = self._get_conn()
        if not conn: return
        try:
            with conn.cursor() as cur:
                # Log execution metric (we just update the description or metadata in governance_sops)
                cur.execute("UPDATE governance_sops SET updated_at = NOW() WHERE id = %s", (playbook_id,))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    def propose_new_playbook(self, old_playbook_id: str, reason: str, expected_benefit: str, risk: str, evidence: str) -> Dict[str, Any]:
        # Validate historical evidence before allowing playbook evolution
        conn = self._get_conn()
        failure_count = 0
        if conn:
            try:
                with conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM ai_recommendation_benchmark
                        WHERE was_successful = FALSE AND recommendation ILIKE %s
                    """, (f"%{old_playbook_id}%",))
                    row = cur.fetchone()
                    if row: failure_count = row[0]
            except Exception:
                pass
            finally:
                conn.close()

        if failure_count == 0:
            return {
                "status": "REJECTED",
                "reason": "Insufficient historical failure evidence to justify playbook evolution."
            }

        proposal = {
            "old_playbook_id": old_playbook_id,
            "reason": reason,
            "expected_benefit": expected_benefit,
            "risk": risk,
            "evidence": evidence,
            "status": "PROPOSED"
        }
        return proposal