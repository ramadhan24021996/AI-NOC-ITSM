import logging
import psycopg2
from typing import Dict, Any, List
import json
import os

logger = logging.getLogger("BenchmarkEngine")

class BenchmarkEngine:
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

    # ── O1: Engineer Benchmark Engine ─────────────────────────────────────────

    def record_engineer_benchmark(self, incident_id: str, ai_data: Dict[str, Any], human_data: Dict[str, Any], outcome: Dict[str, Any]):
        """
        Record the performance of AI vs Human on an incident.
        """
        if not self.conn: return
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ai_engineer_benchmark (
                        incident_id, ai_diagnosis, human_diagnosis, ai_rca, human_rca,
                        ai_solution, human_solution, final_resolution, 
                        ai_diagnosis_correct, ai_rca_correct, ai_solution_correct, 
                        false_positive, false_negative
                    ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                """, (
                    incident_id,
                    ai_data.get("diagnosis"), human_data.get("diagnosis"),
                    ai_data.get("rca"), human_data.get("rca"),
                    ai_data.get("solution"), human_data.get("solution"),
                    outcome.get("final_resolution"),
                    outcome.get("ai_diagnosis_correct"), outcome.get("ai_rca_correct"),
                    outcome.get("ai_solution_correct"),
                    outcome.get("false_positive", False), outcome.get("false_negative", False)
                ))
            self.conn.commit()
            logger.info(f"Recorded Engineer Benchmark for {incident_id}")
        except Exception as e:
            logger.error(f"Failed to record benchmark: {e}")
            self.conn.rollback()

    def get_benchmark_report(self) -> Dict[str, Any]:
        """
        Calculate overall AI vs Human performance accuracy.
        """
        if not self.conn: return dict()
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT 
                        COUNT(*) as total,
                        SUM(CASE WHEN ai_diagnosis_correct THEN 1 ELSE 0 END) as diag_correct,
                        SUM(CASE WHEN ai_rca_correct THEN 1 ELSE 0 END) as rca_correct,
                        SUM(CASE WHEN ai_solution_correct THEN 1 ELSE 0 END) as sol_correct,
                        SUM(CASE WHEN false_positive THEN 1 ELSE 0 END) as fp,
                        SUM(CASE WHEN false_negative THEN 1 ELSE 0 END) as fn
                    FROM ai_engineer_benchmark
                """)
                row = cur.fetchone()
                if row and row[0] > 0:
                    total = row[0]
                    return {
                        "total_comparisons": total,
                        "diagnosis_accuracy": (row[1] / total) * 100,
                        "rca_accuracy": (row[2] / total) * 100,
                        "recommendation_accuracy": (row[3] / total) * 100,
                        "false_positive_rate": (row[4] / total) * 100,
                        "false_negative_rate": (row[5] / total) * 100
                    }
        except Exception as e:
            logger.error(f"Failed to generate benchmark report: {e}")
        return dict()

    # ── O3: Recommendation Benchmark Engine ───────────────────────────────────

    def record_recommendation_feedback(self, incident_id: str, recommendation: str, was_selected: bool, was_successful: bool, downtime_min: float, mttr_min: float):
        """
        Record feedback loop for RLHF (Recommendation Benchmarking).
        """
        if not self.conn: return
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ai_recommendation_benchmark (
                        incident_id, recommendation, was_selected, was_successful, downtime_minutes, mttr_minutes
                    ) VALUES (%s, %s, %s, %s, %s, %s)
                """, (incident_id, recommendation, was_selected, was_successful, downtime_min, mttr_min))
            self.conn.commit()
            logger.info(f"Recorded recommendation feedback for {incident_id}: {recommendation}")
        except Exception as e:
            logger.error(f"Failed to record recommendation feedback: {e}")
            self.conn.rollback()

    def get_recommendation_priority(self, recommendation: str) -> float:
        """
        Calculate dynamic confidence for a recommendation based on production success rates.
        """
        if not self.conn: return 50.0
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    SELECT COUNT(*), SUM(CASE WHEN was_successful THEN 1 ELSE 0 END)
                    FROM ai_recommendation_benchmark
                    WHERE recommendation ILIKE %s AND was_selected = TRUE
                """, (f"%{recommendation}%",))
                row = cur.fetchone()
                if row and row[0] > 0:
                    return (row[1] / row[0]) * 100.0
        except Exception as e:
            logger.error(f"Failed to get priority: {e}")
        return 50.0  # Default unknown

