from abc import ABC, abstractmethod
from typing import Dict, Any, List

class IKnowledgeStore(ABC):
    @abstractmethod
    def add_document(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> bool:
        raise NotImplementedError("LF-1 Framework: add_document not implemented")

    @abstractmethod
    def update_document(self, doc_id: str, content: str) -> bool:
        raise NotImplementedError("LF-1 Framework: update_document not implemented")

    @abstractmethod
    def archive_document(self, doc_id: str) -> bool:
        raise NotImplementedError("LF-1 Framework: archive_document not implemented")

    @abstractmethod
    def search(self, query: str) -> List[Dict[str, Any]]:
        raise NotImplementedError("LF-1 Framework: search not implemented")

    @abstractmethod
    def version(self, doc_id: str) -> str:
        raise NotImplementedError("LF-1 Framework: version not implemented")


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 6.1
# ══════════════════════════════════════════════════════════════════════════════
import os, json, logging
import psycopg2
from SERVER.shared.db_pool import PGConnection, get_redis
from psycopg2.extras import RealDictCursor

_kslog = logging.getLogger("lf1.knowledge_store")

def _pgconn():
    return PGConnection()

class PostgreSQLKnowledgeStore(IKnowledgeStore):
    """LF-1 concrete knowledge store backed by PostgreSQL knowledge_chunks table."""

    def add_document(self, doc_id: str, content: str, metadata: Dict[str, Any]) -> bool:
        try:
            with PGConnection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO knowledge_chunks (chunk_id, title, content, source_url, trust_rating, metadata)
                           VALUES (%s, %s, %s, %s, %s, %s)
                           ON CONFLICT (chunk_id) DO UPDATE SET content=EXCLUDED.content, metadata=EXCLUDED.metadata""",
                        (doc_id, metadata.get("title",""), content,
                         metadata.get("source_url",""), metadata.get("trust_rating","MEDIUM"),
                         json.dumps(metadata))
                    )
                    conn.commit()
            return True
        except Exception as e:
            _kslog.error("[KnowledgeStore] add_document(%s) failed: %s", doc_id, e, exc_info=True)
            return False

    def update_document(self, doc_id: str, content: str) -> bool:
        try:
            with PGConnection() as conn:
                with conn.cursor() as cur:
                    cur.execute("UPDATE knowledge_chunks SET content=%s WHERE chunk_id=%s", (content, doc_id))
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            _kslog.error("[KnowledgeStore] update_document(%s) failed: %s", doc_id, e, exc_info=True)
            return False

    def archive_document(self, doc_id: str) -> bool:
        try:
            with PGConnection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        "UPDATE knowledge_chunks SET trust_rating='ARCHIVED', metadata=metadata || '{\"archived\":true}' WHERE chunk_id=%s",
                        (doc_id,)
                    )
                    conn.commit()
                    return cur.rowcount > 0
        except Exception as e:
            _kslog.error("[KnowledgeStore] archive_document(%s) failed: %s", doc_id, e, exc_info=True)
            return False

    def search(self, query: str) -> List[Dict[str, Any]]:
        try:
            with PGConnection() as conn:
                with conn.cursor(cursor_factory=RealDictCursor) as cur:
                    cur.execute(
                        """SELECT chunk_id, title, content, source_url, trust_rating, metadata
                           FROM knowledge_chunks
                           WHERE to_tsvector('english', content||' '||title) @@ plainto_tsquery('english',%s)
                             AND (metadata->>'archived') IS DISTINCT FROM 'true'
                           ORDER BY similarity_score DESC LIMIT 20""",
                        (query,)
                    )
                    return [dict(r) for r in cur.fetchall()]
        except Exception as e:
            _kslog.error("[KnowledgeStore] search failed: %s", e, exc_info=True)
            return []

    def version(self, doc_id: str) -> str:
        try:
            with PGConnection() as conn:
                with conn.cursor() as cur:
                    cur.execute("SELECT metadata->>'version' FROM knowledge_chunks WHERE chunk_id=%s", (doc_id,))
                    row = cur.fetchone()
                    return str(row[0]) if row and row[0] else "1.0.0"
        except Exception as e:
            _kslog.error("[KnowledgeStore] version(%s) failed: %s", doc_id, e, exc_info=True)
            return "unknown"
