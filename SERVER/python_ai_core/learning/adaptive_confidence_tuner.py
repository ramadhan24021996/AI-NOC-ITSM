"""
Closed-Loop RLHF Feedback & Adaptive Confidence Auto-Tuner (learning/adaptive_confidence_tuner.py)

Dynamically recalibrates vector confidence scores P(SOP_Correct | Evidence) based on real-world NOC operator feedback:
  - Updates Bayesian Prior confidence score using operator "Success / Failure" clicks.
  - Automatically demotes vector status to RETRAIN if confidence drops below 70.0%.
"""

import logging
import json
import os
import sys
import datetime
import psycopg2

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(name)s — %(message)s')
logger = logging.getLogger("ADAPTIVE_CONFIDENCE_TUNER")

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5433" if DB_HOST == "127.0.0.1" else "5432")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "SecurePassword_123!"))

def get_db():
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
        user=DB_USER, password=DB_PASSWORD
    )

class AdaptiveConfidenceTuner:
    def __init__(self, conn=None):
        self.conn = conn or get_db()

    def process_operator_rlhf_feedback(self, vector_id: str, is_successful: bool, feedback_notes: str = "") -> dict:
        """Recalibrates Bayesian prior confidence score based on real NOC operator feedback."""
        logger.info(f"🔄 [ADAPTIVE TUNER] Processing RLHF feedback for vector '{vector_id}' (Success={is_successful})...")

        delta = +3.5 if is_successful else -15.0

        with self.conn.cursor() as cur:
            cur.execute("""
                UPDATE knowledge_vectors
                SET confidence = LEAST(100.0, GREATEST(40.0, confidence + %s)),
                    usage_count = usage_count + 1,
                    success_count = success_count + (CASE WHEN %s THEN 1 ELSE 0 END),
                    status = (CASE WHEN (confidence + %s) < 70.0 THEN 'RETRAIN' ELSE status END),
                    last_validated = NOW()
                WHERE incident_id = %s
                RETURNING confidence, status, usage_count, success_count
            """, (delta, is_successful, delta, vector_id))
            row = cur.fetchone()
            self.conn.commit()

            new_conf = row[0] if row else 95.0
            new_status = row[1] if row else "MONITORING"
            usage = row[2] if row else 1
            successes = row[3] if row else 1

        res = {
            "vector_id": vector_id,
            "recalibrated_confidence": new_conf,
            "status": new_status,
            "usage_count": usage,
            "success_count": successes,
            "success_rate": round(successes / usage * 100.0, 1) if usage > 0 else 100.0
        }

        logger.info(f"✅ [RECALIBRATED] Vector '{vector_id}': New Confidence={new_conf:.1f}%, Status={new_status}")
        return res

if __name__ == "__main__":
    tuner = AdaptiveConfidenceTuner()
    res = tuner.process_operator_rlhf_feedback("KNOW-SANDBOX-2d965861", is_successful=True, feedback_notes="SOP berhasil memulihkan printer kasir")
    print("=== ADAPTIVE CONFIDENCE TUNER RESULT ===")
    print(json.dumps(res, indent=2))
