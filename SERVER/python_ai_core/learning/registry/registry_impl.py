"""
LF-1 Learning Framework — Capability Registry (Concrete Implementation)
Master registry that discovers, loads, validates, and activates
LF-1 engine plugins (Knowledge Store, Evaluator, Scheduler, etc.)
"""
import importlib
import logging
import os
import time
from typing import Dict, Any, List

from .interfaces import (
    IRegistry, IHealthContract, IPluginLoader,
    CapabilityManifest, CapabilityState
)

logger = logging.getLogger("LF1_CAPABILITY_REGISTRY")

# Directory where capability manifests (manifest.json) reside
_CAPABILITIES_DIR = os.getenv(
    "LF1_CAPABILITIES_DIR",
    os.path.join(os.path.dirname(__file__), "..", "..")
)


class CapabilityRegistry(IRegistry, IHealthContract):
    """
    Central LF-1 capability registry.

    Lifecycle:
        discover() → load() → validate() → activate()

    Supports:
        check_compatibility() — validates semver compatibility before activation
        health()              — reports readiness of all active capabilities

    Usage example:
        registry = CapabilityRegistry()
        manifests = registry.discover()
        for m in manifests:
            if registry.validate(m):
                registry.load(m.engine)
                registry.activate(m.engine)
    """

    def __init__(self):
        self._manifests: Dict[str, CapabilityManifest] = {}
        self._active: Dict[str, bool] = {}
        self._instances: Dict[str, Any] = {}
        self._states: Dict[str, CapabilityState] = {}
        self._loaded_at: Dict[str, float] = {}
        logger.info("[LF1-REG] CapabilityRegistry initialized.")

    # ------------------------------------------------------------------
    # IPluginLoader implementation
    # ------------------------------------------------------------------
    def discover(self) -> List[CapabilityManifest]:
        """
        Discovers available LF-1 engine capabilities.
        Returns hardcoded manifests for all 8 LF-1 engines.
        In production: scan _CAPABILITIES_DIR for manifest.json files.
        """
        hardcoded_manifests = [
            CapabilityManifest(
                engine="knowledge_store",
                version="1.0.0", status=CapabilityState.REGISTERED.value,
                dependencies=["psycopg2"],
                requires=["DB_HOST", "DB_PORT"],
                provides=["IKnowledgeStore"],
                owner="lf1_framework",
                api_version="v1",
                schema_version=1,
            ),
            CapabilityManifest(
                engine="evaluator",
                version="1.0.0", status=CapabilityState.REGISTERED.value,
                dependencies=[],
                requires=[],
                provides=["IEvaluationContract"],
                owner="lf1_framework",
                api_version="v1",
                schema_version=1,
            ),
            CapabilityManifest(
                engine="scheduler",
                version="1.0.0", status=CapabilityState.REGISTERED.value,
                dependencies=["asyncio"],
                requires=[],
                provides=["IScheduler"],
                owner="lf1_framework",
                api_version="v1",
                schema_version=1,
            ),
            CapabilityManifest(
                engine="versioning",
                version="1.0.0", status=CapabilityState.REGISTERED.value,
                dependencies=[],
                requires=[],
                provides=["IVersionController"],
                owner="lf1_framework",
                api_version="v1",
                schema_version=1,
            ),
            CapabilityManifest(
                engine="audit",
                version="1.0.0", status=CapabilityState.REGISTERED.value,
                dependencies=["services.audit_logger"],
                requires=[],
                provides=["IAuditLogger"],
                owner="lf1_framework",
                api_version="v1",
                schema_version=1,
            ),
            CapabilityManifest(
                engine="metrics",
                version="1.0.0", status=CapabilityState.REGISTERED.value,
                dependencies=["redis"],
                requires=[],
                provides=["IMetricsTracker"],
                owner="lf1_framework",
                api_version="v1",
                schema_version=1,
            ),
            CapabilityManifest(
                engine="feature_validator",
                version="1.0.0", status=CapabilityState.REGISTERED.value,
                dependencies=[],
                requires=[],
                provides=["IFeatureValidator"],
                owner="lf1_framework",
                api_version="v1",
                schema_version=1,
            ),
            CapabilityManifest(
                engine="feature_registry",
                version="1.0.0", status=CapabilityState.REGISTERED.value,
                dependencies=["psycopg2"],
                requires=["DB_HOST", "DB_PORT"],
                provides=["IFeatureRegistry"],
                owner="lf1_framework",
                api_version="v1",
                schema_version=1,
            ),
        ]
        for m in hardcoded_manifests:
            self._manifests[m.engine] = m
            self._states[m.engine] = CapabilityState.REGISTERED

        logger.info("[LF1-REG] discover() found %d capabilities.", len(hardcoded_manifests))
        return hardcoded_manifests

    def load(self, engine_name: str) -> bool:
        """
        Dynamically loads the concrete implementation for engine_name.
        Maps engine names to their concrete classes.
        """
        _engine_map = {
            "knowledge_store":  ("learning.knowledge_store.knowledge_store_impl", "PostgresKnowledgeStore"),
            "evaluator":        ("learning.evaluator.evaluator_impl", "LLMEvaluationContract"),
            "scheduler":        ("learning.scheduler.scheduler_impl", "AsyncIOScheduler"),
            "versioning":       ("learning.versioning.versioning_impl", "SemanticVersionController"),
            "audit":            ("learning.audit.audit_impl", "LearningAuditLogger"),
            "metrics":          ("learning.metrics.metrics_impl", "PrometheusMetricsTracker"),
            "feature_validator":("learning.feature_store.validators.validator_impl", "TelemetryFeatureValidator"),
            "feature_registry": ("learning.feature_store.registry.registry_impl", "PostgresFeatureRegistry"),
        }
        if engine_name not in _engine_map:
            logger.error("[LF1-REG] load(): unknown engine '%s'", engine_name)
            return False

        module_path, class_name = _engine_map[engine_name]
        try:
            module = importlib.import_module(module_path)
            cls = getattr(module, class_name)
            self._instances[engine_name] = cls()
            self._states[engine_name] = CapabilityState.INSTALLED
            self._loaded_at[engine_name] = time.time()
            logger.info("[LF1-REG] load(): '%s' -> %s.%s INSTALLED",
                        engine_name, module_path, class_name)
            return True
        except Exception as e:
            logger.error("[LF1-REG] load() FAILED for '%s': %s", engine_name, e)
            return False

    def validate(self, manifest: CapabilityManifest) -> bool:
        """
        Validates that a manifest is well-formed and meets schema version requirement.
        """
        if not manifest.engine or not manifest.version:
            logger.warning("[LF1-REG] validate(): manifest missing engine or version.")
            return False
        if manifest.schema_version < 1:
            logger.warning("[LF1-REG] validate(): schema_version must be >= 1.")
            return False
        # Check required env vars
        missing_env = [k for k in manifest.requires if not os.getenv(k)]
        if missing_env:
            logger.warning("[LF1-REG] validate(): missing env vars for '%s': %s",
                           manifest.engine, missing_env)
            # Not a hard fail — log and proceed (may use fallback)
        self._states[manifest.engine] = CapabilityState.VALIDATED
        logger.info("[LF1-REG] validate(): '%s' VALIDATED.", manifest.engine)
        return True

    def activate(self, engine_name: str) -> bool:
        """Marks a loaded engine as ACTIVE and returns its instance."""
        if engine_name not in self._instances:
            logger.error("[LF1-REG] activate(): '%s' not loaded. Call load() first.", engine_name)
            return False
        self._states[engine_name] = CapabilityState.ACTIVE
        self._active[engine_name] = True
        logger.info("[LF1-REG] activate(): '%s' is now ACTIVE.", engine_name)
        return True

    def get(self, engine_name: str) -> Any:
        """Returns the active instance of the requested engine, or None."""
        return self._instances.get(engine_name)

    # ------------------------------------------------------------------
    # IRegistry extension & register implementation
    # ------------------------------------------------------------------
    def register(self, manifest: CapabilityManifest) -> bool:
        """Registers a capability manifest into the registry."""
        if not manifest or not manifest.engine:
            return False
        self._manifests[manifest.engine] = manifest
        self._states[manifest.engine] = CapabilityState.REGISTERED
        logger.info("[LF1-REG] register(): '%s' REGISTERED.", manifest.engine)
        return True

    def check_compatibility(self, manifest: CapabilityManifest) -> bool:
        """
        Checks that the manifest's schema_version is compatible with
        the registry's current schema version (1).
        """
        current_schema_version = 1
        compatible = manifest.schema_version <= current_schema_version
        if not compatible:
            logger.warning(
                "[LF1-REG] check_compatibility: schema_version %d > registry version %d. INCOMPATIBLE.",
                manifest.schema_version, current_schema_version
            )
        return compatible

    # ------------------------------------------------------------------
    # IHealthContract implementation
    # ------------------------------------------------------------------
    def health(self) -> bool:
        """Returns True if at least one capability is ACTIVE."""
        return any(self._active.values())

    def ready(self) -> bool:
        """Returns True if all registered capabilities are ACTIVE."""
        if not self._manifests:
            return False
        return all(
            self._states.get(name) == CapabilityState.ACTIVE
            for name in self._manifests
        )

    def version(self) -> str:
        """Returns the registry version string."""
        return "1.0.0"

    def dependency_status(self) -> Dict[str, bool]:
        """Returns dependency availability for all registered engines."""
        result: Dict[str, bool] = {}
        for engine, manifest in self._manifests.items():
            all_deps_ok = True
            for dep in manifest.dependencies:
                try:
                    importlib.import_module(dep)
                except ImportError:
                    all_deps_ok = False
                    logger.debug("[LF1-REG] dependency '%s' for engine '%s' not importable.", dep, engine)
            result[engine] = all_deps_ok
        return result

    def metrics(self) -> Dict[str, Any]:
        """Returns registry statistics."""
        return {
            "total_registered": len(self._manifests),
            "total_loaded":     len(self._instances),
            "total_active":     sum(1 for v in self._active.values() if v),
            "states":           {k: v.value for k, v in self._states.items()},
        }
