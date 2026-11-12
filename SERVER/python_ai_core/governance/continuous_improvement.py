import logging
import psycopg2
from typing import Dict, Any
import os
import json

logger = logging.getLogger("ContinuousImprovementEngine")

class ContinuousImprovementEngine:
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

    def generate_weekly_report(self) -> Dict[str, Any]:
        """
        Menghasilkan laporan evaluasi diri mingguan untuk AI.
        """
        if not self.conn: return dict()
        
        report = {
            "knowledge_gaps": 0,
            "playbook_failures": 0,
            "hallucination_rate": 0.0,
            "recommendation_accuracy": 0.0,
            "engineer_agreement": 0.0,
            "new_incident_patterns": 0,
            "suggestions": {},
            "overall_improvement": 0.0
        }
        
        try:
            with self.conn.cursor() as cur:
                # Get actual stats from benchmark table
                cur.execute("""
                    SELECT 
                        COUNT(*), 
                        SUM(CASE WHEN false_positive OR false_negative THEN 1 ELSE 0 END),
                        SUM(CASE WHEN ai_solution_correct THEN 1 ELSE 0 END),
                        SUM(CASE WHEN ai_diagnosis_correct THEN 1 ELSE 0 END)
                    FROM ai_engineer_benchmark 
                    WHERE created_at > NOW() - INTERVAL '7 days'
                """)
                row = cur.fetchone()
                if row and row[0] > 0:
                    total = row[0]
                    hallucinations = row[1] or 0
                    sol_correct = row[2] or 0
                    diag_correct = row[3] or 0
                    
                    report["hallucination_rate"] = (hallucinations / total) * 100.0
                    report["recommendation_accuracy"] = (sol_correct / total) * 100.0
                    report["engineer_agreement"] = (diag_correct / total) * 100.0

                # Get playbook failures
                cur.execute("""
                    SELECT COUNT(*) FROM ai_recommendation_benchmark
                    WHERE was_successful = FALSE AND recorded_at > NOW() - INTERVAL '7 days'
                """)
                pb_row = cur.fetchone()
                if pb_row:
                    report["playbook_failures"] = pb_row[0]

                # Get knowledge gaps (incidents with insufficient evidence)
                cur.execute("""
                    SELECT COUNT(*) FROM incidents
                    WHERE (evidence ILIKE '%Insufficient Evidence%' OR confidence < 0.5)
                    AND timestamp > NOW() - INTERVAL '7 days'
                """)
                gap_row = cur.fetchone()
                if gap_row:
                    report["knowledge_gaps"] = gap_row[0]
                    
        except Exception as e:
            logger.error(f"Failed to calculate metrics: {e}")
            self.conn.rollback()

        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ai_continuous_improvement (
                        knowledge_gaps, playbook_failures, hallucination_rate, suggestion_payload
                    ) VALUES (%s, %s, %s, %s)
                """, (
                    report["knowledge_gaps"], report["playbook_failures"], 
                    report["hallucination_rate"], json.dumps(report["suggestions"])
                ))
            self.conn.commit()
            logger.info("Generated Weekly Improvement Report.")
        except Exception as e:
            logger.error(f"Failed to save weekly report: {e}")
            self.conn.rollback()

        return report
