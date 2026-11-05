"""
SERVER.repositories.impl - Concrete Repository Implementations
PostgreSQL-backed implementations for all abstract repository interfaces.
Stack: psycopg2 + RealDictCursor | pgvector SQL extension for vector search
"""
import os
import json
import logging
import uuid
from typing import List, Dict, Any, Tuple, Optional

import psycopg2
from SERVER.shared.db_pool import PGConnection, get_redis
from psycopg2.extras import RealDictCursor

from SERVER.repositories.base_repository import PostgreSQLBaseRepository
from SERVER.repositories.incident_repository import IncidentRepository
from SERVER.repositories.audit_repository import AuditRepository
from SERVER.repositories.knowledge_repository import KnowledgeEntityRepository
from SERVER.repositories.vector_repository import VectorRepository
from SERVER.shared.models import KnowledgeChunkDTO
from SERVER.shared.enums import TrustRating

logger = logging.getLogger(__name__)


def _build_conn_params() -> dict:
    return {
        "host":     os.getenv("DB_HOST", "127.0.0.1"),
        "port":     int(os.getenv("DB_PORT", 5432)),
        "dbname":   os.getenv("DB_NAME", "osi_system"),
        "user":     os.getenv("DB_USER", "postgres"),
        "password": os.environ.get("DB_PASSWORD", ""),
    }


# ── Step 1.2: Incident Repository ─────────────────────────────────────────────

class PostgreSQLIncidentRepository(PostgreSQLBaseRepository, IncidentRepository):
    """
    Concrete Incident Repository.
    Table: incidents (id, site_name, severity, status, description, created_at)
    """
    _table_name = "incidents"
    _id_column  = "id"

    def find_by_site(self, site_name: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM incidents WHERE site_name = %s ORDER BY created_at DESC LIMIT %s",
                        (site_name, limit)
                    )
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error("[IncidentRepo] find_by_site(%s) failed: %s", site_name, e, exc_info=True)
            return []

    def find_by_severity(self, severity_level: str, limit: int = 50) -> List[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM incidents WHERE severity = %s ORDER BY created_at DESC LIMIT %s",
                        (severity_level.upper(), limit)
                    )
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error("[IncidentRepo] find_by_severity(%s) failed: %s", severity_level, e, exc_info=True)
            return []


# ── Step 1.3: Audit Repository ────────────────────────────────────────────────

class PostgreSQLAuditRepository(PostgreSQLBaseRepository, AuditRepository):
    """
    Concrete Audit Repository — append-only (immutable records).
    Table: ai_audit_trail (event_id, actor, action_type, target, detail, created_at)
    """
    _table_name = "ai_audit_trail"
    _id_column  = "event_id"

    def add(self, entity: Dict[str, Any]) -> Dict[str, Any]:
        """Audit records are INSERT-only — never UPDATE existing rows."""
        entity.setdefault("event_id", str(uuid.uuid4()))
        return super().add(entity)

    def update(self, entity_id: str, updates: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise PermissionError("[AuditRepo] Audit records are immutable. Update is forbidden.")

    def delete(self, entity_id: str) -> bool:
        raise PermissionError("[AuditRepo] Audit records are immutable. Delete is forbidden.")

    def find_by_actor(self, user_id: str, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM ai_audit_trail WHERE actor = %s ORDER BY created_at DESC LIMIT %s",
                        (user_id, limit)
                    )
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error("[AuditRepo] find_by_actor(%s) failed: %s", user_id, e, exc_info=True)
            return []

    def find_by_action_type(self, action_type: str, limit: int = 100) -> List[Dict[str, Any]]:
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        "SELECT * FROM ai_audit_trail WHERE action_type = %s ORDER BY created_at DESC LIMIT %s",
                        (action_type, limit)
                    )
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            logger.error("[AuditRepo] find_by_action_type(%s) failed: %s", action_type, e, exc_info=True)
            return []


