"""
Enterprise World Model Engine Module
Unified World Model Representation:
Physical Topology + Logical Topology + Business Services + Affected Users + Policies + Cloud + Current Health + Predicted Future State.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from datetime import datetime, timezone


@dataclass
class EnterpriseWorldModelState:
    timestamp: str
    physical_assets_count: int
    logical_services_count: int
    affected_users_count: int
    active_incidents_count: int
    overall_health_pct: float
    predicted_future_health_pct: float
    summary: str


class EnterpriseWorldModel:
    """Manages the real-time unified Enterprise World Model state."""

    def __init__(self):
        self.physical_assets = 1450
        self.logical_services = 85
        self.active_incidents: Dict[str, Any] = {}
        self.current_health_pct = 99.8

    def update_world_state(
        self,
        incident_id: Optional[str] = None,
        health_delta: float = 0.0,
        affected_users: int = 0
    ) -> EnterpriseWorldModelState:

        ts = datetime.now(timezone.utc).isoformat()
        if incident_id:
            self.active_incidents[incident_id] = {"timestamp": ts, "affected_users": affected_users}

        self.current_health_pct = max(min(self.current_health_pct + health_delta, 100.0), 0.0)
        predicted_future = max(self.current_health_pct - 0.2, 0.0) if self.active_incidents else 100.0

        summary = (
            f"Enterprise World Model State: Health {self.current_health_pct}% | "
            f"Active Incidents={len(self.active_incidents)} | Physical Assets={self.physical_assets} | "
            f"Predicted Future Health={predicted_future}%"
        )

        return EnterpriseWorldModelState(
            timestamp=ts,
            physical_assets_count=self.physical_assets,
            logical_services_count=self.logical_services,
            affected_users_count=sum(i.get("affected_users", 0) for i in self.active_incidents.values()),
            active_incidents_count=len(self.active_incidents),
            overall_health_pct=self.current_health_pct,
            predicted_future_health_pct=predicted_future,
            summary=summary
        )
