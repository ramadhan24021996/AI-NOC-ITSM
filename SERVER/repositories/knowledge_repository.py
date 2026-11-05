"""
SERVER.repositories - Knowledge Repository
Interface for knowledge entity data access operations.
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from SERVER.repositories.base_repository import BaseRepository
from SERVER.shared.models import KnowledgeChunkDTO

class KnowledgeEntityRepository(BaseRepository[KnowledgeChunkDTO], ABC):
    """Abstract Knowledge Entity Repository interface."""
    @abstractmethod
    def search_by_tag(self, tag: str, limit: int = 20) -> List[KnowledgeChunkDTO]:
        pass
