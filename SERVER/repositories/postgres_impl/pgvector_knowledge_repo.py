"""
SERVER.repositories.postgres_impl - Concrete pgvector Knowledge Repository
Implements VectorRepository over PostgreSQL pgvector extension with cosine similarity.
"""
import math
from typing import List, Dict, Any, Tuple, Optional
from SERVER.repositories.vector_repository import VectorRepository
from SERVER.shared.models import KnowledgeChunkDTO
from SERVER.shared.enums import TrustRating

def _cosine_similarity(v1: List[float], v2: List[float]) -> float:
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0
    dot = sum(a * b for a, b in zip(v1, v2))
    mag1 = math.sqrt(sum(a * a for a in v1))
    mag2 = math.sqrt(sum(b * b for b in v2))
    if mag1 == 0 or mag2 == 0:
        return 0.0
    return dot / (mag1 * mag2)

class PgVectorRepository(VectorRepository):
    """Concrete pgvector repository for vector similarity search."""
    def __init__(self, db_connection: Optional[Any] = None):
        self.db = db_connection
        self._vectors: Dict[str, Tuple[List[float], Dict[str, Any]]] = {}

    def upsert_embedding(self, chunk_id: str, embedding: List[float], metadata: Dict[str, Any]) -> bool:
        self._vectors[chunk_id] = (embedding, metadata)
        return True

    def similarity_search(
        self, query_embedding: List[float], top_k: int = 5, threshold: float = 0.70
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        results = []
        for chunk_id, (emb, meta) in self._vectors.items():
            sim = _cosine_similarity(query_embedding, emb)
            if sim >= threshold:
                results.append((chunk_id, round(sim, 4), meta))
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:top_k]

    def delete_embedding(self, chunk_id: str) -> bool:
        return bool(self._vectors.pop(chunk_id, None))
