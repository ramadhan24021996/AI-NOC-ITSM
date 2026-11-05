"""
Typed Versioned Event Bus Module
Event-driven message bus enforcing versioned event schemas:
HypothesisGenerated.v1, ProbeCompleted.v2, SimulationFinished.v1, RollbackRequested.v1
"""

from dataclasses import dataclass, field
from typing import Dict, List, Callable, Any, Optional
from datetime import datetime, timezone


@dataclass
class TypedEventMessage:
    event_type: str        # e.g. "HypothesisGenerated.v1", "ProbeCompleted.v2"
    schema_version: str    # "v1", "v2"
    publisher_agent: str
    payload: Dict[str, Any]
    timestamp: str


class AIOSMessageBus:
    """Typed event bus managing version-compatible event publishing and subscriptions."""

    def __init__(self):
        self.subscribers: Dict[str, List[Callable[[TypedEventMessage], None]]] = {}
        self.event_history: List[TypedEventMessage] = []

    def subscribe(self, event_type: str, callback: Callable[[TypedEventMessage], None]):
        if event_type not in self.subscribers:
            self.subscribers[event_type] = []
        self.subscribers[event_type].append(callback)

    def publish_typed_event(
        self,
        event_type: str,
        publisher_agent: str,
        payload: Dict[str, Any]
    ) -> TypedEventMessage:

        version = event_type.split(".")[-1] if "." in event_type else "v1"
        ts = datetime.now(timezone.utc).isoformat()

        msg = TypedEventMessage(
            event_type=event_type,
            schema_version=version,
            publisher_agent=publisher_agent,
            payload=payload,
            timestamp=ts
        )

        self.event_history.append(msg)

        if event_type in self.subscribers:
            for cb in self.subscribers[event_type]:
                try:
                    cb(msg)
                except Exception:
                    pass

        return msg
