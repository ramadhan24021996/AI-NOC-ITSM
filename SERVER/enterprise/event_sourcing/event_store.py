"""
SERVER.enterprise.event_sourcing - Event Store (Immutable Hash-Chained Log)
Provides immutable, verifiable event sourcing log with SHA-256 hash chaining.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import List, Optional, Dict, Any
from datetime import datetime, timezone
import hashlib
import json

@dataclass
class ImmutableEventEntry:
    event_id: str
    event_type: str
    aggregate_id: str
    payload: Dict[str, Any]
    actor_id: str
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    previous_hash: str = "GENESIS"
    event_hash: str = ""

    def compute_hash(self) -> str:
        """Compute SHA-256 hash chaining this entry to its predecessor."""
        content = json.dumps({
            "event_id": self.event_id,
            "event_type": self.event_type,
            "aggregate_id": self.aggregate_id,
            "payload": self.payload,
            "actor_id": self.actor_id,
            "timestamp": self.timestamp,
            "previous_hash": self.previous_hash,
        }, sort_keys=True)
        return hashlib.sha256(content.encode()).hexdigest()

class EventStore(ABC):
    """Abstract event store interface for immutable hash-chained event log."""

    @abstractmethod
    def append(self, entry: ImmutableEventEntry) -> str:
        """Appends entry and returns its computed event_hash."""
        pass

    @abstractmethod
    def load_stream(self, aggregate_id: str) -> List[ImmutableEventEntry]:
        """Returns all events for a given aggregate in chronological order."""
        pass

    @abstractmethod
    def verify_chain(self, aggregate_id: str) -> bool:
        """Verifies hash chain integrity — True if chain is valid and unmodified."""
        pass
