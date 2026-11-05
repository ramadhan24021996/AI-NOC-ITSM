"""
SERVER.enterprise.state - State Manager
Manages persistent state for incident workflows beyond in-process memory.
"""
from abc import ABC, abstractmethod
from typing import Any, Optional, Dict

class StateManager(ABC):
    """Abstract state manager interface. State MUST be persistable (not in-memory only)."""

    @abstractmethod
    def set_state(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        pass

    @abstractmethod
    def get_state(self, key: str) -> Optional[Any]:
        pass

    @abstractmethod
    def delete_state(self, key: str) -> bool:
        pass

    @abstractmethod
    def get_all_states(self, prefix: str = "") -> Dict[str, Any]:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 5.2
# ══════════════════════════════════════════════════════════════════════════════
import os, json, logging
import redis as _redis
from SERVER.shared.db_pool import get_redis

_slog = logging.getLogger("enterprise.state")

def _rconn():
    return get_redis()

class RedisStateManager(StateManager):
    """
    Redis-backed persistent state manager with namespace prefix.
    Keys: state:{prefix}{key} — JSON serialized values.
    """
    def __init__(self, namespace: str = "workflow"):
        self._ns = f"state:{namespace}:"

    def _key(self, k: str) -> str:
        return f"{self._ns}{k}"

    def set_state(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        try:
            r = _rconn()
            serialized = json.dumps(value, default=str)
            if ttl_seconds:
                r.setex(self._key(key), ttl_seconds, serialized)
            else:
                r.set(self._key(key), serialized)
            return True
        except Exception as e:
            _slog.error("[RedisStateManager] set_state(%s) failed: %s", key, e, exc_info=True)
            return False

    def get_state(self, key: str) -> Optional[Any]:
        try:
            r = _rconn()
            val = r.get(self._key(key))
            return json.loads(val) if val is not None else None
        except Exception as e:
            _slog.error("[RedisStateManager] get_state(%s) failed: %s", key, e, exc_info=True)
            return None

    def delete_state(self, key: str) -> bool:
        try:
            r = _rconn()
            return r.delete(self._key(key)) > 0
        except Exception as e:
            _slog.error("[RedisStateManager] delete_state(%s) failed: %s", key, e, exc_info=True)
            return False

    def get_all_states(self, prefix: str = "") -> Dict[str, Any]:
        try:
            r = _rconn()
            pattern = f"{self._ns}{prefix}*"
            keys = r.keys(pattern)
            if not keys:
                return {}
            values = r.mget(keys)
            result = {}
            for k, v in zip(keys, values):
                short_key = k.replace(self._ns, "", 1)
                result[short_key] = json.loads(v) if v else None
            return result
        except Exception as e:
            _slog.error("[RedisStateManager] get_all_states failed: %s", e, exc_info=True)
            return {}