# ── Step 1.4: Knowledge Entity Repository ─────────────────────────────────────

class PostgreSQLKnowledgeEntityRepository(PostgreSQLBaseRepository, KnowledgeEntityRepository):
    """
    Concrete Knowledge Repository.
    Table: knowledge_chunks (chunk_id, title, content, source_url, trust_rating,
                             similarity_score, coverage_score, metadata)
    """
    _table_name = "knowledge_chunks"
    _id_column  = "chunk_id"

    def _row_to_dto(self, row: dict) -> KnowledgeChunkDTO:
        trust = row.get("trust_rating", "MEDIUM")
        try:
            trust_val = TrustRating(trust)
        except Exception:
            trust_val = TrustRating.MEDIUM
        return KnowledgeChunkDTO(
            chunk_id         = str(row.get("chunk_id", "")),
            title            = str(row.get("title", "")),
            content          = str(row.get("content", "")),
            source_url       = str(row.get("source_url", "")),
            trust_rating     = trust_val,
            similarity_score = float(row.get("similarity_score", 0.0)),
            coverage_score   = float(row.get("coverage_score", 0.0)),
            metadata         = row.get("metadata") or {},
        )

    def get_by_id(self, entity_id: str) -> Optional[KnowledgeChunkDTO]:
        row = super().get_by_id(entity_id)
        return self._row_to_dto(row) if row else None

    def get_all(self, limit: int = 100, offset: int = 0) -> List[KnowledgeChunkDTO]:
        rows = super().get_all(limit, offset)
        return [self._row_to_dto(r) for r in rows]

    def add(self, entity: KnowledgeChunkDTO) -> KnowledgeChunkDTO:
        data = {
            "chunk_id":        entity.chunk_id,
            "title":           entity.title,
            "content":         entity.content,
            "source_url":      entity.source_url,
            "trust_rating":    entity.trust_rating.value if hasattr(entity.trust_rating, "value") else str(entity.trust_rating),
            "similarity_score": entity.similarity_score,
            "coverage_score":  entity.coverage_score,
            "metadata":        json.dumps(entity.metadata),
        }
        super().add(data)
        return entity

    def update(self, entity_id: str, updates: Dict[str, Any]) -> Optional[KnowledgeChunkDTO]:
        row = super().update(entity_id, updates)
        return self._row_to_dto(row) if row else None

    def search_by_tag(self, tag: str, limit: int = 20) -> List[KnowledgeChunkDTO]:
        try:
            with self._connect() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """SELECT * FROM knowledge_chunks
                           WHERE metadata::text ILIKE %s OR content ILIKE %s
                           ORDER BY similarity_score DESC LIMIT %s""",
                        (f"%{tag}%", f"%{tag}%", limit)
                    )
                    return [self._row_to_dto(dict(r)) for r in cur.fetchall()]
        except Exception as e:
            logger.error("[KnowledgeRepo] search_by_tag(%s) failed: %s", tag, e, exc_info=True)
            return []


# ── Step 1.5: PgVector Repository ─────────────────────────────────────────────

