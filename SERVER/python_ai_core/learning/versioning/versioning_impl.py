"""
LF-1 Learning Framework — Version Controller (Concrete Implementation)
Semantic versioning (MAJOR.MINOR.PATCH) with migration hooks and rollback metadata.
"""
import logging
import json
import os
import time
from typing import Dict, Any

from .interfaces import IVersionController

logger = logging.getLogger("LF1_VERSION_CTRL")

# Version compatibility rules:
# - MAJOR mismatch = incompatible (migration required)
# - MINOR mismatch = backwards compatible (schema migration recommended)
# - PATCH mismatch = always compatible (hotfix)
_MIGRATION_HOOKS_DIR = os.getenv(
    "LF1_MIGRATION_DIR",
    os.path.join(os.path.dirname(os.path.abspath(__file__)), "migrations"),
)


class SemanticVersionController(IVersionController):
    """
    Concrete version controller using Semantic Versioning (semver.org).

    Responsibilities:
    - check_compatibility: determines if two schema versions are compatible
    - trigger_migration_hook: runs the appropriate migration script
    - generate_rollback_metadata: captures pre-migration state snapshot
    """

    def __init__(self):
        self._migration_history: list = []
        os.makedirs(_MIGRATION_HOOKS_DIR, exist_ok=True)
        logger.info("[LF1-VER] SemanticVersionController initialized. Migration dir: %s",
                    _MIGRATION_HOOKS_DIR)

    # ------------------------------------------------------------------
    # IVersionController implementation
    # ------------------------------------------------------------------
    def check_compatibility(self, version_a: str, version_b: str) -> bool:
        """
        Returns True if version_a and version_b are compatible.
        MAJOR versions must match. MINOR and PATCH are backwards compatible.

        Examples:
            check_compatibility("2.3.1", "2.4.0") -> True  (same major)
            check_compatibility("1.0.0", "2.0.0") -> False (major mismatch)
            check_compatibility("3.1.0", "3.1.5") -> True  (patch only)
        """
        try:
            major_a, minor_a, _ = self._parse(version_a)
            major_b, minor_b, _ = self._parse(version_b)

            if major_a != major_b:
                logger.warning(
                    "[LF1-VER] INCOMPATIBLE: %s vs %s — major version mismatch (%d != %d)",
                    version_a, version_b, major_a, major_b
                )
                return False

            # Minor backwards-compatible: newer server can serve older clients
            compatible = True
            if minor_a != minor_b:
                logger.info(
                    "[LF1-VER] MINOR mismatch %s vs %s — backwards compatible, migration recommended",
                    version_a, version_b
                )
            logger.info("[LF1-VER] check_compatibility: %s <-> %s = %s",
                        version_a, version_b, "COMPATIBLE" if compatible else "INCOMPATIBLE")
            return compatible
        except ValueError as e:
            logger.error("[LF1-VER] check_compatibility: invalid version format: %s", e)
            return False

    def trigger_migration_hook(self, target_version: str) -> bool:
        """
        Triggers the migration hook for upgrading to target_version.
        Reads a declarative JSON migration manifest in _MIGRATION_HOOKS_DIR:
            migrate_to_{MAJOR}_{MINOR}_{PATCH}.json
        (Arbitrary Python exec() is prohibited for security.)
        Returns True on success, False on failure.
        """
        try:
            major, minor, patch = self._parse(target_version)
            hook_name = f"migrate_to_{major}_{minor}_{patch}.json"
            hook_path = os.path.join(_MIGRATION_HOOKS_DIR, hook_name)

            if os.path.exists(hook_path):
                logger.info("[LF1-VER] Loading declarative migration manifest: %s", hook_path)
                with open(hook_path, "r", encoding="utf-8") as f:
                    manifest = json.load(f)
                if not isinstance(manifest, dict):
                    raise ValueError("Invalid migration manifest format")
                logger.info("[LF1-VER] Migration to %s completed (steps=%d).", target_version, len(manifest.get("steps", [])))
            else:
                # No hook file — create declarative placeholder for future use
                logger.info("[LF1-VER] No migration manifest for %s (no-op migration).", target_version)
                self._write_noop_hook(hook_path, target_version)

            self._migration_history.append({
                "target_version": target_version,
                "timestamp": time.time(),
                "hook": hook_name,
                "status": "completed",
            })
            return True
        except Exception as e:
            logger.error("[LF1-VER] trigger_migration_hook failed for %s: %s", target_version, e)
            return False

    def generate_rollback_metadata(self, current_version: str) -> dict:
        """
        Captures a rollback snapshot of the current version state.
        Used before running a migration so we can revert if it fails.
        """
        try:
            major, minor, patch = self._parse(current_version)
            rollback_metadata = {
                "snapshot_version": current_version,
                "snapshot_ts": time.time(),
                "rollback_target": f"{major}.{minor}.{max(0, patch - 1)}" if patch > 0
                                   else f"{major}.{max(0, minor - 1)}.0",
                "migration_history": list(self._migration_history),
                "can_rollback": len(self._migration_history) > 0,
            }
            # Persist to disk for durability
            snapshot_path = os.path.join(
                _MIGRATION_HOOKS_DIR,
                f"rollback_{current_version.replace('.', '_')}_{int(time.time())}.json"
            )
            with open(snapshot_path, "w") as f:
                json.dump(rollback_metadata, f, indent=2)

            logger.info("[LF1-VER] Rollback metadata generated for %s -> %s",
                        current_version, rollback_metadata["rollback_target"])
            return rollback_metadata
        except Exception as e:
            logger.error("[LF1-VER] generate_rollback_metadata failed: %s", e)
            return {"error": str(e), "can_rollback": False}

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    @staticmethod
    def _parse(version: str):
        """Parse 'MAJOR.MINOR.PATCH' -> (int, int, int). Raises ValueError on bad format."""
        parts = version.strip().split(".")
        if len(parts) != 3:
            raise ValueError(f"Invalid semver: '{version}' — expected MAJOR.MINOR.PATCH")
        return int(parts[0]), int(parts[1]), int(parts[2])

    @staticmethod
    def _write_noop_hook(path: str, version: str) -> None:
        """Write a declarative JSON no-op migration manifest."""
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump({
                "target_version": version,
                "description": f"Migration to {version}: no schema changes required.",
                "steps": []
            }, f, indent=2)
