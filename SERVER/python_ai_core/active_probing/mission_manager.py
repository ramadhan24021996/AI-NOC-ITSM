"""
Mission Manager Module
Maintains long-term enterprise mission objectives (e.g., 'Maintain POS Terminal Availability >= 99.99%'):
Evaluates all active probing and remediation decisions against high-level business missions.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class EnterpriseMission:
    mission_id: str
    target_service: str
    target_availability_pct: float
    current_availability_pct: float
    mission_status: str   # "MET", "AT_RISK", "VIOLATED"


class MissionManager:
    """Manages enterprise operational missions and aligns AI decisions to business targets."""

    def __init__(self):
        self.missions: Dict[str, EnterpriseMission] = {}
        self._initialize_default_missions()

    def _initialize_default_missions(self):
        self.missions["MISSION-POS-01"] = EnterpriseMission(
            mission_id="MISSION-POS-01",
            target_service="POS Retail Payment Engine",
            target_availability_pct=99.99,
            current_availability_pct=99.995,
            mission_status="MET"
        )
        self.missions["MISSION-BRANCH-01"] = EnterpriseMission(
            mission_id="MISSION-BRANCH-01",
            target_service="Branch Office Core VPN",
            target_availability_pct=99.90,
            current_availability_pct=99.95,
            mission_status="MET"
        )

    def evaluate_mission_alignment(
        self,
        mission_id: str,
        proposed_action_impact_pct: float
    ) -> tuple[bool, str]:

        mission = self.missions.get(mission_id)
        if not mission:
            return True, "Mission ID not found; action permitted under standard SLA"

        new_avail = mission.current_availability_pct - proposed_action_impact_pct
        if new_avail < mission.target_availability_pct:
            return False, f"Action REJECTED by Mission Manager: Would degrade '{mission.target_service}' availability below {mission.target_availability_pct}% target."

        return True, f"Action ALIGNED with Mission '{mission.target_service}' (Projected {round(new_avail, 2)}% >= {mission.target_availability_pct}% target)."
