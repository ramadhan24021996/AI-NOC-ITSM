"""
SERVER.repositories - Incident Repository
Interface for incident entity data access operations.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from SERVER.repositories.base_repository import BaseRepository

class IncidentRepository(BaseRepository[Dict[str, Any]], ABC):
    """Abstract Incident Repository interface."""
    @abstractmethod
    def find_by_site(self, site_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def find_by_severity(self, severity_level: str, limit: int = 50) -> List[Dict[str, Any]]:
        pass
