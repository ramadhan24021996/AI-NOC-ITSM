from abc import ABC, abstractmethod
from typing import Dict, Any, List
from enum import Enum
import threading
import logging
import importlib
import os
import json
from datetime import datetime, timezone
from pydantic import BaseModel

class CapabilityState(Enum):
    REGISTERED = "REGISTERED"
    INSTALLED = "INSTALLED"
    VALIDATED = "VALIDATED"
    READY = "READY"
    ACTIVE = "ACTIVE"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"

class CapabilityManifest(BaseModel):
    engine: str
    version: str
    status: str
    dependencies: List[str]
    requires: List[str]
    provides: List[str]
    owner: str
    api_version: str
    schema_version: int

class IHealthContract(ABC):
    @abstractmethod
    def health(self) -> bool:
        raise NotImplementedError
    @abstractmethod
    def ready(self) -> bool:
        raise NotImplementedError
    @abstractmethod
    def version(self) -> str:
        raise NotImplementedError
    @abstractmethod
    def dependency_status(self) -> Dict[str, bool]:
        raise NotImplementedError
    @abstractmethod
    def metrics(self) -> Dict[str, Any]:
        raise NotImplementedError

class IPluginLoader(ABC):
    @abstractmethod
    def discover(self) -> List[CapabilityManifest]:
        raise NotImplementedError
    @abstractmethod
    def load(self, engine_name: str) -> bool:
        raise NotImplementedError
    @abstractmethod
    def validate(self, manifest: CapabilityManifest) -> bool:
        raise NotImplementedError
    @abstractmethod
    def activate(self, engine_name: str) -> bool:
        raise NotImplementedError
    @abstractmethod
    def check_compatibility(self, manifest: CapabilityManifest) -> bool:
        raise NotImplementedError

class IRegistry(IHealthContract, IPluginLoader, ABC):
    @abstractmethod
    def register(self, manifest: CapabilityManifest) -> bool:
        raise NotImplementedError


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 6.7 (P1-2 Persisted with Redis)
# ══════════════════════════════════════════════════════════════════════════════
_crlog = logging.getLogger("lf1.registry")

