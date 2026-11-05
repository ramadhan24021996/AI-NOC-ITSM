"""
Enterprise CMDB Baseline & Asset Inventory Service
Manages CMDB Asset Inventory, Device Metadata, Configuration Baselines, and Drift Analysis.
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("CMDB_BASELINE_SERVICE")

class CMDBBaselineService:
    """
    Enterprise CMDB & Baseline Service
    Maintains official configuration baselines and checks for parameter drift.
    """

    def __init__(self):
        self.asset_inventory: Dict[str, Dict[str, Any]] = {
            "Client_PC_01": {
                "asset_id": "AST-1001",
                "hostname": "Client_PC_01",
                "device_type": "Workstation",
                "vendor": "Dell Inc.",
                "mac": "AA:BB:CC:DD:EE:01",
                "vlan": "VLAN_10",
                "environment": "Production",
                "site": "JAKARTA-HQ"
            },
            "Gateway_Router_01": {
                "asset_id": "AST-9001",
                "hostname": "Gateway_Router_01",
                "device_type": "Core Router",
                "vendor": "Cisco Systems",
                "firmware": "IOS-XE 17.6.3",
                "vlan": "VLAN_1",
                "environment": "Production",
                "site": "JAKARTA-HQ"
            }
        }

        self.config_baselines: Dict[str, Dict[str, Any]] = {
            "Client_PC_01": {
                "mtu": 1500,
                "dns_servers": ["8.8.8.8", "1.1.1.1"],
                "firewall_profile": "Domain",
                "duplex": "Auto-Negotiate"
            }
        }

    def get_asset(self, hostname_or_mac: str) -> Optional[Dict[str, Any]]:
        """Retrieves CMDB asset record."""
        return self.asset_inventory.get(hostname_or_mac)

    def detect_configuration_drift(self, hostname: str, current_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Compares current device configuration against baseline to detect drift."""
        drifts = []
        baseline = self.config_baselines.get(hostname, {})
        for param, expected_val in baseline.items():
            current_val = current_config.get(param)
            if current_val is not None and current_val != expected_val:
                drifts.append({
                    "parameter": param,
                    "expected": expected_val,
                    "actual": current_val,
                    "severity": "HIGH" if param == "dns_servers" else "MEDIUM"
                })
        return drifts
