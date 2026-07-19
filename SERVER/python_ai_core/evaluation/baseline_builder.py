import os
import logging
import json
import statistics
import psycopg2
from typing import Dict, List, Any

logger = logging.getLogger("BASELINE_BUILDER")

class BaselineBuilder:
    """
    Menghitung Baseline (Mean & Std Dev) dari metrik harian selama Validation Sprint.
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
                self._calculate_and_store_baselines(conn, 7)
                self._calculate_and_store_baselines(conn, 30)
            logger.info("[BASELINE] Successfully updated KPI baselines.")
        except Exception as e:
            logger.error(f"[BASELINE] Failed to run: {e}")

    def _calculate_and_store_baselines(self, conn, days: int):
        # Extract flat metrics for the last N days
        metrics_history = self._get_historical_metrics(conn, days)
        
        with conn.cursor() as cur:
            for domain, metrics in metrics_history.items():
                for metric_name, values in metrics.items():
                    if len(values) < 3:
                        continue # Not enough data for a meaningful baseline
                        
                    mean_val = statistics.mean(values)
                    std_dev = statistics.stdev(values) if len(values) > 1 else 0.0
                    
                    cur.execute("""
                        INSERT INTO kpi_baselines (metric_name, domain, window_days, mean_value, std_dev, sample_size)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (metric_name, domain, days, mean_val, std_dev, len(values)))

    def _get_historical_metrics(self, conn, days: int) -> Dict[str, Dict[str, List[float]]]:
        history = {}
        with conn.cursor() as cur:
            cur.execute("""
                SELECT report_type, metrics 
                FROM cognitive_kpis 
                WHERE created_at >= NOW() - INTERVAL '%s days'
            """, (days,))
            
            for report_type, metrics in cur.fetchall():
                if report_type not in history:
                    history[report_type] = {}
                    
                for k, v in metrics.items():
                    if isinstance(v, (int, float)) and not isinstance(v, bool):
                        if k not in history[report_type]:
                            history[report_type][k] = []
                        history[report_type][k].append(float(v))
                        
        return history

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    BaselineBuilder().run()

import asyncio
async def daemon(interval_hours: int = 24):
    while True:
        try:
            await asyncio.to_thread(BaselineBuilder().run)
            await asyncio.sleep(interval_hours * 3600)
        except Exception as e:
            logger.error(f"[BASELINE] Daemon error: {e}")
            await asyncio.sleep(60)
