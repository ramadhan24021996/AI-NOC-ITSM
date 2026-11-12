import logging
import psycopg2
from typing import Dict, Any
import os

logger = logging.getLogger("CapabilityScoreEngine")

class CapabilityScoreEngine:
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

    def record_capability_score(self, scores: Dict[str, float]):
        """
        Merekam tingkat kesehatan AI secara keseluruhan.
        """
        if not self.conn: return
        
        overall = sum(scores.values()) / len(scores) if scores else 0.0
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ai_capability_score (
                        monitoring_score, reasoning_score, knowledge_score, 
                        conversation_score, prediction_score, trust_score, 
                        evidence_score, governance_score, overall_score
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    scores.get("monitoring", 0.0), scores.get("reasoning", 0.0),
                    scores.get("knowledge", 0.0), scores.get("conversation", 0.0),
                    scores.get("prediction", 0.0), scores.get("trust", 0.0),
                    scores.get("evidence", 0.0), scores.get("governance", 0.0),
                    overall
                ))
            self.conn.commit()
            logger.info(f"Recorded AI Capability Score. Overall: {overall:.1f}%")
        except Exception as e:
            logger.error(f"Failed to record capability score: {e}")
            self.conn.rollback()
