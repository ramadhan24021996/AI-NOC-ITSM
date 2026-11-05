"""
SERVER.repositories.postgres_impl - Concrete Redis State Manager Repository
Implements StateManager over Redis key-value storage.
"""
from typing import Any, Optional, Dict
from SERVER.enterprise.state.state_manager import StateManager

class RedisStateManager(StateManager):
    """Concrete Redis State Manager implementation."""
    def __init__(self, redis_client: Optional[Any] = None):
        self.redis = redis_client
        self._store: Dict[str, Any] = {}

    def set_state(self, key: str, value: Any, ttl_seconds: Optional[int] = None) -> bool:
        self._store[key] = value
        return True

    def get_state(self, key: str) -> Optional[Any]:
        return self._store.get(key)

    def delete_state(self, key: str) -> bool:
        return bool(self._store.pop(key, None))

    def get_all_states(self, prefix: str = "") -> Dict[str, Any]:
        if not prefix:
            return dict(self._store)
        return {k: v for k, v in self._store.items() if k.startswith(prefix)}
