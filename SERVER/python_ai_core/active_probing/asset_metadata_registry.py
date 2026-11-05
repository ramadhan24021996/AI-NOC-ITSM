"""
Asset Metadata Registry Module
Stores enterprise asset context:
hostname, role (Domain Controller, Database, POS, Workstation), business criticality, owner, maintenance window, operating hours, SLA.
"""

from dataclasses import dataclass, field
from typing import Dict, Optional, Any
from enum import Enum


class AssetRole(Enum):
    DOMAIN_CONTROLLER = "Domain Controller"
    DATABASE_SERVER = "Database Server"
    POS_TERMINAL = "POS Terminal"
    WORKSTATION = "Workstation"
    CORE_GATEWAY = "Core Gateway"


class CriticalityLevel(Enum):
    CRITICAL = "CRITICAL"    # 99.99% Uptime required
    HIGH = "HIGH"            # 99.9% Uptime
    MEDIUM = "MEDIUM"        # 99.0% Uptime
    LOW = "LOW"              # Best effort


@dataclass
class EnterpriseAsset:
    asset_id: str
    hostname: str
    role: AssetRole
    criticality: CriticalityLevel
    owner_team: str
    in_maintenance_window: bool = False
    operating_hours: str = "24x7"
    sla_response_minutes: int = 15

    def to_dict(self) -> Dict[str, Any]:
        return {
            "asset_id": self.asset_id,
            "hostname": self.hostname,
            "role": self.role.value,
            "criticality": self.criticality.value,
            "owner_team": self.owner_team,
            "in_maintenance_window": self.in_maintenance_window,
            "operating_hours": self.operating_hours,
            "sla_response_minutes": self.sla_response_minutes
        }


class AssetMetadataRegistry:
    """Registry storing enterprise asset metadata and business criticality context."""

    def __init__(self):
        self.assets: Dict[str, EnterpriseAsset] = {}
        self._initialize_default_assets()

    def _initialize_default_assets(self):
        self._add(EnterpriseAsset(
            asset_id="DC-HQ-01",
            hostname="dc01.company.internal",
            role=AssetRole.DOMAIN_CONTROLLER,
            criticality=CriticalityLevel.CRITICAL,
            owner_team="IAM-Infra",
            sla_response_minutes=5
        ))
        self._add(EnterpriseAsset(
            asset_id="DB-PROD-01",
            hostname="pg01.company.internal",
            role=AssetRole.DATABASE_SERVER,
            criticality=CriticalityLevel.CRITICAL,
            owner_team="Database-Ops",
            sla_response_minutes=5
        ))
        self._add(EnterpriseAsset(
            asset_id="POS-KASIR-01",
            hostname="pos-kasir-store01",
            role=AssetRole.POS_TERMINAL,
            criticality=CriticalityLevel.HIGH,
            owner_team="Retail-IT",
            sla_response_minutes=15
        ))
        self._add(EnterpriseAsset(
            asset_id="Client_PC_01",
            hostname="pc-user-01",
            role=AssetRole.WORKSTATION,
            criticality=CriticalityLevel.MEDIUM,
            owner_team="Helpdesk",
            sla_response_minutes=60
        ))

    def _add(self, asset: EnterpriseAsset):
        self.assets[asset.asset_id] = asset

    def get_asset(self, asset_id: str) -> EnterpriseAsset:
        return self.assets.get(asset_id, EnterpriseAsset(
            asset_id=asset_id,
            hostname=asset_id,
            role=AssetRole.WORKSTATION,
            criticality=CriticalityLevel.MEDIUM,
            owner_team="Helpdesk"
        ))
