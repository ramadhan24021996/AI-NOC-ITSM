"""
LF-1 Learning Framework — Feature Registry (Concrete Implementation)
PostgreSQL-backed registry for feature metadata with in-memory cache.
"""
import json
import logging
import os
import time
from typing import Dict, Any

from .interfaces import IFeatureRegistry
from SERVER.shared.db_pool import PGConnection

logger = logging.getLogger("LF1_FEATURE_REGISTRY")

# In-memory cache TTL in seconds
_CACHE_TTL = int(os.getenv("LF1_REGISTRY_CACHE_TTL", "300"))  # 5 min



class PostgresFeatureRegistry(IFeatureRegistry):
    """
    Feature metadata registry backed by PostgreSQL table: lf1_feature_registry

    Schema:
        feature_id   TEXT PRIMARY KEY,
        metadata     JSONB,
        registered_at TIMESTAMPTZ DEFAULT NOW(),
        updated_at   TIMESTAMPTZ DEFAULT NOW()

    Features:
    - write-through cache with configurable TTL
    - PostgreSQL persistence with JSONB metadata
    - in-memory fallback for dev/test environments
    """

    def __init__(self):
        # In-memory cache: {feature_id: (metadata_dict, expire_ts)}
        self._cache: Dict[str, tuple] = {}
        # Fallback in-memory store (when DB unavailable)
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
                        CREATE TABLE IF NOT EXISTS lf1_feature_registry (
                            feature_id    TEXT PRIMARY KEY,
                            metadata      JSONB DEFAULT '{}',
                            registered_at TIMESTAMPTZ DEFAULT NOW(),
                            updated_at    TIMESTAMPTZ DEFAULT NOW()
                        );
                    """)
            logger.info("[LF1-REGISTRY] PostgreSQL table lf1_feature_registry ready.")
            return True
        except Exception as e:
            logger.warning("[LF1-REGISTRY] DB unavailable, using in-memory fallback: %s", e)
            return False

    def _cache_get(self, feature_id: str) -> Dict[str, Any]:
        entry = self._cache.get(feature_id)
        if entry and time.time() < entry[1]:
            return entry[0]
        return {}

    def _cache_set(self, feature_id: str, metadata: Dict[str, Any]) -> None:
        self._cache[feature_id] = (metadata, time.time() + _CACHE_TTL)

    # ------------------------------------------------------------------
    # IFeatureRegistry implementation
    # ------------------------------------------------------------------
    def register_feature_metadata(self, metadata: Dict[str, Any]) -> bool:
        """
        Registers or updates feature metadata.
        Required field: metadata['feature_id']
        """
        feature_id = metadata.get("feature_id", "")
        if not feature_id:
            logger.error("[LF1-REGISTRY] register_feature_metadata: 'feature_id' required.")
            return False

        if self._db_available:
            try:
                with PGConnection() as conn:
                    with conn.cursor() as cur:
                        cur.execute("""
                            INSERT INTO lf1_feature_registry (feature_id, metadata)
                            VALUES (%s, %s)
                            ON CONFLICT (feature_id) DO UPDATE
                                SET metadata = EXCLUDED.metadata,
                                    updated_at = NOW();
                        """, (feature_id, json.dumps(metadata)))
                self._cache_set(feature_id, metadata)
                logger.info("[LF1-REGISTRY] Registered feature: %s", feature_id)
                return True
            except Exception as e:
                logger.error("[LF1-REGISTRY] register_feature_metadata DB error: %s", e)

        # Fallback
        self._memory[feature_id] = metadata
        self._cache_set(feature_id, metadata)
        logger.info("[LF1-REGISTRY] Registered feature (memory): %s", feature_id)
        return True

    def get_feature_metadata(self, feature_id: str) -> Dict[str, Any]:
        """
        Retrieves feature metadata by feature_id.
        Returns {} if not found.
        Checks in-memory cache first, then DB.
        """
        # Cache hit
        cached = self._cache_get(feature_id)
        if cached:
            logger.debug("[LF1-REGISTRY] Cache hit for feature: %s", feature_id)
            return cached

        if self._db_available:
            try:
                with PGConnection() as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "SELECT metadata FROM lf1_feature_registry WHERE feature_id = %s;",
                            (feature_id,)
                        )
                        row = cur.fetchone()
                if row:
                    meta = row[0] if isinstance(row[0], dict) else json.loads(row[0])
                    self._cache_set(feature_id, meta)
                    return meta
                logger.warning("[LF1-REGISTRY] feature not found: %s", feature_id)
                return {}
            except Exception as e:
                logger.error("[LF1-REGISTRY] get_feature_metadata DB error: %s", e)

        # Fallback
        return self._memory.get(feature_id, {})
