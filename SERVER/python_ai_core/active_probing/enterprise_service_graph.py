"""
Enterprise Service Graph Module
Maps business-critical services (ERP, POS Retail Payment, Corporate VPN) to IT infrastructure components:
Calculates business impact ($ revenue loss / hour, active affected users).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class BusinessImpactAnalysis:
    service_name: str
    impacted_infrastructure_nodes: List[str]
    affected_users_count: int
    estimated_revenue_loss_per_hour_usd: float
    business_criticality_tier: str


class EnterpriseServiceGraph:
    """Maps infrastructure dependencies to business services and financial impact."""

    def __init__(self):
        self.service_mapping = {
            "ERP": ["CORE-SW-01", "DB-CLUSTER-01"],
            "POS_RETAIL": ["AP-RETAIL-01", "SW-FLOOR-01", "FW-HQ-01"],
            "VPN_GATEWAY": ["FW-HQ-01", "ISP-MAIN-01"]
        }

    def analyze_business_impact(self, failing_infra_node_id: str) -> BusinessImpactAnalysis:
        affected_services = []
        for service, nodes in self.service_mapping.items():
            if failing_infra_node_id in nodes:
                affected_services.append(service)

        if "POS_RETAIL" in affected_services:
            users = 450
            loss = 12500.0
            tier = "TIER_0_MISSION_CRITICAL"
            name = "POS Retail Payment Service"
        elif "ERP" in affected_services:
            users = 1200
            loss = 25000.0
            tier = "TIER_0_MISSION_CRITICAL"
            name = "Enterprise Resource Planning (ERP)"
        else:
            users = 50
            loss = 500.0
            tier = "TIER_2_STANDARD"
            name = "Internal Utility Service"

        return BusinessImpactAnalysis(
            service_name=name,
            impacted_infrastructure_nodes=[failing_infra_node_id],
            affected_users_count=users,
            estimated_revenue_loss_per_hour_usd=loss,
            business_criticality_tier=tier
        )
