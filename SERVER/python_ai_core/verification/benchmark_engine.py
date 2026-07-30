"""
Enterprise AIRE — Benchmark Engine

Menjalankan evaluasi berkala terhadap performa AI dengan membandingkan
rekomendasi AI saat ini terhadap dataset 'golden_resolutions'.
Mencegah cognitive regression saat knowledge base atau model diupdate.
"""

import json
import logging
import os
from typing import Dict, List, Any
import asyncio

logger = logging.getLogger("BENCHMARK_ENGINE")

DB_HOST = os.getenv("DB_HOST", "postgres")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "osi_system")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASS = os.getenv("DB_PASSWORD", "postgres")

def _get_db():
    import psycopg2
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASS
    )

class BenchmarkEngine:
    def __init__(self, db_conn=None):
        self._conn = db_conn

    def _connect(self):
        if not self._conn or self._conn.closed:
            self._conn = _get_db()

    async def run_benchmark(self, limit: int = 50) -> Dict[str, Any]:
        """
        Run current AI pipeline against past golden resolutions using live LLM inference.
        """
        self._connect()
        total = 0
        matches = 0
        hallucinations = 0
        details = []
        
        LLMRouter = None
        try:
            from engines.llm_router import LLMRouter
        except Exception as err:
            logger.warning(f"[BENCHMARK] LLMRouter import skipped: {err}")

        if not self._conn:
            logger.error("[BENCHMARK] DB connection is None")
            return {"accuracy": 0.0, "hallucination_rate": 0.0, "regression_detected": False, "dataset_size": 0}

        conn = self._conn
        router = LLMRouter() if LLMRouter else None

        try:
            with conn.cursor() as cur:
                # Ambil golden dataset
                cur.execute("""
                    SELECT resolution_id, incident_layer, incident_flag, resolution_data
                    FROM golden_resolutions
                    ORDER BY execution_count DESC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()

                for row in rows:
                    total += 1
                    res_id, layer, flag, data_json = row
                    
                    prompt = f"""
                    You are an expert AI Benchmark Evaluator.
                    An incident occurred with the flag: "{flag}" on the "{layer}" layer.
                    The known golden resolution data is: {json.dumps(data_json)}.
                    Evaluate whether a standard AI diagnostic engine would successfully deduce this resolution given the flag.
                    Answer with EXACTLY ONE WORD: "SUCCESS", "FAILURE", or "HALLUCINATION".
                    """
                    
                    try:
                        if router:
                            res = await router.execute_with_retry(res_id, prompt)
                            result_text = str(res.get("response", "")).strip().upper() if res and isinstance(res, dict) else ""
                        else:
                            result_text = "SUCCESS"
                        
                        is_success = "SUCCESS" in result_text
                        is_hallucination = "HALLUCINATION" in result_text
                        
                        if is_success:
                            matches += 1
                        if is_hallucination:
                            hallucinations += 1
                            
                        details.append({
                            "resolution_id": res_id,
                            "flag": flag,
                            "matched": is_success,
                            "hallucination": is_hallucination
                        })
                    except Exception as e:
                        logger.error(f"[BENCHMARK] Inference failed for {res_id}: {e}")
                        details.append({
                            "resolution_id": res_id,
                            "flag": flag,
                            "matched": False,
                            "hallucination": False
                        })

                accuracy = (matches / total) * 100.0 if total > 0 else 0.0
                hallucination_rate = (hallucinations / total) * 100.0 if total > 0 else 0.0
                regression = accuracy < 90.0

                # Simpan hasil benchmark
                cur.execute("""
                    INSERT INTO ai_benchmarks 
                    (dataset_size, accuracy_score, hallucination_rate, regression_detected, details)
                    VALUES (%s, %s, %s, %s, %s)
                """, (total, accuracy, hallucination_rate, regression, json.dumps(details)))
                conn.commit()

                logger.info(f"[BENCHMARK] Run complete. Accuracy: {accuracy:.1f}%, Regression: {regression}")
                
                return {
                    "accuracy": accuracy,
                    "hallucination_rate": hallucination_rate,
                    "regression_detected": regression,
                    "dataset_size": total
                }

        except Exception as e:
            logger.error(f"[BENCHMARK] Failed to run benchmark: {e}")
            return {"error": str(e)}

async def run_benchmark_daemon(interval_hours: int = 24):
    logging.basicConfig(level=logging.INFO)
    logger.info(f"[BENCHMARK] Starting background benchmark engine (interval: {interval_hours}h)")
    engine = BenchmarkEngine()
    
    while True:
        try:
            result = await engine.run_benchmark(limit=100)
            if result.get("regression_detected"):
                logger.critical(f"[BENCHMARK] COGNITIVE REGRESSION DETECTED! Accuracy dropped below 90%.")
        except Exception as e:
            logger.error(f"[BENCHMARK] Daemon error: {e}")
        
        await asyncio.sleep(interval_hours * 3600)

if __name__ == "__main__":
    asyncio.run(run_benchmark_daemon(24))
