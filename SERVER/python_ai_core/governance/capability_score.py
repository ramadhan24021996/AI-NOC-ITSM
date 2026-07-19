import logging
import psycopg2
from typing import Dict, Any
import os

logger = logging.getLogger("CapabilityScoreEngine")

class CapabilityScoreEngine:
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
