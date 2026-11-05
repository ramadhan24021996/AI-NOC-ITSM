"""
AI Kernel - Configuration Loader
Centralized environment & runtime configuration management.
"""
import os
from typing import Dict, Any, Optional

class ConfigLoader:
    """Foundational configuration loader for environment and runtime parameters."""
    def __init__(self, env_prefix: str = ""):
        self.env_prefix = env_prefix
        self._configs: Dict[str, Any] = {}

    def get(self, key: str, default: Optional[Any] = None) -> Any:
        full_key = f"{self.env_prefix}{key}" if self.env_prefix else key
        return os.environ.get(full_key, self._configs.get(key, default))

    def set(self, key: str, value: Any) -> None:
        self._configs[key] = value

    def get_bool(self, key: str, default: bool = False) -> bool:
        val = self.get(key)
        if val is None:
            return default
        if isinstance(val, bool):
            return val
        return str(val).lower() in ("true", "1", "yes", "on")
