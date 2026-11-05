"""
SERVER.compatibility - Legacy Events Adapter Bridge
Translates legacy dictionary events to DomainEventContract schemas.
"""
from typing import Dict, Any
from SERVER.contracts.events import DomainEventContract, IncidentCreatedEvent

class LegacyEventBridge:
    """Translates raw dictionary payloads from NATS or webhooks into versioned DomainEventContracts."""

    @staticmethod
    def dict_to_event(raw_event: Dict[str, Any]) -> DomainEventContract:
        event_id = str(raw_event.get("event_id", raw_event.get("id", "EVT-LEGACY")))
        event_type = str(raw_event.get("event_type", raw_event.get("type", "IncidentCreated")))
        timestamp = str(raw_event.get("timestamp", "2026-08-05T00:00:00Z"))
        payload = raw_event.get("payload", raw_event)

        return IncidentCreatedEvent(
            event_id=event_id,
            event_type=event_type,
            timestamp=timestamp,
            payload=payload,
        )
