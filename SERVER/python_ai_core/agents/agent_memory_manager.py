"""
Enterprise Agent Memory Manager (Phase 3 Capability 3)
Manages 6 distinct memory dimensions:
1. Working Memory (Short-term active task context)
2. Conversation Memory (Multi-turn user/system dialogue)
3. Incident Memory (Active & historic incident states)
4. Operator Feedback Memory (RLHF Ground Truth corrections)
5. Historical Task Memory (Past agent action logs)
6. Reasoning Memory (Intermediate hypothesis & chain of thought)
"""

import logging
import time
from typing import Dict, List, Any, Optional

logger = logging.getLogger("AGENT_MEMORY_MANAGER")

class AgentMemoryManager:
    """
    Enterprise Agent Memory System
    Provides short-term working memory and long-term operational memory for AI agents.
    """

    def __init__(self):
        self.working_memory: Dict[str, Any] = {}
        self.conversation_memory: List[Dict[str, Any]] = []
        self.incident_memory: Dict[str, Dict[str, Any]] = {}
        self.operator_feedback_memory: List[Dict[str, Any]] = []
        self.historical_task_memory: List[Dict[str, Any]] = []
        self.reasoning_memory: List[Dict[str, Any]] = []

    def set_working_memory(self, key: str, value: Any):
        """Sets short-term working memory item."""
        self.working_memory[key] = value

    def get_working_memory(self, key: str) -> Optional[Any]:
        """Gets short-term working memory item."""
        return self.working_memory.get(key)

    def add_reasoning_step(self, agent_id: str, hypothesis: str, confidence: float):
        """Appends reasoning step to reasoning memory."""
        self.reasoning_memory.append({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "agent_id": agent_id,
            "hypothesis": hypothesis,
            "confidence": confidence
        })

    def store_operator_feedback(self, incident_id: str, feedback: str, approved: bool):
        """Stores operator ground truth feedback for RLHF learning."""
        self.operator_feedback_memory.append({
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "incident_id": incident_id,
            "feedback": feedback,
            "approved": approved
        })
