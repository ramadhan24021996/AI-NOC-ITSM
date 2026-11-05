"""
SERVER.python_ai_core.cognition.client_snapshot_assembler
=========================================================
Assembles raw multi-collector PC Client telemetry (EventLogs, Top 5 Processes, 
CPU/RAM metrics, Wi-Fi BSSID/signal, Spooler status, and Browser state) 
into a unified, production-ready ClientDiagnosticSnapshotDTO.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger("CLIENT_SNAPSHOT_ASSEMBLER")


@dataclass
class ClientDiagnosticSnapshotDTO:
    """Unified Diagnostic Snapshot DTO for PC Client Incidents."""
    device_id: str
    target_os: str = "WINDOWS"             # WINDOWS | LINUX | MACOS
    cpu_usage_pct: float = 0.0
    ram_usage_pct: float = 0.0
    disk_free_gb: float = 0.0
    wifi_ssid: str = ""
    wifi_signal_pct: int = 100
    top_processes: List[Dict[str, Any]] = field(default_factory=list)
    recent_event_logs: List[Dict[str, Any]] = field(default_factory=list)
    spooler_queue_count: int = 0
    spooler_status: str = "RUNNING"        # RUNNING | STOPPED | HANG
    browser_active_tabs: int = 0
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "device_id": self.device_id,
            "target_os": self.target_os,
            "cpu_usage_pct": round(self.cpu_usage_pct, 2),
            "ram_usage_pct": round(self.ram_usage_pct, 2),
            "disk_free_gb": round(self.disk_free_gb, 2),
            "wifi_ssid": self.wifi_ssid,
            "wifi_signal_pct": self.wifi_signal_pct,
            "top_processes": self.top_processes,
            "recent_event_logs": self.recent_event_logs,
            "spooler_queue_count": self.spooler_queue_count,
            "spooler_status": self.spooler_status,
            "browser_active_tabs": self.browser_active_tabs,
            "timestamp": self.timestamp,
        }


def safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val: Any, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


class ClientDiagnosticSnapshotAssembler:
    """Assembles raw telemetry json into structured ClientDiagnosticSnapshotDTO."""

    @classmethod
    def assemble(cls, device_id: str, raw_telemetry: Dict[str, Any]) -> ClientDiagnosticSnapshotDTO:
        """Parses multi-collector json data safely with zero-crash fallbacks."""
        if not raw_telemetry:
            return ClientDiagnosticSnapshotDTO(device_id=device_id)

        target_os = str(raw_telemetry.get("os") or raw_telemetry.get("target_os") or "WINDOWS").upper()
        
        raw_cpu = raw_telemetry.get("cpu_usage_pct") if raw_telemetry.get("cpu_usage_pct") is not None else raw_telemetry.get("cpu", 0.0)
        cpu_usage = safe_float(raw_cpu, 0.0)

        raw_ram = raw_telemetry.get("ram_usage_pct") if raw_telemetry.get("ram_usage_pct") is not None else raw_telemetry.get("memory", 0.0)
        ram_usage = safe_float(raw_ram, 0.0)

        raw_disk = raw_telemetry.get("disk_free_gb") if raw_telemetry.get("disk_free_gb") is not None else raw_telemetry.get("disk_free", 50.0)
        disk_free = safe_float(raw_disk, 50.0)

        # Process Tree
        procs = raw_telemetry.get("top_processes") or raw_telemetry.get("processes") or []
        if not isinstance(procs, list):
            procs = []

        # Event logs
        logs = raw_telemetry.get("recent_event_logs") or raw_telemetry.get("event_logs") or []
        if not isinstance(logs, list):
            logs = []

        # Wi-Fi
        wifi_info = raw_telemetry.get("wifi") or {}
        wifi_ssid = str(wifi_info.get("ssid") or raw_telemetry.get("wifi_ssid") or "")
        wifi_signal = safe_int(wifi_info.get("signal_pct") or raw_telemetry.get("wifi_signal_pct"), 100)

        # Spooler
        spooler_info = raw_telemetry.get("spooler") or {}
        spooler_count = safe_int(spooler_info.get("queue_count") or raw_telemetry.get("spooler_queue_count"), 0)
        spooler_status = str(spooler_info.get("status") or raw_telemetry.get("spooler_status") or "RUNNING").upper()

        # Browser
        browser_info = raw_telemetry.get("browser") or {}
        active_tabs = safe_int(browser_info.get("active_tabs") or raw_telemetry.get("browser_active_tabs"), 0)

        snapshot = ClientDiagnosticSnapshotDTO(
            device_id=device_id,
            target_os=target_os,
            cpu_usage_pct=cpu_usage,
            ram_usage_pct=ram_usage,
            disk_free_gb=disk_free,
            wifi_ssid=wifi_ssid,
            wifi_signal_pct=wifi_signal,
            top_processes=procs[:5],
            recent_event_logs=logs[:10],
            spooler_queue_count=spooler_count,
            spooler_status=spooler_status,
            browser_active_tabs=active_tabs,
        )

        logger.info(f"[SNAPSHOT_ASSEMBLER] Assembled DTO for device={device_id} | CPU={cpu_usage}% | RAM={ram_usage}%")
        return snapshot
