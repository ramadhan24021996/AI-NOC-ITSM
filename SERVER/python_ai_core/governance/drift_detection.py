import logging
import psycopg2
from typing import Dict, Any, List
import datetime
import os

logger = logging.getLogger("DriftDetectionEngine")

class DriftDetectionEngine:
    def __init__(self, db_conn=None):
        self.conn = db_conn
        if not self.conn:
            self.db_host = os.getenv("DB_HOST", "127.0.0.1")
            self.db_port = os.getenv("DB_PORT", "5432")
            self.db_name = os.getenv("DB_NAME", "osi_system")
            self.user = os.getenv("DB_USER", "postgres")
            self.password = os.getenv("DB_PASSWORD", "postgres")
            self.conn = psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.user,
                password=self.password
            )

    def analyze_playbook_drift(self, playbook_name: str, threshold_pct: float = 15.0) -> Dict[str, Any]:
        """
        Mendeteksi Playbook Drift dengan membandingkan success rate 90 hari terakhir
        dengan 30 hari terakhir.
        """
        if not self.conn: return {"drift_detected": False, "drift_percentage": 0.0}
        try:
            with self.conn.cursor() as cur:
                # Baseline 90-30 days ago
                cur.execute("""
                    SELECT COUNT(*), SUM(CASE WHEN was_successful THEN 1 ELSE 0 END)
                    FROM ai_recommendation_benchmark
                    WHERE recommendation ILIKE %s
                      AND recorded_at >= NOW() - INTERVAL '90 days'
                      AND recorded_at < NOW() - INTERVAL '30 days'
                """, (f"%{playbook_name}%",))
                base_row = cur.fetchone()
                
                # Current 30 days
                cur.execute("""
                    SELECT COUNT(*), SUM(CASE WHEN was_successful THEN 1 ELSE 0 END)
                    FROM ai_recommendation_benchmark
                    WHERE recommendation ILIKE %s
                      AND recorded_at >= NOW() - INTERVAL '30 days'
                """, (f"%{playbook_name}%",))
                curr_row = cur.fetchone()

                base_rate = (base_row[1] / base_row[0] * 100) if base_row and base_row[0] > 0 else 100.0
                curr_rate = (curr_row[1] / curr_row[0] * 100) if curr_row and curr_row[0] > 0 else base_rate

                drift = base_rate - curr_rate

                if drift > threshold_pct:
                    logger.warning(f"DRIFT DETECTED: Playbook '{playbook_name}' dropped by {drift:.1f}%")
                    self._log_drift("PLAYBOOK", playbook_name, base_rate, curr_rate, drift)
                    return {
                        "drift_detected": True,
                        "drift_percentage": drift,
                        "message": f"Playbook {playbook_name} mengalami penurunan success rate {drift:.1f}% dibanding baseline."
                    }
                
                return {"drift_detected": False, "drift_percentage": drift}
        except Exception as e:
            logger.error(f"Failed to analyze playbook drift: {e}")
        return {"drift_detected": False, "drift_percentage": 0.0}

    def _log_drift(self, metric_type: str, target_name: str, base: float, curr: float, drift: float):
        if not self.conn: return
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ai_drift_metrics (metric_type, target_name, baseline_success_rate, current_success_rate, drift_percentage)
                    VALUES (%s, %s, %s, %s, %s)
                """, (metric_type, target_name, base, curr, drift))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to log drift metric: {e}")
            self.conn.rollback()

