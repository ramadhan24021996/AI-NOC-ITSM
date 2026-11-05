"""
SERVER.repositories - Memory Repository
Interface for AI memory entity data access operations.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from SERVER.repositories.base_repository import BaseRepository

class MemoryEntityRepository(BaseRepository[Dict[str, Any]], ABC):
    """Abstract Memory Entity Repository interface."""
    @abstractmethod
    def fetch_session_memory(self, session_id: str, limit: int = 50) -> List[Dict[str, Any]]:
        pass
