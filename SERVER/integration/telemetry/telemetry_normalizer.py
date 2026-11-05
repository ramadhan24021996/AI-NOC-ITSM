"""
SERVER.integration.telemetry — Normalized Telemetry DTO & Telemetry Normalizer
==================================================================================
Tahap 2.6A — Telemetry Integration

Mengubah data mentah dari Netdata Receiver dan Go Agent PC Client Receiver
menjadi DTO standar yang seragam (NormalizedTelemetryDTO).
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import uuid


@dataclass
class NormalizedTelemetryDTO:
    """Standardized Telemetry DTO across all sources (Netdata & PC Agent)."""
    telemetry_id: str
    source_type: str            # "netdata" | "agent"
    device_id: str
    host_name: str
    metric_category: str        # "cpu" | "memory" | "disk" | "network" | "l1_l7_probe" | "alarm"
    metric_name: str
    value: float
    unit: str
    severity: str               # "low" | "medium" | "high" | "critical"
    timestamp: str              # ISO-8601 UTC
    metadata: Dict[str, Any] = field(default_factory=dict)


class TelemetryNormalizer:
    """Normalizes raw payloads from Netdata and Go Client PC Agent."""

    def normalize_netdata(self, raw_payload: Dict[str, Any]) -> NormalizedTelemetryDTO:
        """Normalizes raw Netdata alarm/metric payload."""
        device_id = raw_payload.get("hostname") or raw_payload.get("chart_id") or ""
        metric_name = raw_payload.get("alarm") or raw_payload.get("chart") or ""
        raw_val = raw_payload.get("value")
        value = float(raw_val) if raw_val is not None else float("nan")
        status = str(raw_payload.get("status", "WARNING")).upper()

        severity = "medium"
        if status in ("CRITICAL", "CLEAR_CRITICAL"):
            severity = "critical"
        elif status in ("WARNING", "WARN"):
            severity = "high"
        elif status in ("CLEAR", "NORMAL", "OK"):
            severity = "low"

        return NormalizedTelemetryDTO(
            telemetry_id=f"TEL-ND-{uuid.uuid4().hex[:8].upper()}",
            source_type="netdata",
            device_id=device_id,
            host_name=device_id,
            metric_category="alarm" if "alarm" in raw_payload else "cpu",
            metric_name=metric_name,
            value=value,
            unit=raw_payload.get("units", "%"),
            severity=severity,
            timestamp=datetime.now(timezone.utc).isoformat(),
            metadata=raw_payload,
        )

    def normalize_agent(self, raw_payload: Dict[str, Any]) -> NormalizedTelemetryDTO:
        """Normalizes raw L1-L7 probe payload from Go Client PC Agent."""
        device_id = raw_payload.get("device_id") or raw_payload.get("hostname") or ""
        l3_net = raw_payload.get("layer_3_network", {})
        l4_trans = raw_payload.get("layer_4_transport", {})
        l7_app = raw_payload.get("layer_5_7_application", {})

        dns_latency = float(l3_net.get("dns_latency_ms", 0.0))
        tcp_retrans = float(l4_trans.get("tcp_retrans_rate", 0.0))
        app_crashes = int(l7_app.get("browser_crashes", 0))

        # Severity decision based on probes
        severity = "low"
        if dns_latency > 150.0 or app_crashes > 5 or tcp_retrans > 0.05:
            severity = "critical"
        elif dns_latency > 50.0 or app_crashes > 0 or tcp_retrans > 0.01:
            severity = "high"
        elif dns_latency > 20.0:
            severity = "medium"

        return NormalizedTelemetryDTO(
            telemetry_id=f"TEL-AG-{uuid.uuid4().hex[:8].upper()}",
            source_type="agent",
            device_id=device_id,
            host_name=device_id,
            metric_category="l1_l7_probe",
            metric_name="agent_l1_l7_health",
            value=dns_latency,
            unit="ms",
            severity=severity,
            timestamp=raw_payload.get("timestamp", datetime.now(timezone.utc).isoformat()),
            metadata=raw_payload,
        )
