import os
import json
import psycopg2
from typing import Dict, Any, List

class SemanticMemory:
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

    def store_knowledge(self, knowledge_type: str, content: Dict[str, Any]):
        conn = self._get_conn()
        if not conn: return
        try:
            with conn.cursor() as cur:
                # Store in golden_solutions table as generalized semantic knowledge
                cur.execute("""
                    INSERT INTO golden_solutions (title, description, layer, confidence_score, metadata)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    content.get("title", f"Knowledge: {knowledge_type}"),
                    content.get("description", str(content)),
                    content.get("layer", "L7"),
                    content.get("confidence", 80.0),
                    json.dumps(content)
                ))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    def retrieve_knowledge(self, query: str) -> List[Dict[str, Any]]:
        results = []
        conn = self._get_conn()
        if not conn: return results
        try:
            with conn.cursor() as cur:
                # Simple keyword search on golden_solutions
                search_term = f"%{query}%"
                cur.execute("""
                    SELECT title, description, layer, confidence_score, metadata 
                    FROM golden_solutions 
                    WHERE title ILIKE %s OR description ILIKE %s
                    LIMIT 5
                """, (search_term, search_term))
                for row in cur.fetchall():
                    meta = row[4]
                    if isinstance(meta, str):
                        try:
                            meta = json.loads(meta)
                        except Exception:
                            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
                    results.append({
                        "title": row[0],
                        "description": row[1],
                        "layer": row[2],
                        "confidence": row[3],
                        "metadata": meta
                    })
        except Exception:
            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
        finally:
            conn.close()
        return results