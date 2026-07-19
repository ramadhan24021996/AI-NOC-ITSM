import os
import logging
import psycopg2
from typing import Dict, List, Any

logger = logging.getLogger("DRIFT_DETECTOR")

class DriftDetector:
    """
    Mendeteksi apakah nilai KPI terbaru menyimpang (drift) secara signifikan
    dibandingkan dengan baseline 7 hari.
    """
    def __init__(self):
        self.db_params = {
            "host": os.getenv("DB_HOST", "postgres"),
            "port": os.getenv("DB_PORT", "5432"),
            "database": os.getenv("DB_NAME", "osi_system"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", "postgres")
        }

    def run(self):
        try:
            with psycopg2.connect(**self.db_params) as conn:
                self._detect_drifts(conn)
            logger.info("[DRIFT] Successfully completed drift detection cycle.")
        except Exception as e:
            logger.error(f"[DRIFT] Failed to run: {e}")

    def _detect_drifts(self, conn):
        # Ambil baseline 7 hari terbaru
        baselines = {}
        with conn.cursor() as cur:
            cur.execute("""
                SELECT metric_name, domain, mean_value, std_dev 
                FROM kpi_baselines 
                WHERE window_days = 7 
                AND calculated_at >= NOW() - INTERVAL '1 day'
            """)
            for name, domain, mean, std in cur.fetchall():
                baselines[name] = {"mean": mean, "std_dev": std, "domain": domain}

            if not baselines:
                logger.info("[DRIFT] No baselines available for detection yet.")
                return

            # Ambil data hari ini (24 jam terakhir)
            cur.execute("""
                SELECT report_type, metrics 
                FROM cognitive_kpis 
                WHERE created_at >= NOW() - INTERVAL '1 day'
            """)
            
            latest_metrics = {}
            for report_type, metrics in cur.fetchall():
                for k, v in metrics.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        if k not in latest_metrics:
                            latest_metrics[k] = []
                        latest_metrics[k].append(float(v))
                        
            # Cek Drift
            for metric, vals in latest_metrics.items():
                if not vals or metric not in baselines:
                    continue
                    
                current_val = sum(vals) / len(vals) # Average of today
                b = baselines[metric]
                
                if b["std_dev"] == 0:
                    continue # Cannot calculate sigma
                    
                diff = current_val - b["mean"]
                sigma = abs(diff / b["std_dev"])
                
                # Jika deviasi > 2 Sigma, anggap sebagai drift (anomaly)
                if sigma > 2.0:
                    severity = "HIGH" if sigma > 3.0 else "MEDIUM"
                    logger.warning(f"⚠️ DRIFT DETECTED: {metric} is {current_val} (Baseline: {b['mean']}, Sigma: {sigma:.2f})")
                    
                    cur.execute("""
                        INSERT INTO kpi_drifts (metric_name, domain, current_value, baseline_mean, deviation_sigma, severity)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (metric, b["domain"], current_val, b["mean"], sigma, severity))

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    DriftDetector().run()

import asyncio
async def daemon(interval_hours: int = 24):
    while True:
        try:
            await asyncio.to_thread(DriftDetector().run)
            await asyncio.sleep(interval_hours * 3600)
        except Exception as e:
            logger.error(f"[DRIFT] Daemon error: {e}")
            await asyncio.sleep(60)
