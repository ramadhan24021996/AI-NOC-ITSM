"""
SERVER.orchestrator.cognitive.goal_manager
===========================================
Component: Goal Manager

Tracks and manages active conversation goals so that dialogue stays focused:
  - Operator: "Kenapa CPU tinggi?" -> Goal: Find RCA
  - Operator: "Restart nginx" -> Goal: Recovery Execution
  - Operator: "Apakah aman?" -> Goal: Risk Assessment
"""
import logging
from dataclasses import dataclass
from typing import Dict, Any

from SERVER.contracts.schemas import GoalPayload

logger = logging.getLogger("orchestrator.cognitive.goal_manager")


class GoalManager:
    """
    Manages active dialogue goals per session.
    """

    def __init__(self):
        self._goals: Dict[str, GoalPayload] = {}

    def get_or_create_goal(self, session_id: str) -> GoalPayload:
        if not session_id:
            session_id = "default_session"
        if session_id not in self._goals:
            self._goals[session_id] = GoalPayload(
                active_goal="Find RCA",
                previous_goal="",
                goal_status="IN_PROGRESS",
            )
        return self._goals[session_id]

    def update_goal(self, session_id: str, query_text: str, intent: str, stage: str) -> GoalPayload:
        payload = self.get_or_create_goal(session_id)
        query_lower = query_text.lower()

        new_goal = payload.active_goal

        if intent == "execute_action" or any(kw in query_lower for kw in ["restart", "reboot", "clear cache", "solusi"]):
            new_goal = "Recovery Execution"
        elif stage == "Risk Assessment" or any(kw in query_lower for kw in ["apakah aman", "resiko", "risk", "efek"]):
            new_goal = "Risk Assessment"
        elif intent == "learn_fact":
            new_goal = "Memory Registration"
        elif stage == "Diagnosis" or intent == "diagnose_incident":
            new_goal = "Find RCA"

        if new_goal != payload.active_goal:
            payload.previous_goal = payload.active_goal
            payload.active_goal = new_goal
            payload.goal_status = "TRANSITIONED"
            logger.info(f"[GoalManager] Goal transition | session={session_id} | from={payload.previous_goal} -> to={new_goal}")
        else:
            payload.goal_status = "IN_PROGRESS"

        return payload
