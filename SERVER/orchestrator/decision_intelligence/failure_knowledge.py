"""
SERVER.orchestrator.decision_intelligence.failure_knowledge
===========================================================
Component: Failure Knowledge Tracker

Records failed recovery attempts and issues warning alerts for ineffective actions:
"Saya tidak menyarankan restart PostgreSQL karena pada 2 incident sebelumnya tindakan tersebut tidak menyelesaikan masalah."
"""
import logging
from typing import List, Dict, Any
from SERVER.contracts.schemas import FailureKnowledgeEntry

logger = logging.getLogger("orchestrator.decision.failure")


class FailureKnowledgeTracker:
    """
    Tracks failed recovery attempts and provides failure warnings.
    """

    def __init__(self):
        self._failure_records: List[FailureKnowledgeEntry] = [
            FailureKnowledgeEntry(
                action_name="Restart PostgreSQL Service Container",
                result="FAILED",
                reason="Table lock remained active after container restart",
                confidence_impact_pct=-32,
            )
        ]

    def record_failure(
        self, action_name: str, reason: str, confidence_impact_pct: int = -30
    ) -> FailureKnowledgeEntry:
        entry = FailureKnowledgeEntry(
            action_name=action_name,
            result="FAILED",
            reason=reason,
            confidence_impact_pct=confidence_impact_pct,
        )
        self._failure_records.append(entry)
        logger.warning(f"[FailureKnowledgeTracker] Recorded failure for {action_name}: {reason}")
        return entry

    def check_failure_warnings(self, candidate_actions: List[str]) -> List[Dict[str, Any]]:
        warnings = []
        for act in candidate_actions:
            matching = [f for f in self._failure_records if act.lower() in f.action_name.lower()]
            if matching:
                count = len(matching)
                warnings.append({
                    "action_name": act,
                    "warning_message": f"Tindakan '{act}' tidak disarankan karena pada {count} insiden sebelumnya gagal menyelesaikan masalah.",
                    "failure_count": count,
                    "last_reason": matching[-1].reason,
                })
        return warnings
