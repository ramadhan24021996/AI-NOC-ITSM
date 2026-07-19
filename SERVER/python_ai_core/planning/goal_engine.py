"""
Enterprise Autonomous AI OS — Phase 4: Step 4.1
Goal Engine

Memberikan AI tujuan operasional yang terukur dan memastikan semua
keputusan dikalibrasi terhadap tujuan bisnis yang aktif.

Tujuan dibaca dari tabel ai_goals dan digunakan oleh Decision Engine
untuk memvalidasi apakah sebuah aksi selaras dengan target organisasi.
"""

import logging
import os
from typing import Dict, List, Optional

logger = logging.getLogger("GOAL_ENGINE")

# Goal metric evaluators
METRIC_DIRECTION = {
    "uptime_pct":         "maximize",  # higher is better
    "mttr_minutes":       "minimize",  # lower is better
    "coverage_pct":       "maximize",
    "false_positive_rate":"minimize",
}


class GoalEngine:
    """
    Reads active goals from ai_goals table.
    Evaluates action alignment and records metric progress.
    """

    def __init__(self, db_conn=None):
        self._conn = db_conn

    def get_active_goals(self) -> List[Dict]:
        """Return all active goals ordered by priority."""
        if not self._conn:
            return self._default_goals()
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    SELECT id, goal_name, target_metric, target_value,
                           current_value, priority
                    FROM ai_goals
                    WHERE is_active = TRUE
                    ORDER BY priority ASC
                """)
                rows = cur.fetchall()
                return [
                    {
                        "id": r[0], "name": r[1], "metric": r[2],
                        "target": r[3], "current": r[4], "priority": r[5],
                        "gap": self._compute_gap(r[2], r[3], r[4])
                    }
                    for r in rows
                ]
        except Exception as e:
            logger.error("[GOAL_ENGINE] Failed to fetch goals: %s", e)
            return self._default_goals()

    def evaluate_alignment(self, action: str, confidence: float, risk: str) -> float:
        """
        Score how well a proposed action aligns with current goals.
        Returns 0.0 (misaligned) to 1.0 (perfectly aligned).
        """
        goals = self.get_active_goals()
        if not goals:
            return 0.5  # neutral

        score = 0.5
        action_lower = action.lower()

        # Reward availability-related actions
        if any(kw in action_lower for kw in ("restart", "recover", "restore", "rollback")):
            score += 0.2

        # Penalize low confidence (hurts MTTR goal)
        if confidence < 50.0:
            score -= 0.2

        # Penalize HIGH risk actions (hurts availability goal)
        if risk.upper() in ("HIGH", "CRITICAL"):
            score -= 0.1

        return max(0.0, min(1.0, score))

    def record_goal_progress(self, metric: str, value: float) -> bool:
        """Update current measurement for a tracked metric."""
        if not self._conn:
            return False
        try:
            with self._conn.cursor() as cur:
                cur.execute("""
                    UPDATE ai_goals
                    SET current_value = %s, updated_at = NOW()
                    WHERE target_metric = %s AND is_active = TRUE
                """, (value, metric))
            self._conn.commit()
            logger.info("[GOAL_ENGINE] Updated metric=%s value=%.3f", metric, value)
            return True
        except Exception as e:
            logger.error("[GOAL_ENGINE] Failed to record progress: %s", e)
            try:
                self._conn.rollback()
            except Exception:
                import logging; logging.getLogger(__name__).debug('_ = None suppressed')
            return False

    def get_top_priority_goal(self) -> Optional[Dict]:
        """Return the single highest-priority active goal."""
        goals = self.get_active_goals()
        return goals[0] if goals else None

    def _compute_gap(self, metric: str, target: float, current: float) -> float:
        """Compute normalized gap (positive = improvement needed)."""
        if target is None or current is None:
            return 0.0
        direction = METRIC_DIRECTION.get(metric, "maximize")
        if direction == "maximize":
            return max(0.0, target - current)
        else:
            return max(0.0, current - target)

    def _default_goals(self) -> List[Dict]:
        """Fallback in-memory goals when DB unavailable."""
        return [
            {"id": 1, "name": "High Availability",  "metric": "uptime_pct",         "target": 99.9,  "current": 0, "priority": 1, "gap": 99.9},
            {"id": 2, "name": "MTTR Reduction",     "metric": "mttr_minutes",        "target": 30.0,  "current": 0, "priority": 2, "gap": 30.0},
            {"id": 3, "name": "Knowledge Coverage", "metric": "coverage_pct",        "target": 90.0,  "current": 0, "priority": 3, "gap": 90.0},
            {"id": 4, "name": "Low False Positive", "metric": "false_positive_rate", "target": 0.05,  "current": 0, "priority": 4, "gap": 0.05},
        ]
