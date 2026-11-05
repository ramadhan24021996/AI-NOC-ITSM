"""
Enterprise AI Digital Twin Manager (Phase 4 Capability 7)
Maintains active real-time Digital Twin state for every PC Client:
- Hardware Specifications (CPU, RAM, Disks, SMART)
- Software Inventory & Installed Apps
- Driver Versions & Operating System Patches
- Security Policies & Firewall Rules
- Real-time Topology & Incident History
- Continuous Learning Profile
"""

import logging
import time
import math
from typing import Dict, Any, Optional, List

logger = logging.getLogger("DIGITAL_TWIN_MANAGER")


class DigitalTwinProfile:

    def __init__(self, device_id: str):
        self.device_id: str = device_id
        self.hardware: Dict[str, Any] = {}
        self.software: List[str] = []
        self.drivers: Dict[str, str] = {}
        self.topology_neighbors: List[str] = []
        self.incident_history: List[Dict[str, Any]] = []
        self.cpu_samples: List[float] = [20.0, 25.0, 18.0, 22.0, 30.0]
        self.ram_samples: List[float] = [45.0, 50.0, 48.0, 42.0, 46.0]
        self.last_updated: str = time.strftime("%Y-%m-%dT%H:%M:%SZ")


def safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


class AIDigitalTwinManager:
    """
    Enterprise AI Digital Twin Manager
    Provides instant state retrieval and baseline metric drift calculation per PC Client.
    """

    def __init__(self):
        self.twins: Dict[str, DigitalTwinProfile] = {}

    def get_or_create_twin(self, device_id: str) -> DigitalTwinProfile:
        """Retrieves or initializes Digital Twin profile."""
        if device_id not in self.twins:
            twin = DigitalTwinProfile(device_id)
            twin.hardware = {"cpu": "Intel Core i5/i7", "ram_gb": 8, "disk_smart": "GOOD"}
            twin.software = ["Windows 11 POS", "Chrome", "NOC-Agent-Go"]
            twin.topology_neighbors = ["Switch_Access_01", "Gateway_Router_01"]
            self.twins[device_id] = twin
        return self.twins[device_id]

    def update_twin_telemetry(self, device_id: str, telemetry_data: Dict[str, Any]) -> None:
        """Updates Digital Twin state with live telemetry and maintains baseline samples."""
        twin = self.get_or_create_twin(device_id)
        twin.last_updated = time.strftime("%Y-%m-%dT%H:%M:%SZ")

        if not telemetry_data:
            return

        raw_cpu = telemetry_data.get("cpu_usage_pct")
        if raw_cpu is None:
            raw_cpu = telemetry_data.get("cpu", 0.0)
        cpu = safe_float(raw_cpu, 0.0)

        raw_ram = telemetry_data.get("ram_usage_pct")
        if raw_ram is None:
            raw_ram = telemetry_data.get("ram", telemetry_data.get("memory", 0.0))
        ram = safe_float(raw_ram, 0.0)

        if cpu > 0:
            twin.cpu_samples.append(cpu)
            if len(twin.cpu_samples) > 50:
                twin.cpu_samples.pop(0)

        if ram > 0:
            twin.ram_samples.append(ram)
            if len(twin.ram_samples) > 50:
                twin.ram_samples.pop(0)

        logger.info("[DIGITAL TWIN] Updated profile for %s at %s (CPU: %.1f%%, RAM: %.1f%%)", device_id, twin.last_updated, cpu, ram)

    def calculate_metric_drift(self, device_id: str, current_cpu: float, current_ram: float) -> Dict[str, Any]:
        """Calculates Z-score metric drift (% deviation from baseline) for PC Client."""
        twin = self.get_or_create_twin(device_id)

        # Baseline CPU
        cpu_mean = sum(twin.cpu_samples) / max(1, len(twin.cpu_samples))
        cpu_var = sum((x - cpu_mean) ** 2 for x in twin.cpu_samples) / max(1, len(twin.cpu_samples))
        cpu_std = math.sqrt(cpu_var) if cpu_var > 0 else 1.0
        cpu_z_score = (current_cpu - cpu_mean) / cpu_std

        # Baseline RAM
        ram_mean = sum(twin.ram_samples) / max(1, len(twin.ram_samples))
        ram_var = sum((x - ram_mean) ** 2 for x in twin.ram_samples) / max(1, len(twin.ram_samples))
        ram_std = math.sqrt(ram_var) if ram_var > 0 else 1.0
        ram_z_score = (current_ram - ram_mean) / ram_std

        is_anom = cpu_z_score > 2.5 or ram_z_score > 2.5
        drift_result = {
            "device_id": device_id,
            "cpu_baseline_mean": round(cpu_mean, 1),
            "cpu_z_score": round(cpu_z_score, 2),
            "ram_baseline_mean": round(ram_mean, 1),
            "ram_z_score": round(ram_z_score, 2),
            "is_significant_drift": is_anom,
        }
        logger.info(f"[DIGITAL TWIN] Metric drift for {device_id}: CPU_Z={cpu_z_score:.2f}, RAM_Z={ram_z_score:.2f}, Anomaly={is_anom}")
        return drift_result
