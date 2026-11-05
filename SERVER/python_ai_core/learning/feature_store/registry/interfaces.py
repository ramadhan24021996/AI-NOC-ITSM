from abc import ABC, abstractmethod
from typing import Dict, Any, List

class IFeatureRegistry(ABC):
    @abstractmethod
    def register_feature_metadata(self, metadata: Dict[str, Any]) -> bool:
        raise NotImplementedError
    @abstractmethod
    def get_feature_metadata(self, feature_id: str) -> Dict[str, Any]:
        raise NotImplementedError


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 6.6 (P1-1 Persisted with Redis)
# ══════════════════════════════════════════════════════════════════════════════
import json
import threading
import logging
from datetime import datetime, timezone
from SERVER.shared.db_pool import get_redis

_frlog = logging.getLogger("lf2.feature_registry")

class InMemoryFeatureRegistry(IFeatureRegistry):
    """
    Thread-safe feature registry with Redis write-through persistence.
    Maintains local cache for speed and syncs with Redis for durability across restarts.
    """
    REDIS_KEY_PREFIX = "lf2:feature_meta:"

    def __init__(self):
        self._store: Dict[str, Any] = {}
        self._lock = threading.RLock()
        self._load_from_redis()

    def _load_from_redis(self):
        try:
            r = get_redis()
            keys = r.keys(f"{self.REDIS_KEY_PREFIX}*")
            if keys:
                values = r.mget(keys)
                for k, v in zip(keys, values):
                    if v:
                        k_str = k.decode("utf-8") if isinstance(k, bytes) else str(k)
                        fid = k_str.replace(self.REDIS_KEY_PREFIX, "")
                        v_str = v.decode("utf-8") if isinstance(v, bytes) else str(v)
                        self._store[fid] = json.loads(v_str)
                _frlog.info("[FeatureRegistry] Loaded %d feature metadata records from Redis", len(keys))
        except Exception as e:
            _frlog.warning("[FeatureRegistry] Failed to load initial state from Redis: %s", e)

    def register_feature_metadata(self, metadata: Dict[str, Any]) -> bool:
        fid = metadata.get("feature_id", "")
        if not fid:
            _frlog.error("[FeatureRegistry] register_feature_metadata — missing feature_id")
            return False
        with self._lock:
            metadata["registered_at"] = metadata.get("registered_at") or datetime.now(timezone.utc).isoformat()
            self._store[fid] = metadata
            try:
                r = get_redis()
                r.set(f"{self.REDIS_KEY_PREFIX}{fid}", json.dumps(metadata, default=str))
            except Exception as e:
                _frlog.warning("[FeatureRegistry] Failed to write feature '%s' to Redis: %s", fid, e)
        _frlog.info("[FeatureRegistry] Registered feature '%s'", fid)
        return True

    def get_feature_metadata(self, feature_id: str) -> Dict[str, Any]:
        with self._lock:
            if feature_id in self._store:
                return dict(self._store[feature_id])
        # Cache miss fallback to Redis
        try:
            r = get_redis()
            val = r.get(f"{self.REDIS_KEY_PREFIX}{feature_id}")
            if val:
                val_str = val.decode("utf-8") if isinstance(val, bytes) else str(val)
                data = json.loads(val_str)
                with self._lock:
                    self._store[feature_id] = data
                return dict(data)
        except Exception as e:
            _frlog.warning("[FeatureRegistry] Redis lookup failed for '%s': %s", feature_id, e)
        return {}


