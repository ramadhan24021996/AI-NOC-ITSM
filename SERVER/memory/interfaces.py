"""
AI Memory Fabric Interfaces for Enterprise AI Operations Platform
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

class MemoryStore(ABC):
    """Abstract interface for foundational memory persistence."""
    @abstractmethod
    def store(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        pass

    @abstractmethod
    def retrieve(self, key: str) -> Optional[Any]:
        pass

class ConversationMemory(ABC):
    """Abstract interface for short-term chat dialogue buffer."""
    @abstractmethod
    def add_message(self, session_id: str, sender: str, text: str) -> None:
        pass

    @abstractmethod
    def get_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        pass

class EpisodeMemory(ABC):
    """Abstract interface for past incident execution episodes."""
    @abstractmethod
    def record_episode(self, incident_id: str, episode_data: Dict[str, Any]) -> None:
        pass

class SemanticMemory(ABC):
    """Abstract interface for long-term vector semantic knowledge graph memory."""
    @abstractmethod
    def query_semantic(self, vector_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATIONS — Step 3
# ══════════════════════════════════════════════════════════════════════════════
import os
import json
import logging
import redis as _redis
import psycopg2
from SERVER.shared.db_pool import PGConnection, get_redis
from psycopg2.extras import RealDictCursor
from datetime import datetime, timezone

_mlog = logging.getLogger("memory.impl")

def _pgconn():
    return PGConnection()

def _rconn():
    return get_redis()


# Step 3.1
class RedisMemoryStore(MemoryStore):
    """Redis-backed key-value memory store with optional TTL."""

    def store(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        try:
            r = _rconn()
            serialized = json.dumps(value, default=str)
            if ttl_seconds:
                r.setex(f"mem:{key}", ttl_seconds, serialized)
            else:
                r.set(f"mem:{key}", serialized)
            return True
        except Exception as e:
            _mlog.error("[RedisMemoryStore] store(%s) failed: %s", key, e, exc_info=True)
            return False

    def retrieve(self, key: str) -> Optional[Any]:
        try:
            r = _rconn()
            val = r.get(f"mem:{key}")
            return json.loads(val) if val else None
        except Exception as e:
            _mlog.error("[RedisMemoryStore] retrieve(%s) failed: %s", key, e, exc_info=True)
            return None


# Step 3.2
class RedisConversationMemory(ConversationMemory):
    """Redis list-based short-term conversation memory per session."""
    MAX_HISTORY = 50

    def add_message(self, session_id: str, sender: str, text: str) -> None:
        try:
            r = _rconn()
            key = f"conv:{session_id}"
            entry = json.dumps({"sender": sender, "text": text,
                                "ts": datetime.now(timezone.utc).isoformat()})
            r.rpush(key, entry)
            r.ltrim(key, -self.MAX_HISTORY, -1)
            r.expire(key, 3600)
        except Exception as e:
            _mlog.error("[ConvMemory] add_message(%s) failed: %s", session_id, e, exc_info=True)

    def get_history(self, session_id: str, limit: int = 10) -> List[Dict[str, str]]:
        try:
            r = _rconn()
            raw = r.lrange(f"conv:{session_id}", -limit, -1)
            return [json.loads(x) for x in raw]
        except Exception as e:
            _mlog.error("[ConvMemory] get_history(%s) failed: %s", session_id, e, exc_info=True)
            return []


# Step 3.3
class PostgreSQLEpisodeMemory(EpisodeMemory):
    """Writes incident execution episodes to incident_events table."""

    def record_episode(self, incident_id: str, episode_data: Dict[str, Any]) -> None:
        try:
            with PGConnection() as conn:
                with conn.cursor() as cur:
                    cur.execute(
                        """INSERT INTO incident_events
                           (incident_id, event_type, timestamp, description, data)
                           VALUES (%s, %s, NOW(), %s, %s)""",
                        (incident_id, episode_data.get("event_type","EPISODE"),
                         episode_data.get("description",""),
                         json.dumps(episode_data))
                    )
                    conn.commit()
        except Exception as e:
            _mlog.error("[EpisodeMemory] record_episode(%s) failed: %s", incident_id, e, exc_info=True)


# Step 3.4
class PostgreSQLSemanticMemory(SemanticMemory):
    """Cosine similarity search against knowledge_embeddings (pgvector or numpy fallback)."""

    def query_semantic(self, vector_embedding: List[float], top_k: int = 5) -> List[Dict[str, Any]]:
        try:
            from SERVER.repositories.impl import PgVectorRepository
            repo = PgVectorRepository()
            results = repo.similarity_search(vector_embedding, top_k=top_k, threshold=0.50)
            return [{"chunk_id": cid, "score": score, "metadata": meta}
                    for cid, score, meta in results]
        except Exception as e:
            _mlog.error("[SemanticMemory] query_semantic failed: %s", e, exc_info=True)
            return []
