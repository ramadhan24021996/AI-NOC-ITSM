"""
Knowledge Fabric Interfaces for Enterprise AI Operations Platform
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from SERVER.shared.models import KnowledgeChunkDTO, EvidenceScoreDTO

class KnowledgeProvider(ABC):
    """Abstract interface for external/internal knowledge providers."""
    @abstractmethod
    def fetch_knowledge(self, query: str, top_k: int = 5) -> List[KnowledgeChunkDTO]:
        pass

class KnowledgeRepository(ABC):
    """Abstract interface for knowledge persistence operations."""
    @abstractmethod
    def save_chunk(self, chunk: KnowledgeChunkDTO) -> str:
        pass

    @abstractmethod
    def get_chunk_by_id(self, chunk_id: str) -> Optional[KnowledgeChunkDTO]:
        pass

class KnowledgeRetriever(ABC):
    """Abstract interface for multi-metric retrieval."""
    @abstractmethod
    def retrieve(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[KnowledgeChunkDTO]:
        pass

class KnowledgeValidator(ABC):
    """Abstract interface for verifying knowledge accuracy & anti-poisoning."""
    @abstractmethod
    def validate(self, chunk: KnowledgeChunkDTO) -> EvidenceScoreDTO:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATIONS — Step 2
# ══════════════════════════════════════════════════════════════════════════════
import os
import json
import logging
import psycopg2
from SERVER.shared.db_pool import PGConnection, get_redis
from psycopg2.extras import RealDictCursor

_logger = logging.getLogger("knowledge.impl")

def _pgconn():
    return PGConnection()


# Step 2.1 — KnowledgeProvider
class PostgreSQLKnowledgeProvider(KnowledgeProvider):
    """Fetches knowledge using PostgreSQL full-text search (tsvector GIN index)."""

    def fetch_knowledge(self, query: str, top_k: int = 5) -> List[KnowledgeChunkDTO]:
        try:
            with PGConnection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """SELECT chunk_id, title, content, source_url, trust_rating,
                                  similarity_score, coverage_score, metadata
                           FROM knowledge_chunks
                           WHERE to_tsvector('english', content || ' ' || title) @@ plainto_tsquery('english', %s)
                           ORDER BY similarity_score DESC LIMIT %s""",
                        (query, top_k)
                    )
                    rows = cur.fetchall()
                    return [KnowledgeChunkDTO(
                        chunk_id=str(r["chunk_id"]), title=str(r["title"]),
                        content=str(r["content"]), source_url=str(r["source_url"]),
                        trust_rating=r.get("trust_rating", "MEDIUM"),
                        similarity_score=float(r.get("similarity_score", 0.0)),
                        coverage_score=float(r.get("coverage_score", 0.0)),
                        metadata=r.get("metadata") or {},
                    ) for r in rows]
        except Exception as e:
            _logger.error("[KnowledgeProvider] fetch_knowledge failed: %s", e, exc_info=True)
            return []


# Step 2.2 — KnowledgeRepository (save/get)
class PostgreSQLKnowledgeRepository(KnowledgeRepository):
    """Persists and retrieves KnowledgeChunkDTO from knowledge_chunks table."""

    def save_chunk(self, chunk: KnowledgeChunkDTO) -> str:
        try:
            with PGConnection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO knowledge_chunks
                           (chunk_id, title, content, source_url, trust_rating, similarity_score, coverage_score, metadata)
                           VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                           ON CONFLICT (chunk_id) DO UPDATE SET
                           content=EXCLUDED.content, similarity_score=EXCLUDED.similarity_score""",
                        (chunk.chunk_id, chunk.title, chunk.content, chunk.source_url,
                         str(chunk.trust_rating), chunk.similarity_score, chunk.coverage_score,
                         json.dumps(chunk.metadata))
                    )
                    conn.commit()
            return chunk.chunk_id
        except Exception as e:
            _logger.error("[KnowledgeRepo] save_chunk failed: %s", e, exc_info=True)
            return ""

    def get_chunk_by_id(self, chunk_id: str) -> Optional[KnowledgeChunkDTO]:
        try:
            with PGConnection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute("SELECT * FROM knowledge_chunks WHERE chunk_id = %s", (chunk_id,))
                    r = cur.fetchone()
                    if not r:
                        return None
                    return KnowledgeChunkDTO(
                        chunk_id=str(r["chunk_id"]), title=str(r["title"]),
                        content=str(r["content"]), source_url=str(r["source_url"]),
                        trust_rating=r.get("trust_rating", "MEDIUM"),
                        similarity_score=float(r.get("similarity_score", 0.0)),
                        coverage_score=float(r.get("coverage_score", 0.0)),
                        metadata=r.get("metadata") or {},
                    )
        except Exception as e:
            _logger.error("[KnowledgeRepo] get_chunk_by_id(%s) failed: %s", chunk_id, e, exc_info=True)
            return None


