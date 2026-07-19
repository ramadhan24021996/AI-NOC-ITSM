"""
Enterprise Autonomous AI OS — Phase 6: Step 6.1
Meta-Cognition Layer

AI mengevaluasi efisiensi cara berpikirnya sendiri setelah setiap insiden.
Pertanyaan yang dijawab Meta-Cognition:
  - Apakah reasoning saya efisien? (token usage vs outcome)
  - Apakah saya memilih tool yang tepat?
  - Apakah saya memiliki bias dalam rekomendasi?
  - Apakah planning cycle terlalu banyak iterasi?

Output disimpan ke meta_cognition_logs dan dapat mempengaruhi
threshold Decision Engine dan Policy Engine di iterasi berikutnya.
"""

import json
import logging
import os
from typing import Dict, Any, List, Optional

logger = logging.getLogger("META_COGNITION")


class MetaCognitionLayer:
    """
    Post-incident cognitive efficiency evaluator.
    Analyzes the AI's own reasoning process and suggests improvements.
    """

    # Thresholds for bias/inefficiency detection
    MAX_EFFICIENT_TOKENS = 2000
    MAX_PLANNING_CYCLES  = 3
    MIN_TOOL_ACCURACY    = 0.7
    HALLUCINATION_KEYWORDS = [
        "i cannot", "i don't know", "unclear", "unable to determine",
        "no information", "not enough data", "uncertain"
    ]

    def __init__(self, db_conn=None):
        self._conn = db_conn

    def evaluate(
        self,
        incident_id: Optional[int],
        worker_name: str,
        reasoning_trace: Dict,
        planning_trace: Dict,
        policy_trace: Dict,
        llm_response: str = "",
        token_used: int = 0,
        planning_cycles: int = 1,
        action_success: bool = True,
    ) -> Dict[str, Any]:
        """
        Evaluate AI cognitive efficiency for a completed task.
        Returns evaluation report with recommendations.
        """
        report = {
            "incident_id":     incident_id,
            "worker":          worker_name,
            "token_used":      token_used,
            "planning_cycles": planning_cycles,
            "bias_detected":   False,
            "bias_type":       None,
            "efficiency_score": 1.0,
            "reasoning_depth": len(reasoning_trace.get("stages", [])),
            "tool_accuracy":   1.0,
            "recommendations": [],
        }

        # 1. Token efficiency
        if token_used > self.MAX_EFFICIENT_TOKENS:
            penalty = (token_used - self.MAX_EFFICIENT_TOKENS) / self.MAX_EFFICIENT_TOKENS * 0.3
            report["efficiency_score"] = max(0.0, report["efficiency_score"] - penalty)
            report["recommendations"].append(
                f"Token usage {token_used} exceeds efficient threshold {self.MAX_EFFICIENT_TOKENS}. "
                "Consider shorter prompts or prompt caching."
            )

        # 2. Planning cycle depth
        if planning_cycles > self.MAX_PLANNING_CYCLES:
            report["efficiency_score"] -= 0.1
            report["recommendations"].append(
                f"Planning took {planning_cycles} cycles (max recommended: {self.MAX_PLANNING_CYCLES}). "
                "Consider pre-caching common plans."
            )

        # 3. Hallucination detection in LLM response
        if llm_response:
            resp_lower = llm_response.lower()
            hallucination_hits = [kw for kw in self.HALLUCINATION_KEYWORDS if kw in resp_lower]
            if hallucination_hits:
                report["bias_detected"] = True
                report["bias_type"]     = "HALLUCINATION"
                report["efficiency_score"] -= 0.2
                report["recommendations"].append(
                    f"Potential hallucination detected. Keywords: {hallucination_hits}. "
                    "Consider enriching knowledge base on this topic."
                )

        # 4. Tool accuracy (inferred from success)
        if not action_success:
            report["tool_accuracy"]    = 0.4
            report["efficiency_score"] -= 0.2
            report["recommendations"].append(
                "Action did not succeed. Verify tool selection logic and knowledge freshness."
            )

        # 5. Clamp score
        report["efficiency_score"] = round(max(0.0, min(1.0, report["efficiency_score"])), 3)

        # Persist to DB
        self._persist(report)
        logger.info(
            "[META_COGNITION] Incident=%s worker=%s efficiency=%.3f bias=%s",
            incident_id, worker_name, report["efficiency_score"], report["bias_type"]
        )
        return report

    def _persist(self, report: Dict):
        """Save meta-cognition evaluation to meta_cognition_logs."""
        if not self._conn:
            return
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO meta_cognition_logs
                        (incident_id, worker_name, reasoning_depth, token_used,
                         tool_accuracy, planning_cycles, bias_detected, bias_type,
                         efficiency_score, recommendations, evaluated_at)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
                """, (
                    report["incident_id"],
                    report["worker"],
                    report["reasoning_depth"],
                    report["token_used"],
                    report["tool_accuracy"],
                    report["planning_cycles"],
                    report["bias_detected"],
                    report["bias_type"],
                    report["efficiency_score"],
                    json.dumps(report["recommendations"]),
                ))
            self._conn.commit()
        except Exception as e:
            logger.warning("[META_COGNITION] Failed to persist: %s", e)
            try:
                self._conn.rollback()
            except Exception:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')

    def get_recent_metrics(self, limit: int = 10) -> List[Dict]:
        """Return recent meta-cognition evaluations for the AI Health Monitor."""
        if not self._conn:
            return list()
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    SELECT worker_name, efficiency_score, bias_detected,
                           bias_type, token_used, planning_cycles, evaluated_at
                    FROM meta_cognition_logs
                    ORDER BY evaluated_at DESC
                    LIMIT %s
                """, (limit,))
                rows = cur.fetchall()
                return [
                    {
                        "worker": r[0], "efficiency": float(r[1] or 0),
                        "bias": r[2], "bias_type": r[3],
                        "tokens": r[4], "cycles": r[5], "at": str(r[6])
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error("[META_COGNITION] Failed to fetch metrics: %s", e)
            return list()

    def get_hallucination_rate(self, last_n_days: int = 7) -> float:
        """Return hallucination detection rate over the last N days."""
        if not self._conn:
            return 0.0
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    SELECT
                        COUNT(*) FILTER (WHERE bias_detected = TRUE) * 100.0 / NULLIF(COUNT(*), 0)
                    FROM meta_cognition_logs
                    WHERE evaluated_at > NOW() - INTERVAL '%s days'
                """, (last_n_days,))
                rate = cur.fetchone()[0]
                return round(float(rate or 0), 2)
        except Exception as e:
            logger.error("[META_COGNITION] Hallucination rate error: %s", e)
            return 0.0
