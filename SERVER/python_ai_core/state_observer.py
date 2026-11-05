"""
Shim module for backward compatibility.
Redirects imports of state_observer to services.state_observer.
"""
from services.state_observer import (
    IncidentEventBus,
    TelemetryObserver,
    AuditObserver,
    incident_event_bus,
)

__all__ = [
    "IncidentEventBus",
    "TelemetryObserver",
    "AuditObserver",
    "incident_event_bus",
]