# Step 2.3 — KnowledgeRetriever
class PostgreSQLKnowledgeRetriever(KnowledgeRetriever):
    """Multi-metric retrieval: fulltext + filters (site, trust, date range)."""

    def retrieve(self, query: str, filters: Optional[Dict[str, Any]] = None) -> List[KnowledgeChunkDTO]:
        filters = filters or {}
        clauses = ["(to_tsvector('english', content || ' ' || title) @@ plainto_tsquery('english', %s))"]
        params: List[Any] = [query]

        if "trust_rating" in filters:
            clauses.append("trust_rating = %s")
            params.append(filters["trust_rating"])
        if "min_score" in filters:
            clauses.append("similarity_score >= %s")
            params.append(float(filters["min_score"]))

        where = " AND ".join(clauses)
        limit = int(filters.get("top_k", 10))
        params.append(limit)

        try:
            with PGConnection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        f"SELECT * FROM knowledge_chunks WHERE {where} ORDER BY similarity_score DESC LIMIT %s",
                        params
                    )
                    return [KnowledgeChunkDTO(
                        chunk_id=str(r["chunk_id"]), title=str(r["title"]),
                        content=str(r["content"]), source_url=str(r["source_url"]),
                        trust_rating=r.get("trust_rating", "MEDIUM"),
                        similarity_score=float(r.get("similarity_score", 0.0)),
                        coverage_score=float(r.get("coverage_score", 0.0)),
                        metadata=r.get("metadata") or {},
                    ) for r in cur.fetchall()]
        except Exception as e:
            _logger.error("[KnowledgeRetriever] retrieve failed: %s", e, exc_info=True)
            return []


# Step 2.4 — KnowledgeValidator
class RuleBasedKnowledgeValidator(KnowledgeValidator):
    """
    Validates chunk quality using composite evidence scoring.
    Scores: similarity (0.3) + coverage (0.25) + freshness (0.2) + trust (0.15) + consensus (0.1)
    """
    TRUST_WEIGHT = {"HIGH": 1.0, "MEDIUM": 0.7, "LOW": 0.3, "UNKNOWN": 0.1}

    def validate(self, chunk: KnowledgeChunkDTO) -> "EvidenceScoreDTO":
        from SERVER.shared.models import EvidenceScoreDTO
        sim  = min(1.0, max(0.0, float(chunk.similarity_score or 0.0)))
        cov  = min(1.0, max(0.0, float(chunk.coverage_score or 0.0)))
        trust_key = str(getattr(chunk.trust_rating, 'value', chunk.trust_rating)).upper()
        trust = self.TRUST_WEIGHT.get(trust_key, 0.5)
        # Freshness: check metadata for 'date' field (normalized 0-1)
        freshness = float(chunk.metadata.get("freshness_score", 0.7))
        consensus = float(chunk.metadata.get("consensus_score", 0.6))
        composite = round(sim*0.30 + cov*0.25 + freshness*0.20 + trust*0.15 + consensus*0.10, 4)
        return EvidenceScoreDTO(
            similarity=sim, coverage=cov, freshness=freshness,
            source_trust=trust, consensus=consensus, composite_score=composite
        )
