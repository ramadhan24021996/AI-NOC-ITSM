import logging
import psycopg2
from typing import Dict, Any, List
import os

logger = logging.getLogger("KnowledgeCoverageEngine")

class KnowledgeCoverageEngine:
    def __init__(self, db_conn=None):
        self._owns_conn = db_conn is None
        self.conn = db_conn
        if not self.conn:
            try:
                from shared.db_pool import get_db_connection
                self.conn = get_db_connection()
            except Exception:
                db_host = os.getenv("DB_HOST", "127.0.0.1")
                self.conn = psycopg2.connect(
                    host=db_host,
                    port=os.getenv("DB_PORT", "5433" if db_host in ("127.0.0.1", "localhost") else "5432"),
                    database=os.getenv("DB_NAME", "osi_system"),
                    user=os.getenv("DB_USER", "postgres"),
                    password=os.getenv("DB_PASSWORD", "[REDACTED_DB_PASS]")
                )

    def close(self):
        if getattr(self, "_owns_conn", False) and getattr(self, "conn", None) is not None:
            try:
                self.conn.close()
            except Exception:
                pass
            self.conn = None

    def __del__(self):
        self.close()

    def calculate_coverage(self, domains: List[str]) -> Dict[str, float]:
        """
        Menghitung seberapa luas pengetahuan AI untuk suatu domain.
        Simulasi pembacaan ke Vector DB.
        """
        if not self.conn: return dict()
        
        coverage = {}
        try:
            with self.conn.cursor() as cur:
                for domain in domains:
                    # Query nyata ke tabel ai_knowledge_coverage untuk mengukur cakupan pengetahuan
                    cur.execute("SELECT coverage_percentage FROM ai_knowledge_coverage WHERE domain = %s", (domain,))
                    row = cur.fetchone()
                    if row:
                        coverage[domain] = row[0]
                    else:
                        coverage[domain] = 0.0
            return coverage
        except Exception as e:
            logger.error(f"Failed to calculate knowledge coverage: {e}")
            return dict()

    def get_knowledge_gaps(self, threshold: float = 85.0) -> List[str]:
        """
        Mengidentifikasi area teknologi yang kurang dipahami AI.
        """
        if not self.conn: return list()
        
        gaps = []
        try:
            with self.conn.cursor() as cur:
                cur.execute("SELECT domain FROM ai_knowledge_coverage WHERE coverage_percentage < %s", (threshold,))
                rows = cur.fetchall()
                for r in rows:
                    gaps.append(r[0])
            return gaps
        except Exception as e:
            logger.error(f"Failed to fetch knowledge gaps: {e}")
            return list()
