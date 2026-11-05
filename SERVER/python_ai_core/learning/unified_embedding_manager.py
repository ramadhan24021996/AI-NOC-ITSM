"""
Enterprise Unified Embedding Manager
Manages Sentence Embeddings, Graph Embeddings, Hybrid Embedding Fusion, and Embedding Cache.
"""

import logging
from typing import Dict, List, Any, Optional
from learning.graph_embedding import GraphEmbeddingEngine

logger = logging.getLogger("UNIFIED_EMBEDDING_MANAGER")

class UnifiedEmbeddingManager:
    """
    Enterprise Unified Embedding Manager
    Fuses textual sentence embeddings and structural graph embeddings into hybrid vectors.
    """

    def __init__(self, embedding_dim: int = 128):
        self.dim = embedding_dim
        self.graph_embedder = GraphEmbeddingEngine(dimensions=embedding_dim)
        self.cache: Dict[str, List[float]] = {}

    def get_hybrid_embedding(self, graph, node_id: str, text: str) -> List[float]:
        """Calculates fused hybrid embedding (50% Graph Structural + 50% Sentence Token Hash)."""
        cache_key = f"{node_id}:{text[:30]}"
        if cache_key in self.cache:
            return self.cache[cache_key]

        graph_vec = self.graph_embedder.generate_node_embedding(graph, node_id)
        text_vec = self.graph_embedder._local_hash_vector(text) if hasattr(self.graph_embedder, "_local_hash_vector") else graph_vec

        fused = [round((g + t) / 2.0, 6) for g, t in zip(graph_vec, text_vec)]
        self.cache[cache_key] = fused
        return fused
