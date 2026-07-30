"""
Phase 3: Operator Feedback & Quality Score Tuner.

Aggregates operator "Benar / Salah" feedback from PostgreSQL database
and dynamically tunes validator thresholds and curriculum learning rules.
"""

import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger("OperatorFeedbackTuner")


@dataclass
class FeedbackSummary:
    total_feedback_count: int
    approvals_count: int
    rejections_count: int
    acceptance_rate_percent: float
    recommended_quality_threshold: float
    curriculum_updates: List[str]


class OperatorFeedbackTuner:
    """Tuner engine for learning from operator feedback."""

    def __init__(self, db_conn=None):
        self.db_conn = db_conn

    def fetch_and_tune(self, mock_feedback: Optional[List[Dict[str, Any]]] = None) -> FeedbackSummary:
        """Fetches feedback logs, calculates acceptance rate, and returns tuned parameters."""
        approvals = 0
        rejections = 0
        curriculum_lessons = []

        if mock_feedback:
            for fb in mock_feedback:
                if fb.get("flag") in ["HUMAN_APPROVAL", "APPROVED", "CORRECT"]:
                    approvals += 1
                else:
                    rejections += 1
                    if fb.get("failed_action"):
                        curriculum_lessons.append(f"Action '{fb.get('failed_action')}' rejected by operator.")
        elif self.db_conn:
            try:
                with self.db_conn.cursor() as cur:
                    cur.execute("""
                        SELECT flag, report_data->>'failed_action' 
                        FROM incident_post_mortems 
                        WHERE created_at >= NOW() - INTERVAL '7 days'
                    """)
                    rows = cur.fetchall()
                    for flag, failed_action in rows:
                        if flag in ["HUMAN_APPROVAL", "APPROVED", "CORRECT"]:
                            approvals += 1
                        else:
                            rejections += 1
                            if failed_action:
                                curriculum_lessons.append(f"Action '{failed_action}' rejected by operator.")
            except Exception as e:
                logger.error(f"[OperatorFeedbackTuner] DB Fetch failed: {e}")

        total = approvals + rejections
        acceptance_rate = round((approvals / max(1, total)) * 100.0, 2) if total > 0 else 85.0

        # Dynamic Quality Threshold Tuning:
        # High acceptance rate (>90%) -> lower threshold to 70.0 (less aggressive filtering)
        # Low acceptance rate (<75%) -> raise threshold to 80.0 (stricter filtering)
        if acceptance_rate >= 90.0:
            recommended_threshold = 70.0
        elif acceptance_rate < 75.0:
            recommended_threshold = 80.0
        else:
            recommended_threshold = 75.0

        logger.info(f"[OperatorFeedbackTuner] Acceptance Rate: {acceptance_rate}%, Recommended Threshold: {recommended_threshold}")

        return FeedbackSummary(
            total_feedback_count=total,
            approvals_count=approvals,
            rejections_count=rejections,
            acceptance_rate_percent=acceptance_rate,
            recommended_quality_threshold=recommended_threshold,
            curriculum_updates=curriculum_lessons
        )
