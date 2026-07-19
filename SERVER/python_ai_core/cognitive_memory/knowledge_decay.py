import os
import psycopg2
from typing import Dict, Any, Optional

class DecayEngine:
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

    def apply_decay(self, knowledge_id: Optional[str] = None):
        # Decrease confidence if not used for a long time
        conn = self._get_conn()
        if not conn: return
        try:
            with conn.cursor() as cur:
                if knowledge_id:
                    # Decay specific
                    cur.execute("""
                        UPDATE golden_solutions 
                        SET confidence_score = GREATEST(0, confidence_score - 1.0)
                        WHERE id = %s
                    """, (knowledge_id,))
                else:
                    # Decay all old
                    cur.execute("""
                        UPDATE golden_solutions 
                        SET confidence_score = GREATEST(0, confidence_score - 0.1)
                        WHERE created_at < NOW() - INTERVAL '30 days'
                    """)
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()