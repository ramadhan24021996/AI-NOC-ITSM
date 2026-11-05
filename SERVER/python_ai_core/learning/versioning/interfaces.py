from abc import ABC, abstractmethod

class IVersionController(ABC):
    @abstractmethod
    def check_compatibility(self, version_a: str, version_b: str) -> bool:
        raise NotImplementedError("LF-1 Framework: check_compatibility not implemented")

    @abstractmethod
    def trigger_migration_hook(self, target_version: str) -> bool:
        raise NotImplementedError("LF-1 Framework: trigger_migration_hook not implemented")

    @abstractmethod
    def generate_rollback_metadata(self, current_version: str) -> dict:
        raise NotImplementedError("LF-1 Framework: generate_rollback_metadata not implemented")


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 6.2
# ══════════════════════════════════════════════════════════════════════════════
import logging
from datetime import datetime, timezone

_vlog = logging.getLogger("lf1.versioning")

class SemanticVersionController(IVersionController):
    """
    Semantic versioning controller (semver: MAJOR.MINOR.PATCH).
    Tracks migration hooks and generates rollback metadata snapshots.
    """

    def _parse(self, v: str):
        try:
            parts = str(v).strip().lstrip("v").split(".")
            return tuple(int(x) for x in parts[:3])
        except Exception:
            return (0, 0, 0)

    def check_compatibility(self, version_a: str, version_b: str) -> bool:
        """Compatible if MAJOR version matches."""
        a, b = self._parse(version_a), self._parse(version_b)
        compatible = a[0] == b[0]
        _vlog.info("[VersionController] Compatibility %s ↔ %s: %s", version_a, version_b, compatible)
        return compatible

    def trigger_migration_hook(self, target_version: str) -> bool:
        """Log migration event — concrete DB schema migration plugged in here."""
        _vlog.info("[VersionController] Migration hook triggered → target=%s at %s",
                   target_version, datetime.now(timezone.utc).isoformat())
        return True

    def generate_rollback_metadata(self, current_version: str) -> dict:
        major, minor, patch = self._parse(current_version)
        rollback_ver = f"{major}.{minor}.{max(0, patch - 1)}"
        return {
            "current_version": current_version,
            "rollback_version": rollback_ver,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "strategy": "PATCH_ROLLBACK" if patch > 0 else "MINOR_ROLLBACK",
            "safe": patch > 0,
        }
