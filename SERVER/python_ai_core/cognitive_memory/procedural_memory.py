import os
import json
import psycopg2
from typing import Dict, Any, List

class ProceduralMemory:
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

    def get_procedure(self, action_type: str) -> Dict[str, Any]:
        conn = self._get_conn()
        if not conn: return dict()
        try:
            with conn.cursor() as cur:
                cur.execute("SELECT name, description, steps FROM governance_sops WHERE name = %s LIMIT 1", (action_type,))
                row = cur.fetchone()
                if row:
                    steps = row[2]
                    if isinstance(steps, str):
                        try:
                            steps = json.loads(steps)
                        except:
                            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
                    return {"name": row[0], "description": row[1], "steps": steps}
        except Exception:
            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
        finally:
            conn.close()
        return dict()

    def add_procedure(self, action_type: str, steps: List[str]):
        conn = self._get_conn()
        if not conn: return
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO governance_sops (name, description, steps, created_at)
                    VALUES (%s, %s, %s, NOW())
                """, (action_type, f"Auto-learned procedure for {action_type}", json.dumps(steps)))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()