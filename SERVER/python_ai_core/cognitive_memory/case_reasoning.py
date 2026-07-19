import os
import psycopg2
from typing import Dict, Any, List

class CaseBasedReasoning:
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

    def find_similar_cases(self, new_incident: Dict[str, Any], limit: int = 10) -> List[Dict[str, Any]]:
        cases = []
        conn = self._get_conn()
        if not conn: return cases
        
        try:
            with conn.cursor() as cur:
                title_query = f"%{new_incident.get('title', '')[:30]}%"
                cur.execute("""
                    SELECT id, title, description, status 
                    FROM incidents 
                    WHERE title ILIKE %s
                    LIMIT %s
                """, (title_query, limit))
                for row in cur.fetchall():
                    cases.append({
                        "id": row[0],
                        "title": row[1],
                        "description": row[2],
                        "status": row[3]
                    })
        except Exception:
            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
        finally:
            conn.close()
        return cases

    def calculate_similarity(self, case1: Dict[str, Any], case2: Dict[str, Any]) -> float:
        # Basic jaccard similarity on tokens
        c1_tokens = set(str(case1.get('title', '')).lower().split())
        c2_tokens = set(str(case2.get('title', '')).lower().split())
        if not c1_tokens or not c2_tokens: return 0.0
        intersection = c1_tokens.intersection(c2_tokens)
        union = c1_tokens.union(c2_tokens)
        return float(len(intersection)) / float(len(union))