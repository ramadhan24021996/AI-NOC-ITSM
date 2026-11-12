import logging
import psycopg2
from typing import Dict, Any
import os

logger = logging.getLogger("PromptEvaluationEngine")

class PromptEvaluationEngine:
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
                    password=os.getenv("DB_PASSWORD", "")
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

    def evaluate_prompt_version(self, version_tag: str, test_results: Dict[str, Any]) -> str:
        """
        Mengevaluasi Prompt baru terhadap Gold Dataset.
        Memblokir deployment jika performa menurun.
        """
        if not self.conn: return "ERROR"
        
        diag_acc = test_results.get("diagnosis_accuracy", 0.0)
        rca_acc = test_results.get("rca_accuracy", 0.0)
        hallucination = test_results.get("hallucination_rate", 100.0)
        agreement = test_results.get("engineer_agreement", 0.0)
        latency = test_results.get("latency_sec", 999.0)
        
        # Hard constraints for Enterprise AI
        status = "PASS"
        if rca_acc < 90.0 or hallucination > 2.0 or latency > 5.0:
            status = "BLOCK_DEPLOYMENT"
            
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ai_prompt_evaluation (
                        prompt_version, diag_accuracy, rca_accuracy, 
                        hallucination_rate, engineer_agreement, latency_sec, status
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (version_tag, diag_acc, rca_acc, hallucination, agreement, latency, status))
            self.conn.commit()
            logger.info(f"Prompt {version_tag} Evaluated: {status}")
            return status
        except Exception as e:
            logger.error(f"Failed to evaluate prompt: {e}")
            self.conn.rollback()
            return "ERROR"
