import logging
import psycopg2
from typing import Dict, Any
import os

logger = logging.getLogger("RootCauseValidationEngine")

class RootCauseValidationEngine:
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

    def validate_root_cause(self, incident_id: str, ai_prediction: str, human_rca: str, layer_diff: int, reason: str):
        """
        AI membandingkan Prediksi RCA-nya dengan kesimpulan Engineer akhir.
        Berguna untuk menghitung Prediction Distance.
        """
        if not self.conn: return
        
        root_cause_match = (ai_prediction.lower() == human_rca.lower())
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ai_rca_validation (
                        incident_id, ai_pred, human_rca, layer_difference, root_cause_match, reason
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (incident_id, ai_prediction, human_rca, layer_diff, root_cause_match, reason))
            self.conn.commit()
            logger.info(f"Recorded RCA Validation for {incident_id}. Match: {root_cause_match}")
        except Exception as e:
            logger.error(f"Failed to record RCA validation: {e}")
            self.conn.rollback()
