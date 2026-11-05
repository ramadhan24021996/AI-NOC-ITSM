"""
SERVER.orchestrator - Execution Planner
Abstract execution planner interface for mapping steps into execution sequences.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any

class ExecutionPlanner(ABC):
    """Abstract execution planner interface."""
    @abstractmethod
    def plan_steps(self, intent_type: str) -> List[str]:
        pass
