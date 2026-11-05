"""
SERVER.orchestrator.closed_loop.human_learning_feedback
=========================================================
Component: Human Learning Feedback Engine

Captures operator rationale when selecting AI NOC options over Jarvis recommendations.
Generates a Learning Candidate Markdown file in SERVER/memory/staging/.
"""
import logging
from typing import Dict, Any, Optional
from SERVER.contracts.schemas import OperatorFeedbackLearningCandidate
from SERVER.memory.staging_manager import MemoryStagingManager

logger = logging.getLogger("orchestrator.closed_loop.feedback")


class HumanLearningFeedbackEngine:
    """
    Learns from operator choices when choosing AI NOC proposals over Jarvis recommendations.
    """

    def __init__(self, staging_manager: Optional[MemoryStagingManager] = None):
        self.staging_manager = staging_manager or MemoryStagingManager()

    def record_feedback_choice(
        self,
        session_id: str,
        chosen_option: str,
        operator_reason_category: str = "Corporate SOP",
    ) -> OperatorFeedbackLearningCandidate:
        user_q = f"Operator Feedback Selection on `{session_id}`: Chosen '{chosen_option}'."
        assistant_resp = f"Catatan Umpan Balik: Operator memilih '{chosen_option}' berdasarkan kategori alasan: '{operator_reason_category}'."

        cog_payload = {
            "analysis_result": {"intent": "operator_learning_feedback", "entities": [chosen_option]},
            "goal_payload": {"active_goal": "Feedback Learning Candidate"},
            "context_state": {"stage": "ClosedLoop"},
            "knowledge_gap": {"has_gap": True},
            "memory_candidate": {"is_candidate": True},
            "confidence_scorecard": {"overall_confidence": 0.98},
        }

        fn = self.staging_manager.create_staging_file(
            session_id=f"fb_{session_id}",
            user_query=user_q,
            assistant_response=assistant_resp,
            cognitive_payload=cog_payload,
            operator="Operator",
            persona="Senior System Engineer",
            source="operator",
        )

        candidate = OperatorFeedbackLearningCandidate(
            session_id=session_id,
            chosen_option=chosen_option,
            operator_reason_category=operator_reason_category,
            staging_file_created=fn,
        )

        logger.info(f"[HumanLearningFeedbackEngine] Recorded feedback choice for {session_id}: created staging file {fn}")
        return candidate
