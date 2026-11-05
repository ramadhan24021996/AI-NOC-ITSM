"""
SERVER.control_plane.emergency_mode - Emergency Mode & System Kill Switch
Provides emergency kill switch to immediately freeze non-critical actions during incident storms.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger("control_plane.emergency")

class EmergencyManager:
    """Manages emergency mode kill switches and graceful lockdown."""
    def __init__(self):
        self._emergency_active: bool = False
        self._emergency_reason: str = ""

    def activate_emergency(self, reason: str) -> None:
        self._emergency_active = True
        self._emergency_reason = reason
        logger.critical(f"[KILL_SWITCH_ACTIVATED] Reason: {reason}")

    def deactivate_emergency(self) -> None:
        self._emergency_active = False
        self._emergency_reason = ""
        logger.info("[KILL_SWITCH_DEACTIVATED] System restored to normal operation.")

    @property
    def is_emergency_active(self) -> bool:
        return self._emergency_active

    @property
    def emergency_reason(self) -> str:
        return self._emergency_reason
