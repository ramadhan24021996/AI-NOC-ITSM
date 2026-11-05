"""
Phase 4.0-B Causal Event Envelope (control_plane/event_envelope.py)

Standardized event envelope structure for Control Plane Event Orchestrator.
Enforces:
- Unique event identification
- Idempotency key derivation via SHA-256: SHA256(source + event_id + incident_id + schema_version)
- Correlation & trace tracking
- Schema versioning and payload integrity hashing
"""

import dataclasses
import hashlib
import json
import time
from typing import Dict, Any, Optional


@dataclasses.dataclass
class CausalEventEnvelope:
    event_id: str
    incident_id: str
    trace_id: str
    source: str
    event_type: str
    occurred_at: str
    received_at: str
    decision_deadline: str
    payload: Dict[str, Any]
    payload_hash: str = ""
    correlation_id: Optional[str] = None
    schema_version: str = "1.0.0"
    attempt_count: int = 0
    claimed_at: Optional[str] = None
    claimed_by: Optional[str] = None
    claim_token: Optional[str] = None

    def __post_init__(self):
        if not self.payload_hash and self.payload:
            payload_str = json.dumps(self.payload, sort_keys=True)
            self.payload_hash = hashlib.sha256(payload_str.encode("utf-8")).hexdigest()
        if not self.correlation_id:
            self.correlation_id = f"CORR-{self.incident_id}-{self.event_id}"

    def calculate_idempotency_key(self) -> str:
        """Derives explicit idempotency key: SHA256(source + event_id + incident_id + schema_version)"""
        raw = f"{self.source}:{self.event_id}:{self.incident_id}:{self.schema_version}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        d = dataclasses.asdict(self)
        d["idempotency_key"] = self.calculate_idempotency_key()
        return d

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "CausalEventEnvelope":
        data_copy = dict(data)
        data_copy.pop("idempotency_key", None)
        return cls(**data_copy)