class PgVectorRepository(VectorRepository):
    """
    Concrete vector embedding repository.
    Uses pgvector if available, falls back to numpy cosine similarity.
    Table: knowledge_embeddings (chunk_id TEXT, embedding VECTOR/TEXT, metadata JSONB)

    P0-5 Fix: _ensure_table() called ONCE at __init__, not on every operation.
    """
    _table_initialized: bool = False
    _init_lock = __import__("threading").Lock()

    def __init__(self):
        self._use_pgvector = self._check_pgvector()
        # P0-5: Initialize table schema ONCE per process lifecycle
        if not PgVectorRepository._table_initialized:
            with PgVectorRepository._init_lock:
                if not PgVectorRepository._table_initialized:
                    try:
                        with PGConnection() as conn:
                            self._ensure_table(conn)
                        PgVectorRepository._table_initialized = True
                        logger.info("[PgVectorRepo] Table schema initialized.")
                    except Exception as e:
                        logger.warning("[PgVectorRepo] Table init skipped (DB may be offline): %s", e)

    def _connect(self):
        return PGConnection()


    def _check_pgvector(self) -> bool:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
                    return cur.fetchone() is not None
        except Exception:
            return False

    def _ensure_table(self, conn):
        with conn.cursor() as cur:
            if self._use_pgvector:
                cur.execute("""CREATE TABLE IF NOT EXISTS knowledge_embeddings (
                    chunk_id TEXT PRIMARY KEY,
                    embedding VECTOR(1536),
                    metadata JSONB DEFAULT '{}'
                )""")
            else:
                cur.execute("""CREATE TABLE IF NOT EXISTS knowledge_embeddings (
                    chunk_id TEXT PRIMARY KEY,
                    embedding TEXT,
                    metadata JSONB DEFAULT '{}'
                )""")
            conn.commit()

    def upsert_embedding(self, chunk_id: str, embedding: List[float], metadata: Dict[str, Any]) -> bool:
        try:
            with self._connect() as conn:
                # Table guaranteed initialized in __init__ (P0-5 fix)
                emb_val = str(embedding) if self._use_pgvector else json.dumps(embedding)
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO knowledge_embeddings (chunk_id, embedding, metadata)
                           VALUES (%s, %s, %s)
                           ON CONFLICT (chunk_id) DO UPDATE
                           SET embedding = EXCLUDED.embedding, metadata = EXCLUDED.metadata""",
                        (chunk_id, emb_val, json.dumps(metadata))
                    )
                    conn.commit()
                return True
        except Exception as e:
            logger.error("[PgVectorRepo] upsert_embedding(%s) failed: %s", chunk_id, e, exc_info=True)
            return False

    def similarity_search(
        self, query_embedding: List[float], top_k: int = 5, threshold: float = 0.70
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        try:
            with self._connect() as conn:
                # Table guaranteed initialized in __init__ (P0-5 fix)
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    if self._use_pgvector:
                        cur.execute(
                            """SELECT chunk_id, metadata,
                                      1 - (embedding <=> %s::vector) AS similarity
                               FROM knowledge_embeddings
                               WHERE 1 - (embedding <=> %s::vector) >= %s
                               ORDER BY similarity DESC LIMIT %s""",
                            (str(query_embedding), str(query_embedding), threshold, top_k)
                        )
                        return [
                            (str(r["chunk_id"]), float(r["similarity"]), r.get("metadata") or {})
                            for r in cur.fetchall()
                        ]
                    else:
                        import numpy as np
                        cur.execute("SELECT chunk_id, embedding, metadata FROM knowledge_embeddings")
                        rows = cur.fetchall()
                        q = query_embedding

                        def cosine(a, b):
                            a, b = np.array(a), np.array(b)
                            norm = np.linalg.norm(a) * np.linalg.norm(b)
                            return float(np.dot(a, b) / norm) if norm > 0 else 0.0

                        scored = []
                        for row in rows:
                            emb = json.loads(row["embedding"]) if isinstance(row["embedding"], str) else row["embedding"]
                            sim = cosine(q, emb)
                            if sim >= threshold:
                                scored.append((str(row["chunk_id"]), sim, row.get("metadata") or {}))
                        scored.sort(key=lambda x: x[1], reverse=True)
                        return scored[:top_k]
        except Exception as e:
            logger.error("[PgVectorRepo] similarity_search failed: %s", e, exc_info=True)
            return []

    def delete_embedding(self, chunk_id: str) -> bool:
        try:
            with self._connect() as conn:
                with conn.cursor() as cur:
                    cur.execute("DELETE FROM knowledge_embeddings WHERE chunk_id = %s", (chunk_id,))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            logger.error("[PgVectorRepo] delete_embedding(%s) failed: %s", chunk_id, e, exc_info=True)
            return False
