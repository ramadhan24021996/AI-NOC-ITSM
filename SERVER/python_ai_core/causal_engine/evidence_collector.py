"""
Unified Evidence Collector Module
Aggregates 12 multi-modal evidence streams into a single UnifiedEvidence payload object.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import json


@dataclass
class UnifiedEvidence:
    incident_id: str
    device_id: str
    timestamp: str
    telemetry: Dict[str, Any] = field(default_factory=dict)
    netdata_metrics: Dict[str, Any] = field(default_factory=dict)
    event_viewer: List[Dict[str, Any]] = field(default_factory=list)
    browser_console: List[Dict[str, Any]] = field(default_factory=list)
    syslog_events: List[Dict[str, Any]] = field(default_factory=list)
    docker_stats: Dict[str, Any] = field(default_factory=dict)
    process_snapshot: List[Dict[str, Any]] = field(default_factory=list)
    packet_capture: Dict[str, Any] = field(default_factory=dict)
    snmp_oids: Dict[str, Any] = field(default_factory=dict)
    config_snapshot: Dict[str, Any] = field(default_factory=dict)
    registry_keys: Dict[str, Any] = field(default_factory=dict)
    historical_incidents: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "device_id": self.device_id,
            "timestamp": self.timestamp,
            "telemetry": self.telemetry,
            "netdata_metrics": self.netdata_metrics,
            "event_viewer": self.event_viewer,
            "browser_console": self.browser_console,
            "syslog_events": self.syslog_events,
            "docker_stats": self.docker_stats,
            "process_snapshot": self.process_snapshot,
            "packet_capture": self.packet_capture,
            "snmp_oids": self.snmp_oids,
            "config_snapshot": self.config_snapshot,
            "registry_keys": self.registry_keys,
            "historical_incidents": self.historical_incidents
        }


class EvidenceCollector:
    def collect_all_evidence(self, raw_input: Dict[str, Any]) -> UnifiedEvidence:
        """
        Gathers and unifies all 12 evidence streams from raw telemetry payload.
        """
        device_id = raw_input.get("device_id") or raw_input.get("host") or "UNKNOWN_DEVICE"
        incident_id = raw_input.get("incident_id") or f"INC-EVD-{device_id}"
        ts = raw_input.get("timestamp") or datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        return UnifiedEvidence(
            incident_id=incident_id,
            device_id=device_id,
            timestamp=ts,
            telemetry=raw_input.get("telemetry") or raw_input.get("metrics") or {},
            netdata_metrics=raw_input.get("netdata") or {},
            event_viewer=raw_input.get("event_viewer") or raw_input.get("windows_events") or [],
            browser_console=raw_input.get("browser_console") or [],
            syslog_events=raw_input.get("syslog") or [],
            docker_stats=raw_input.get("docker") or {},
            process_snapshot=raw_input.get("processes") or [],
            packet_capture=raw_input.get("pcap") or {},
            snmp_oids=raw_input.get("snmp") or {},
            config_snapshot=raw_input.get("config") or {},
            registry_keys=raw_input.get("registry") or {},
            historical_incidents=raw_input.get("history") or []
        )