class CapabilityRegistryImpl(IRegistry):
    """
    Concrete capability registry with state machine: REGISTERED → INSTALLED → VALIDATED → READY → ACTIVE.
    Auto-discovers engines from the learning/ sub-package filesystem.
    Persists registry state & manifests to Redis for cross-restart durability.
    """
    REDIS_KEY_PREFIX = "lf1:capability:"

    def __init__(self):
        self._manifests: Dict[str, CapabilityManifest] = {}
        self._states: Dict[str, CapabilityState] = {}
        self._lock = threading.RLock()
        self._load_from_redis()

    def _sync_to_redis(self, engine_name: str):
        try:
            from SERVER.shared.db_pool import get_redis
            r = get_redis()
            manifest = self._manifests.get(engine_name)
            state = self._states.get(engine_name)
            manifest_data = None
            if manifest:
                # Pydantic v2: model_dump(); v1 fallback not needed (project uses v2)
                manifest_data = manifest.model_dump()
            data = {
                "manifest": manifest_data,
                "state": state.value if state is not None else None
            }
            r.set(f"{self.REDIS_KEY_PREFIX}{engine_name}", json.dumps(data, default=str))
        except Exception as e:
            _crlog.warning("[CapabilityRegistry] Failed to sync '%s' to Redis: %s", engine_name, e)

    def _load_from_redis(self):
        try:
            from SERVER.shared.db_pool import get_redis
            r = get_redis()
            keys = r.keys(f"{self.REDIS_KEY_PREFIX}*")
            if keys:
                values = r.mget(keys)
                for k, v in zip(keys, values):
                    if v:
                        k_str: str = k.decode("utf-8") if isinstance(k, bytes) else k
                        engine_name = k_str.replace(self.REDIS_KEY_PREFIX, "")
                        v_str: str = v.decode("utf-8") if isinstance(v, bytes) else v
                        item = json.loads(v_str)
                        if "manifest" in item and isinstance(item["manifest"], dict):
                            m = CapabilityManifest(**item["manifest"])
                            self._manifests[engine_name] = m
                        if "state" in item and item["state"]:
                            try:
                                self._states[engine_name] = CapabilityState(item["state"])
                            except Exception:
                                pass
                _crlog.info("[CapabilityRegistry] Loaded %d engines from Redis", len(keys))
        except Exception as e:
            _crlog.warning("[CapabilityRegistry] Failed to load state from Redis: %s", e)

    # ── IHealthContract ───────────────────────────────────────────────────────
    def health(self) -> bool:
        return True

    def ready(self) -> bool:
        active = sum(1 for s in self._states.values() if s == CapabilityState.ACTIVE)
        _crlog.info("[CapabilityRegistry] %d/%d engines ACTIVE", active, len(self._manifests))
        return active > 0

    def version(self) -> str:
        return "1.0.0"

    def dependency_status(self) -> Dict[str, bool]:
        status = {}
        for name, manifest in self._manifests.items():
            for dep in manifest.dependencies:
                status[dep] = dep in self._manifests
        return status

    def metrics(self) -> Dict[str, Any]:
        return {
            "total_registered": len(self._manifests),
            "active_count": sum(1 for s in self._states.values() if s == CapabilityState.ACTIVE),
            "ready_count": sum(1 for s in self._states.values() if s in (CapabilityState.READY, CapabilityState.ACTIVE)),
            "checked_at": datetime.now(timezone.utc).isoformat(),
        }

    # ── IPluginLoader ─────────────────────────────────────────────────────────
    def discover(self) -> List[CapabilityManifest]:
        """Scan learning/ subdirectories for engines with a manifest.json."""
        found = []
        base_path = os.path.dirname(os.path.abspath(__file__))
        parent = os.path.dirname(base_path)
        for entry in os.scandir(parent):
            if entry.is_dir():
                manifest_path = os.path.join(entry.path, "manifest.json")
                if os.path.exists(manifest_path):
                    try:
                        import json
                        with open(manifest_path) as f:
                            data = json.load(f)
                        m = CapabilityManifest(**data)
                        found.append(m)
                        _crlog.info("[CapabilityRegistry] Discovered: %s v%s", m.engine, m.version)
                    except Exception as e:
                        _crlog.warning("[CapabilityRegistry] Failed to parse manifest at %s: %s", manifest_path, e)
        return found

    def load(self, engine_name: str) -> bool:
        with self._lock:
            for m in self._manifests.values():
                if m.engine == engine_name:
                    self._states[engine_name] = CapabilityState.INSTALLED
                    self._sync_to_redis(engine_name)
                    _crlog.info("[CapabilityRegistry] Loaded: %s", engine_name)
                    return True
        _crlog.warning("[CapabilityRegistry] Engine not found: %s", engine_name)
        return False

    def validate(self, manifest: CapabilityManifest) -> bool:
        if not manifest.engine or not manifest.version:
            return False
        if manifest.schema_version < 1:
            return False
        _crlog.info("[CapabilityRegistry] Validated manifest: %s", manifest.engine)
        return True

    def activate(self, engine_name: str) -> bool:
        with self._lock:
            if self._states.get(engine_name) in (CapabilityState.VALIDATED, CapabilityState.READY, CapabilityState.INSTALLED):
                self._states[engine_name] = CapabilityState.ACTIVE
                self._sync_to_redis(engine_name)
                _crlog.info("[CapabilityRegistry] ACTIVATED: %s", engine_name)
                return True
        return False

    def check_compatibility(self, manifest: CapabilityManifest) -> bool:
        for dep in manifest.dependencies:
            if dep not in self._manifests:
                _crlog.warning("[CapabilityRegistry] Dependency missing: %s (required by %s)", dep, manifest.engine)
                return False
        return True

    def register(self, manifest: CapabilityManifest) -> bool:
        if not self.validate(manifest):
            return False
        with self._lock:
            self._manifests[manifest.engine] = manifest
            self._states[manifest.engine] = CapabilityState.REGISTERED
            self._sync_to_redis(manifest.engine)
        _crlog.info("[CapabilityRegistry] REGISTERED: %s v%s", manifest.engine, manifest.version)
        return True

