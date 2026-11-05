"""
SERVER.control_plane.feature_flags - Dynamic Feature Flags Manager
Controls feature switches dynamically (Digital Twin, Chaos, Learning, Voice, Auto-remediation, Tool execution).
"""
from enum import Enum
from typing import Dict, Any, Optional

class FeatureFlag(str, Enum):
    DIGITAL_TWIN = "digital_twin"
    CHAOS_ENGINEERING = "chaos_engineering"
    CONTINUOUS_LEARNING = "continuous_learning"
    AUTO_REMEDIATION = "auto_remediation"
    AUTO_APPROVAL = "auto_approval"
    VOICE_INTERFACE = "voice_interface"
    TOOL_EXECUTION = "tool_execution"

class FeatureFlagsManager:
    """Dynamic Feature Flag Manager with safe default fallbacks."""
    def __init__(self):
        self._flags: Dict[str, bool] = {
            FeatureFlag.DIGITAL_TWIN.value: True,
            FeatureFlag.CHAOS_ENGINEERING.value: False,  # Disabled by default
            FeatureFlag.CONTINUOUS_LEARNING.value: True,
            FeatureFlag.AUTO_REMEDIATION.value: False,   # Requires HITL by default
            FeatureFlag.AUTO_APPROVAL.value: False,
            FeatureFlag.VOICE_INTERFACE.value: True,
            FeatureFlag.TOOL_EXECUTION.value: True,
        }

    def is_enabled(self, flag: FeatureFlag) -> bool:
        return self._flags.get(flag.value, False)

    def set_flag(self, flag: FeatureFlag, enabled: bool) -> None:
        self._flags[flag.value] = enabled

    def get_all_flags(self) -> Dict[str, bool]:
        return dict(self._flags)
