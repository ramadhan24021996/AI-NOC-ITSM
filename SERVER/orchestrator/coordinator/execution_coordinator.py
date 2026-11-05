"""
SERVER.orchestrator - Execution Coordinator
Coordinates execution sequence without containing diagnosis logic.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, List, Optional
from SERVER.contracts.schemas import IncidentQueryContract, IncidentResponseContract

class ExecutionCoordinator(ABC):
    """Abstract coordinator interface for managing workflow execution sequence."""
    @abstractmethod
    def coordinate_execution(self, query_contract: IncidentQueryContract) -> IncidentResponseContract:
        pass
