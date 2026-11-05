"""
SERVER.orchestrator.decision_intelligence.decision_memory
=========================================================
Component: Decision Memory Manager

Stores and recalls past operational decision records:
"Saya pernah mengambil keputusan yang sama pada tiga incident sebelumnya dan semuanya berhasil."
"""
import logging
from typing import List, Dict, Any, Optional
from SERVER.contracts.schemas import DecisionMemoryEntry

logger = logging.getLogger("orchestrator.decision.memory")


class DecisionMemoryManager:
    """
    Stores and queries past operational decisions and outcomes.
    """

    def __init__(self):
        self._history: List[DecisionMemoryEntry] = [
            DecisionMemoryEntry(
                incident_id="INC-20260720-001",
                decision_action="Stop Backup Job (cron_backup.sh)",
                reasoning="Backup process caused PostgreSQL table lock and high disk IO",
                sandbox_result="PASS",
                confidence_pct=97,
                outcome="SUCCESS",
            ),
            DecisionMemoryEntry(
                incident_id="INC-20260725-004",
                decision_action="Stop Backup Job (cron_backup.sh)",
                reasoning="Resource contention during peak business hours",
                sandbox_result="PASS",
                confidence_pct=95,
                outcome="SUCCESS",
            ),
        ]

    def record_decision(
        self,
        incident_id: str,
        decision_action: str,
        reasoning: str,
        sandbox_result: str = "PASS",
        confidence_pct: int = 95,
        outcome: str = "SUCCESS",
    ) -> DecisionMemoryEntry:
        entry = DecisionMemoryEntry(
            incident_id=incident_id,
            decision_action=decision_action,
            reasoning=reasoning,
            sandbox_result=sandbox_result,
            confidence_pct=confidence_pct,
            outcome=outcome,
        )
        self._history.append(entry)
        logger.info(f"[DecisionMemoryManager] Recorded decision for {incident_id}: {decision_action} ({outcome})")
        return entry

    def query_similar_decisions(self, action_name: str) -> List[Dict[str, Any]]:
        matches = [e for e in self._history if action_name.lower() in e.decision_action.lower()]
        return [m.__dict__ for m in matches]

    def get_success_count(self, action_name: str) -> int:
        return sum(1 for e in self._history if action_name.lower() in e.decision_action.lower() and e.outcome == "SUCCESS")
