"""
SERVER.compatibility Domain Package
Temporary migration bridge between legacy python_ai_core and clean monorepo domains.
Can be safely pruned once full migration completes.
"""
from SERVER.compatibility.legacy_models import LegacyModelAdapter
from SERVER.compatibility.legacy_repositories import LegacyRepositoryBridge
from SERVER.compatibility.legacy_events import LegacyEventBridge
from SERVER.compatibility.legacy_api import LegacyAPIBridge
from SERVER.compatibility.migration_adapter import MigrationAdapter

__all__ = [
    "LegacyModelAdapter", "LegacyRepositoryBridge",
    "LegacyEventBridge", "LegacyAPIBridge", "MigrationAdapter"
]
