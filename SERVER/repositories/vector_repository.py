"""
SERVER.repositories - Vector Repository
Interface for vector embedding storage operations (pgvector / ChromaDB / Pinecone).
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Tuple, Optional
from SERVER.repositories.base_repository import BaseRepository
from SERVER.shared.models import KnowledgeChunkDTO

class VectorRepository(ABC):
    """Abstract vector store repository. Not inheriting BaseRepository because
    vector queries are embedding-based, not CRUD-based."""

    @abstractmethod
    def upsert_embedding(self, chunk_id: str, embedding: List[float], metadata: Dict[str, Any]) -> bool:
        pass

    @abstractmethod
    def similarity_search(
        self, query_embedding: List[float], top_k: int = 5, threshold: float = 0.70
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """Returns list of (chunk_id, similarity_score, metadata) tuples."""
        pass

    @abstractmethod
    def delete_embedding(self, chunk_id: str) -> bool:
        pass
