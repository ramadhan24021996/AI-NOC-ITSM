import logging
import psycopg2
from typing import Dict, Any
import os

logger = logging.getLogger("EvidenceQualityEngine")

class EvidenceQualityEngine:
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

    def calculate_evidence_score(self, incident_id: str, telemetry: Dict[str, Any]) -> Dict[str, Any]:
        """
        Menghitung Kualitas Evidence. AI harus meminta data tambahan jika kualitas rendah.
        """
        if not self.conn: return dict()
        
        metrics = telemetry.get("metrics", {})
        logs = telemetry.get("logs", {})
        topology = telemetry.get("topology", {})
        
        metrics_score = 100.0 if metrics else 0.0
        logs_score = 95.0 if logs else 0.0
        topology_score = 100.0 if topology else 0.0
        db_logs_score = 100.0 if logs.get("db") else 0.0
        fw_logs_score = 100.0 if logs.get("firewall") else 0.0
        
        weights = [metrics_score, logs_score, topology_score, db_logs_score, fw_logs_score]
        overall_score = sum(weights) / len(weights)
        
        missing = []
        if db_logs_score == 0: missing.append("Database telemetry unavailable.")
        if fw_logs_score == 0: missing.append("Firewall logs unavailable.")
        if metrics_score == 0: missing.append("Host metrics unavailable.")
        
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO ai_evidence_quality (
                        incident_id, metrics_score, logs_score, topology_score, overall_score
                    ) VALUES (%s, %s, %s, %s, %s)
                """, (incident_id, metrics_score, logs_score, topology_score, overall_score))
            self.conn.commit()
        except Exception as e:
            logger.error(f"Failed to record evidence score: {e}")
            self.conn.rollback()

        return {
            "overall_evidence_score": overall_score,
            "missing_evidence": missing,
            "needs_more_evidence": overall_score < 80.0
        }
