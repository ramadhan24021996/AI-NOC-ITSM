"""
LF-1 Learning Framework — Knowledge Store (Concrete Implementation)
PostgreSQL-backed KnowledgeStore with SHA-256 integrity and versioning.
Fallback: in-memory dict when DB is unavailable.
"""
import hashlib
import json
import logging
import os
from typing import Dict, Any, List

from .interfaces import IKnowledgeStore
from SERVER.shared.db_pool import PGConnection

logger = logging.getLogger("LF1_KNOWLEDGE_STORE")


class PostgresKnowledgeStore(IKnowledgeStore):
    """
    Production KnowledgeStore backed by PostgreSQL table: lf1_knowledge_docs
    Schema:
        doc_id TEXT PRIMARY KEY,
        content TEXT,
        metadata JSONB,
        checksum TEXT,
        version INT DEFAULT 1,
        archived BOOLEAN DEFAULT FALSE,
        created_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at TIMESTAMPTZ DEFAULT NOW()
    Falls back to in-memory store when DB unavailable (dev/test mode).
    """

    def __init__(self):
        self._memory: Dict[str, Dict[str, Any]] = {}
        self._db_available = self._ensure_table()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _ensure_table(self) -> bool:
        try:
            with PGConnection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        CREATE TABLE IF NOT EXISTS lf1_knowledge_docs (
                            doc_id      TEXT PRIMARY KEY,
                            content     TEXT,
                            metadata    JSONB DEFAULT '{}',
                            checksum    TEXT,
                            version     INT DEFAULT 1,
                            archived    BOOLEAN DEFAULT FALSE,
                            created_at  TIMESTAMPTZ DEFAULT NOW(),
                            updated_at  TIMESTAMPTZ DEFAULT NOW()
                        );
                        CREATE INDEX IF NOT EXISTS idx_lf1_docs_fts
                            ON lf1_knowledge_docs USING gin(to_tsvector('english', content));
                    """)
            logger.info("[LF1-KS] PostgreSQL table lf1_knowledge_docs ready.")
            return True
        except Exception as e:
            logger.warning("[LF1-KS] DB unavailable, using in-memory fallback: %s", e)
            return False

    @staticmethod
    def _checksum(content: str) -> str:
        return hashlib.sha256(content.encode()).hexdigest()

    # ------------------------------------------------------------------
    # IKnowledgeStore implementation
    # ------------------------------------------------------------------
    def add_document(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> bool:
        chk = self._checksum(content)
        if self._db_available:
            try:
                with PGConnection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO lf1_knowledge_docs (doc_id, content, metadata, checksum)
                            VALUES (%s, %s, %s, %s)
                            ON CONFLICT (doc_id) DO NOTHING;
                        """, (doc_id, content, json.dumps(metadata), chk))
                logger.info("[LF1-KS] add_document: %s (checksum=%s)", doc_id, chk[:8])
                return True
            except Exception as e:
                logger.error("[LF1-KS] add_document DB error: %s", e)
        # Fallback
        if doc_id not in self._memory:
            self._memory[doc_id] = {
                "content": content, "metadata": metadata,
                "checksum": chk, "version": 1, "archived": False,
            }
        return True

    def update_document(self, doc_id: str, content: str) -> bool:
        chk = self._checksum(content)
        if self._db_available:
            try:
                with PGConnection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE lf1_knowledge_docs
                            SET content = %s, checksum = %s,
                                version = version + 1, updated_at = NOW()
                            WHERE doc_id = %s AND archived = FALSE;
                        """, (content, chk, doc_id))
                        updated = cur.rowcount
                if updated:
                    logger.info("[LF1-KS] update_document: %s v+1", doc_id)
                    return True
                return False
            except Exception as e:
                logger.error("[LF1-KS] update_document DB error: %s", e)
        # Fallback
        if doc_id in self._memory and not self._memory[doc_id]["archived"]:
            self._memory[doc_id]["content"] = content
            self._memory[doc_id]["checksum"] = chk
            self._memory[doc_id]["version"] += 1
            return True
        return False

    def archive_document(self, doc_id: str) -> bool:
        if self._db_available:
            try:
                with PGConnection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            UPDATE lf1_knowledge_docs
                            SET archived = TRUE, updated_at = NOW()
                            WHERE doc_id = %s;
                        """, (doc_id,))
                logger.info("[LF1-KS] archive_document: %s", doc_id)
                return True
            except Exception as e:
                logger.error("[LF1-KS] archive_document DB error: %s", e)
        # Fallback
        if doc_id in self._memory:
            self._memory[doc_id]["archived"] = True
            return True
        return False

    def search(self, query: str) -> List[Dict[str, Any]]:
        if self._db_available:
            try:
                with PGConnection() as conn:
                    results = []
                    with conn.cursor() as cur:
                        cur.execute("""
                            SELECT doc_id, content, metadata, version
                            FROM lf1_knowledge_docs
                            WHERE archived = FALSE
                              AND to_tsvector('english', content) @@ plainto_tsquery('english', %s)
                            ORDER BY ts_rank(to_tsvector('english', content),
                                            plainto_tsquery('english', %s)) DESC
                            LIMIT 20;
                        """, (query, query))
                        for row in cur.fetchall():
                            results.append({
                                "doc_id": row[0], "content": row[1],
                                "metadata": row[2] or {}, "version": row[3],
                            })
                logger.info("[LF1-KS] search '%s' -> %d results", query, len(results))
                return results
            except Exception as e:
                logger.error("[LF1-KS] search DB error: %s", e)
        # Fallback — naive substring match
        q_lower = query.lower()
        return [
            {"doc_id": k, "content": v["content"], "metadata": v["metadata"], "version": v["version"]}
            for k, v in self._memory.items()
            if not v["archived"] and q_lower in v["content"].lower()
        ]

    def version(self, doc_id: str) -> str:
        if self._db_available:
            try:
                with PGConnection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT version FROM lf1_knowledge_docs WHERE doc_id = %s;",
                            (doc_id,)
                        )
                        row = cur.fetchone()
                return f"v{row[0]}" if row else "NOT_FOUND"
            except Exception as e:
                logger.error("[LF1-KS] version DB error: %s", e)
        doc = self._memory.get(doc_id)
        return f"v{doc['version']}" if doc else "NOT_FOUND"
