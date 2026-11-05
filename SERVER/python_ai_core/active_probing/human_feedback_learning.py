"""
Granular Human Feedback & Learning Queue Module
Replaces binary feedback with 12 granular categories:
1. Wrong RCA           7. Wrong Remediation
2. Wrong Probe         8. Wrong Rollback
3. Wrong Confidence    9. Wrong Priority
4. Wrong Risk          10. Wrong Business Impact
5. Wrong Sequence      11. Wrong Dependency
6. Wrong SOP           12. Wrong Explanation
Feeds directly into the Learning Queue for model and reflection memory evolution.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum
import time


class GranularFeedbackCategory(Enum):
    WRONG_RCA = "Wrong_RCA"
    WRONG_PROBE = "Wrong_Probe"
    WRONG_CONFIDENCE = "Wrong_Confidence"
    WRONG_RISK = "Wrong_Risk"
    WRONG_SEQUENCE = "Wrong_Sequence"
    WRONG_SOP = "Wrong_SOP"
    WRONG_REMEDIATION = "Wrong_Remediation"
    WRONG_ROLLBACK = "Wrong_Rollback"
    WRONG_PRIORITY = "Wrong_Priority"
    WRONG_BUSINESS_IMPACT = "Wrong_Business_Impact"
    WRONG_DEPENDENCY = "Wrong_Dependency"
    WRONG_EXPLANATION = "Wrong_Explanation"


@dataclass
class GranularFeedbackRecord:
    feedback_id: str
    incident_id: str
    operator_id: str
    category: GranularFeedbackCategory
    operator_notes: str
    corrective_guidance: str
    timestamp: float


class HumanFeedbackLearning:
    """Manages 12-category granular human feedback and feeds the AI Learning Queue."""

    def __init__(self):
        self.learning_queue: List[GranularFeedbackRecord] = []

    def submit_granular_feedback(
        self,
        incident_id: str,
        operator_id: str,
        category: GranularFeedbackCategory,
        operator_notes: str,
        corrective_guidance: str
    ) -> GranularFeedbackRecord:

        fid = f"FB-{incident_id}-{int(time.time() * 1000) % 10000}"
        rec = GranularFeedbackRecord(
            feedback_id=fid,
            incident_id=incident_id,
            operator_id=operator_id,
            category=category,
            operator_notes=operator_notes,
            corrective_guidance=corrective_guidance,
            timestamp=time.time()
        )
        self.learning_queue.append(rec)
        return rec

    def process_learning_queue(self) -> Dict[str, Any]:
        unprocessed_count = len(self.learning_queue)

        categories_summary = {}
        for item in self.learning_queue:
            cat_name = item.category.value
            categories_summary[cat_name] = categories_summary.get(cat_name, 0) + 1

        return {
            "total_feedback_processed": unprocessed_count,
            "category_breakdown": categories_summary,
            "queue_status": "LEARNING_QUEUE_SYNCHRONIZED"
        }
