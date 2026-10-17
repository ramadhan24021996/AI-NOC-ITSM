"""
SERVER.jarvis.avatar - Avatar State Stream Manager
Manages UI avatar visual expression state stream (listening, thinking, speaking, idle).
"""
from enum import Enum
from typing import Dict, Any

class AvatarState(str, Enum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"
    ERROR = "error"

class AvatarStateManager:
    """Manages visual avatar expression states for UI rendering."""
    def __init__(self, initial_state: AvatarState = AvatarState.IDLE):
        self._current_state = initial_state

    def set_state(self, state: AvatarState) -> None:
        self._current_state = state

    @property
    def current_state(self) -> AvatarState:
        return self._current_state

    def get_state_payload(self) -> Dict[str, Any]:
        return {
            "avatar_state": self._current_state.value,
            "animation_trigger": f"anim_{self._current_state.value}",
        }
