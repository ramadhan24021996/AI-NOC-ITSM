"""
SERVER.repositories - Audit Repository
Interface for immutable audit trail data access.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from SERVER.repositories.base_repository import BaseRepository

class AuditRepository(BaseRepository[Dict[str, Any]], ABC):
    """Abstract Audit Repository interface. Records are immutable after creation."""
    @abstractmethod
    def find_by_actor(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def find_by_action_type(self, action_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        pass

    def delete(self, entity_id: str) -> bool:
        """Audit records are immutable. Deletion is explicitly forbidden."""
        raise PermissionError("Audit records are immutable and cannot be deleted.")
