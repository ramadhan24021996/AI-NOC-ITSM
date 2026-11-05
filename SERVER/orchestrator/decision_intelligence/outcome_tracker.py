"""
SERVER.orchestrator.decision_intelligence.outcome_tracker
=========================================================
Component: Outcome Tracker

Monitors post-execution outcomes (SUCCESS, PARTIAL, FAILED) and feeds results
into Decision Memory and Failure Knowledge Tracker.
"""
import time
import logging
from typing import Dict, Any, Optional
from SERVER.contracts.schemas import OutcomeTrackingResult
from SERVER.orchestrator.decision_intelligence.decision_memory import DecisionMemoryManager
from SERVER.orchestrator.decision_intelligence.failure_knowledge import FailureKnowledgeTracker

logger = logging.getLogger("orchestrator.decision.outcome")


class OutcomeTracker:
    """
    Monitors execution outcome and updates memory/failure knowledge stores.
    """

    def __init__(
        self,
        decision_memory: Optional[DecisionMemoryManager] = None,
        failure_tracker: Optional[FailureKnowledgeTracker] = None,
    ):
        self.decision_memory = decision_memory or DecisionMemoryManager()
        self.failure_tracker = failure_tracker or FailureKnowledgeTracker()

    def record_outcome(
        self,
        incident_id: str,
        action_name: str,
        outcome: str,
        reason: str = "",
        confidence_pct: int = 95,
    ) -> OutcomeTrackingResult:
        now_str = time.strftime("%Y-%m-%d %H:%M:%S")

        if outcome.upper() == "SUCCESS":
            self.decision_memory.record_decision(
                incident_id=incident_id,
                decision_action=action_name,
                reasoning=reason or "Execution completed successfully",
                confidence_pct=confidence_pct,
                outcome="SUCCESS",
            )
        elif outcome.upper() == "FAILED":
            self.failure_tracker.record_failure(
                action_name=action_name,
                reason=reason or "Execution failed to resolve incident",
            )
            self.decision_memory.record_decision(
                incident_id=incident_id,
                decision_action=action_name,
                reasoning=reason,
                confidence_pct=confidence_pct,
                outcome="FAILED",
            )

        logger.info(f"[OutcomeTracker] Recorded outcome for {incident_id}: {action_name} -> {outcome}")
        return OutcomeTrackingResult(
            incident_id=incident_id,
            action_name=action_name,
            outcome=outcome.upper(),
            recorded_at=now_str,
        )
