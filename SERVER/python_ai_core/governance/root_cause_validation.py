import logging
import psycopg2
from typing import Dict, Any
import os

logger = logging.getLogger("RootCauseValidationEngine")

class RootCauseValidationEngine:
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
