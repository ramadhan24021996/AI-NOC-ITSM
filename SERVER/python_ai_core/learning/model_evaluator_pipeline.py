"""
DYNAMIC MODEL EVALUATION PIPELINE (LLM PERFORMANCE SCORECARD)
Evaluates LLM performance real-time across 5 dimensions:
1. Latency (ms)
2. Accuracy (%)
3. Hallucination Rate (%)
4. Cost ($ per 1k tokens)
5. Success Rate (%)
Calculates dynamic composite score to rank providers for LLMRouter.
"""

import logging
import sqlite3
import time
import os
import json
from typing import Dict, Any, List, Optional

logger = logging.getLogger("MODEL_EVALUATOR_PIPELINE")

class ModelEvaluatorPipeline:
    def __init__(self, db_path: Optional[str] = None):
        if db_path is None:
            db_path = os.path.join(os.path.dirname(__file__), "..", "cognitive_memory.db")
        self.db_path = db_path
        self._init_db()

    def _get_connection(self):
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        """Initializes model evaluation metrics scorecard table."""
        try:
            os.makedirs(os.path.dirname(self.db_path), exist_ok=True)
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("""
                    CREATE TABLE IF NOT EXISTS model_eval_scorecard (
                        provider_id TEXT PRIMARY KEY,
                        provider_name TEXT NOT NULL,
                        latency_ms REAL NOT NULL,
                        accuracy_pct REAL NOT NULL,
                        hallucination_pct REAL NOT NULL,
                        cost_usd_per_1k REAL NOT NULL,
                        success_rate_pct REAL NOT NULL,
                        composite_score REAL NOT NULL,
                        total_invocations INTEGER DEFAULT 1,
                        updated_at TEXT NOT NULL
                    )
                """)
                conn.commit()
                logger.info(f"[MODEL EVALUATOR] Scorecard schema initialized successfully at {self.db_path}")
        except Exception as e:
            logger.error(f"[MODEL EVALUATOR] Failed to initialize evaluation table: {e}")

    def record_model_call(self, provider_id: str, latency_ms: float, is_accurate: bool, is_hallucinated: bool, cost_usd: float, is_success: bool) -> float:
        """
        Records a model invocation metric, updates running averages, and re-calculates composite score.
        """
        now = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM model_eval_scorecard WHERE provider_id = ?", (provider_id,))
                row = cursor.fetchone()

                if row:
                    count = row["total_invocations"] + 1
                    # Moving average calculation
                    avg_latency = (row["latency_ms"] * row["total_invocations"] + latency_ms) / count
                    avg_accuracy = (row["accuracy_pct"] * row["total_invocations"] + (100.0 if is_accurate else 0.0)) / count
                    avg_hallucination = (row["hallucination_pct"] * row["total_invocations"] + (100.0 if is_hallucinated else 0.0)) / count
                    avg_cost = (row["cost_usd_per_1k"] * row["total_invocations"] + cost_usd) / count
                    avg_success = (row["success_rate_pct"] * row["total_invocations"] + (100.0 if is_success else 0.0)) / count
                else:
                    count = 1
                    avg_latency = latency_ms
                    avg_accuracy = 100.0 if is_accurate else 0.0
                    avg_hallucination = 100.0 if is_hallucinated else 0.0
                    avg_cost = cost_usd
                    avg_success = 100.0 if is_success else 0.0

                # Formula Composite Score:
                # Score = (Accuracy * 0.35) + (Success * 0.35) + ((100 - Hallucination) * 0.15) + (max(0, 100 - Latency/10) * 0.10) + (max(0, 100 - Cost*1000) * 0.05)
                norm_latency_score = max(0.0, 100.0 - (avg_latency / 10.0))
                norm_cost_score = max(0.0, 100.0 - (avg_cost * 1000.0))
                
                composite_score = round(
                    (avg_accuracy * 0.35) +
                    (avg_success * 0.35) +
                    ((100.0 - avg_hallucination) * 0.15) +
                    (norm_latency_score * 0.10) +
                    (norm_cost_score * 0.05),
                    2
                )

                cursor.execute("""
                    INSERT INTO model_eval_scorecard (provider_id, provider_name, latency_ms, accuracy_pct, hallucination_pct, cost_usd_per_1k, success_rate_pct, composite_score, total_invocations, updated_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ON CONFLICT(provider_id) DO UPDATE SET
                        latency_ms = excluded.latency_ms,
                        accuracy_pct = excluded.accuracy_pct,
                        hallucination_pct = excluded.hallucination_pct,
                        cost_usd_per_1k = excluded.cost_usd_per_1k,
                        success_rate_pct = excluded.success_rate_pct,
                        composite_score = excluded.composite_score,
                        total_invocations = excluded.total_invocations,
                        updated_at = excluded.updated_at
                """, (provider_id, provider_id.upper(), avg_latency, avg_accuracy, avg_hallucination, avg_cost, avg_success, composite_score, count, now))

                conn.commit()
                logger.info(f"[MODEL EVALUATOR] Updated provider {provider_id}: Composite Score = {composite_score}")
                return composite_score
        except Exception as e:
            logger.error(f"[MODEL EVALUATOR] Error recording model call: {e}")
            return 50.0

    def get_best_provider(self) -> Dict[str, Any]:
        """Returns the model provider with the highest Composite Score."""
        try:
            with self._get_connection() as conn:
                cursor = conn.cursor()
                cursor.execute("SELECT * FROM model_eval_scorecard ORDER BY composite_score DESC LIMIT 1")
                row = cursor.fetchone()
                if row:
                    return dict(row)
        except Exception as e:
            logger.error(f"[MODEL EVALUATOR] Error fetching best provider: {e}")

        # Fallback default
        return {
            "provider_id": "offline-rule-engine",
            "provider_name": "RandomForestClassifier_rules.pkl",
            "composite_score": 88.5,
            "latency_ms": 12.0,
            "accuracy_pct": 94.0,
            "hallucination_pct": 0.0,
            "cost_usd_per_1k": 0.0,
            "success_rate_pct": 98.0
        }


# Demo test run
if __name__ == "__main__":
    evaluator = ModelEvaluatorPipeline()
    print("=== UJI DYNAMIC MODEL EVALUATION PIPELINE (SCORECARD ENGINE) ===")

    evaluator.record_model_call("gemini-2.0-flash", latency_ms=180.0, is_accurate=True, is_hallucinated=False, cost_usd=0.0001, is_success=True)
    evaluator.record_model_call("groq-llama3", latency_ms=90.0, is_accurate=True, is_hallucinated=False, cost_usd=0.0002, is_success=True)
    evaluator.record_model_call("offline-rule-engine", latency_ms=8.0, is_accurate=True, is_hallucinated=False, cost_usd=0.0, is_success=True)

    best = evaluator.get_best_provider()
    print(f"\n🏆 Best Ranked Provider: {best['provider_name']} (Composite Score: {best['composite_score']})")
    print(f"   Latency: {best['latency_ms']:.1f}ms | Accuracy: {best['accuracy_pct']}% | Cost: ${best['cost_usd_per_1k']}/1k")
