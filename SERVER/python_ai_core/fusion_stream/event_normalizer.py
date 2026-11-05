"""
Event Normalizer Module
Converts multi-modal raw telemetry logs from diverse sources into a unified, standardized schema.
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from enum import Enum
from typing import Dict, Any, Optional
import hashlib
import json


class ModalityType(str, Enum):
    NETWORK = "NETWORK"
    HARDWARE = "HARDWARE"
    OS = "OS"
    BROWSER = "BROWSER"
    APPLICATION = "APPLICATION"
    USER = "USER"
    SECURITY = "SECURITY"


class SeverityLevel(str, Enum):
    INFO = "INFO"
    LOW = "LOW"
    WARNING = "WARNING"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


@dataclass
class NormalizedEvent:
    event_id: str
    timestamp: str          # ISO8601 UTC string (e.g. 2026-08-04T08:03:14Z)
    device_id: str         # Device/Host Identifier
    layer: str             # Architecture Layer (e.g. L0 - L9, OS, L3, L7)
    modality: ModalityType # NETWORK, HARDWARE, OS, BROWSER, APP, USER, SECURITY
    source: str            # DNS, Chrome, EventViewer, Syslog, POS, etc.
    event_code: str        # e.g. DNS_TIMEOUT, ERR_NAME_NOT_RESOLVED, PACKET_LOSS
    severity: SeverityLevel
    duration_ms: int = 0
    metrics: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        d["modality"] = self.modality.value if isinstance(self.modality, Enum) else str(self.modality)
        d["severity"] = self.severity.value if isinstance(self.severity, Enum) else str(self.severity)
        return d

    def generate_hash(self) -> str:
        """Generate deduplication hash key based on device, modality, source, and event_code"""
        raw = f"{self.device_id}:{self.modality}:{self.source}:{self.event_code}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]


class EventNormalizer:
    """Normalizes raw input logs into structured NormalizedEvent objects"""

    @staticmethod
    def normalize(raw_payload: Dict[str, Any]) -> NormalizedEvent:
        # Extract Timestamp
        ts = raw_payload.get("timestamp") or raw_payload.get("time") or raw_payload.get("created_at")
        if not ts:
            ts = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        # Device ID
        device_id = raw_payload.get("device_id") or raw_payload.get("device") or raw_payload.get("host") or raw_payload.get("pc_name") or "UNKNOWN_DEVICE"

        # Modality
        modality_raw = str(raw_payload.get("modality", "")).upper()
        try:
            modality = ModalityType(modality_raw)
        except ValueError:
            modality = EventNormalizer._infer_modality(raw_payload)

        # Severity
        sev_raw = str(raw_payload.get("severity", "")).upper()
        try:
            severity = SeverityLevel(sev_raw)
        except ValueError:
            severity = SeverityLevel.WARNING if "error" in str(raw_payload.get("event", "")).lower() else SeverityLevel.INFO

        # Layer
        layer = str(raw_payload.get("layer") or EventNormalizer._infer_layer(modality))

        # Event Code
        event_code = str(raw_payload.get("event") or raw_payload.get("event_code") or raw_payload.get("message_code") or "GENERIC_EVENT")

        # Source
        source = str(raw_payload.get("source") or raw_payload.get("collector") or "UNKNOWN_SOURCE")

        # Duration
        duration_ms = int(raw_payload.get("duration_ms") or raw_payload.get("latency_ms") or 0)

        # Event ID
        event_id = raw_payload.get("event_id") or f"EVT-{hashlib.md5(f'{ts}-{device_id}-{event_code}'.encode()).hexdigest()[:12]}"

        # Metrics & Metadata
        metrics = raw_payload.get("metrics") or {}
        metadata = raw_payload.get("metadata") or {k: v for k, v in raw_payload.items() if k not in ["timestamp", "device_id", "modality", "source", "event_code", "severity", "metrics"]}

        return NormalizedEvent(
            event_id=event_id,
            timestamp=ts,
            device_id=device_id,
            layer=layer,
            modality=modality,
            source=source,
            event_code=event_code,
            severity=severity,
            duration_ms=duration_ms,
            metrics=metrics,
            metadata=metadata
        )

    @staticmethod
    def _infer_modality(raw: Dict[str, Any]) -> ModalityType:
        src = str(raw.get("source", "")).lower()
        evt = str(raw.get("event", "")).lower()

        if any(x in src or x in evt for x in ["dns", "wifi", "network", "ping", "gateway", "dhcp", "vpn", "rssi"]):
            return ModalityType.NETWORK
        elif any(x in src or x in evt for x in ["cpu", "ram", "memory", "disk", "smart", "temp", "battery", "hardware"]):
            return ModalityType.HARDWARE
        elif any(x in src or x in evt for x in ["eventviewer", "syslog", "kernel", "driver", "service", "os", "registry"]):
            return ModalityType.OS
        elif any(x in src or x in evt for x in ["chrome", "browser", "extension", "v8", "console", "url"]):
            return ModalityType.BROWSER
        elif any(x in src or x in evt for x in ["defender", "antivirus", "firewall", "edr", "usb", "malware", "security"]):
            return ModalityType.SECURITY
        elif any(x in src or x in evt for x in ["mouse", "keyboard", "user", "login", "logout", "idle"]):
            return ModalityType.USER
        else:
            return ModalityType.APPLICATION

    @staticmethod
    def _infer_layer(modality: ModalityType) -> str:
        mapping = {
            ModalityType.USER: "L0",
            ModalityType.BROWSER: "L1",
            ModalityType.APPLICATION: "L1",
            ModalityType.NETWORK: "L3",
            ModalityType.OS: "OS",
            ModalityType.HARDWARE: "L7",
            ModalityType.SECURITY: "L8"
        }
        return mapping.get(modality, "L4")
