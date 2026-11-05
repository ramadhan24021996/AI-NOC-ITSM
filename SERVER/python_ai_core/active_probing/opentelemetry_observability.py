"""
OpenTelemetry Observability Module
Provides OpenTelemetry-compliant tracing metadata for probe executions:
trace_id, span_id, correlation_id, investigation_id, incident_id.
"""

from dataclasses import dataclass, field
from typing import Dict, Any, Optional
import uuid
from datetime import datetime, timezone


@dataclass
class OTelProbeSpan:
    trace_id: str
    span_id: str
    correlation_id: str
    investigation_id: str
    incident_id: str
    probe_id: str
    probe_name: str
    asset_id: str
    start_time: str
    end_time: Optional[str] = None
    status_code: str = "UNSET"    # "OK", "ERROR", "UNSET"
    attributes: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "span_id": self.span_id,
            "correlation_id": self.correlation_id,
            "investigation_id": self.investigation_id,
            "incident_id": self.incident_id,
            "probe_id": self.probe_id,
            "probe_name": self.probe_name,
            "asset_id": self.asset_id,
            "start_time": self.start_time,
            "end_time": self.end_time,
            "status_code": self.status_code,
            "attributes": self.attributes
        }


class OpenTelemetryObservability:
    """Manages OpenTelemetry tracing, span creation, and correlation ID generation."""

    def __init__(self, incident_id: str):
        self.incident_id = incident_id
        self.investigation_id = f"INV-{uuid.uuid4().hex[:8]}"
        self.trace_id = uuid.uuid4().hex
        self.spans: Dict[str, OTelProbeSpan] = {}

    def start_probe_span(self, probe_id: str, probe_name: str, asset_id: str) -> OTelProbeSpan:
        span_id = uuid.uuid4().hex[:16]
        correlation_id = f"CORR-{uuid.uuid4().hex[:8]}"
        now_iso = datetime.now(timezone.utc).isoformat()

        span = OTelProbeSpan(
            trace_id=self.trace_id,
            span_id=span_id,
            correlation_id=correlation_id,
            investigation_id=self.investigation_id,
            incident_id=self.incident_id,
            probe_id=probe_id,
            probe_name=probe_name,
            asset_id=asset_id,
            start_time=now_iso,
            attributes={"service.name": "noc-probe-engine", "component": "active_probing"}
        )
        self.spans[span_id] = span
        return span

    def end_probe_span(self, span_id: str, status_code: str, attributes: Optional[Dict[str, Any]] = None):
        span = self.spans.get(span_id)
        if span:
            span.end_time = datetime.now(timezone.utc).isoformat()
            span.status_code = status_code
            if attributes:
                span.attributes.update(attributes)

    def get_trace_summary(self) -> Dict[str, Any]:
        return {
            "trace_id": self.trace_id,
            "investigation_id": self.investigation_id,
            "incident_id": self.incident_id,
            "total_spans": len(self.spans),
            "spans": [s.to_dict() for s in self.spans.values()]
        }
