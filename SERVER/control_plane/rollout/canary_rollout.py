"""
SERVER.control_plane.rollout - Canary Rollout Manager
Manages canary rollout percentage routing for AI model candidates.
"""
import random
from typing import Dict, Any

class CanaryRolloutManager:
    """Manages progressive canary deployment routing."""
    def __init__(self, canary_percentage: float = 10.0):
        self.canary_percentage = max(0.0, min(100.0, canary_percentage))

    def set_percentage(self, percentage: float) -> None:
        self.canary_percentage = max(0.0, min(100.0, percentage))

    def should_route_to_canary(self, session_id: str) -> bool:
        # Deterministic hash routing based on session_id
        hashed = hash(session_id) % 100
        return hashed < self.canary_percentage
