"""
SERVER.orchestrator.governance.human_override_learning
======================================================
Component: Human Override Learning Engine

Captures operator overrides when human operator chooses Option #3 instead of Option #1.
Automatically generates a LearningCandidate Markdown file in SERVER/memory/staging/.
"""
import time
import logging
from typing import Dict, Any, Optional
from SERVER.contracts.schemas import HumanOverrideLearningEntry
from SERVER.memory.staging_manager import MemoryStagingManager

logger = logging.getLogger("orchestrator.governance.override")


class HumanOverrideLearningEngine:
    """
    Learns from human operator overrides.
    """

    def __init__(self, staging_manager: Optional[MemoryStagingManager] = None):
        self.staging_manager = staging_manager or MemoryStagingManager()

    def record_override(
        self,
        incident_id: str,
        chosen_option: str,
        default_ai_option: str,
        override_reason: str = "Operator preference based on site context",
    ) -> HumanOverrideLearningEntry:
        # Create staging learning candidate
        user_q = f"Human Override on Incident `{incident_id}`: Chosen '{chosen_option}' over AI default '{default_ai_option}'."
        assistant_resp = f"Catatan Pembelajaran: Operator memilih '{chosen_option}' dengan alasan: {override_reason}."

        cog_payload = {
            "analysis_result": {"intent": "human_override_learning", "entities": [chosen_option]},
            "goal_payload": {"active_goal": "SOP Learning Update"},
            "context_state": {"stage": "Governance"},
            "knowledge_gap": {"has_gap": True},
            "memory_candidate": {"is_candidate": True},
            "confidence_scorecard": {"overall_confidence": 0.99},
        }

        fn = self.staging_manager.create_staging_file(
            session_id=f"override_{incident_id}",
            user_query=user_q,
            assistant_response=assistant_resp,
            cognitive_payload=cog_payload,
            operator="Operator",
            persona="Senior System Engineer",
            source="operator",
        )

        entry = HumanOverrideLearningEntry(
            incident_id=incident_id,
            chosen_option=chosen_option,
            default_ai_option=default_ai_option,
            override_reason=override_reason,
            staging_file_created=fn,
        )

        logger.info(f"[HumanOverrideLearningEngine] Recorded override for {incident_id}: created staging file {fn}")
        return entry
