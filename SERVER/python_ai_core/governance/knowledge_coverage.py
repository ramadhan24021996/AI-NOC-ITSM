import logging
import psycopg2
from typing import Dict, Any, List
import os

logger = logging.getLogger("KnowledgeCoverageEngine")

class KnowledgeCoverageEngine:
    def __init__(self, db_conn=None):
        self.conn = db_conn
        if not self.conn:
            self.conn = psycopg2.connect(
                host=os.getenv("DB_HOST", "127.0.0.1"),
                port=os.getenv("DB_PORT", "5432"),
                database=os.getenv("DB_NAME", "osi_system"),
                user=os.getenv("DB_USER", "postgres"),
                password=os.getenv("DB_PASSWORD", "postgres")
            )

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
