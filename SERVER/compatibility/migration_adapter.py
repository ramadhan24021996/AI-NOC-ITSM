"""
SERVER.compatibility - Migration Adapter
Unified migration adapter managing state and data migration between legacy python_ai_core and new monorepo domains.
"""
from typing import Dict, Any, List
from SERVER.compatibility.legacy_models import LegacyModelAdapter
from SERVER.compatibility.legacy_events import LegacyEventBridge
from SERVER.compatibility.legacy_api import LegacyAPIBridge

class MigrationAdapter:
    """Central migration adapter orchestrating data structure transformations."""
    def __init__(self):
        self.models = LegacyModelAdapter()
        self.events = LegacyEventBridge()
        self.api = LegacyAPIBridge()

    def is_migration_active() -> bool:
        """Returns True if legacy migration bridge is currently active."""
        return True
