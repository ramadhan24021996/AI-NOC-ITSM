"""
Dynamic Asset Policy Engine Module
Enforces role-specific probe permissions based on enterprise asset roles:
Domain Controller denies service restarts & driver updates while allowing Ping/LDAP;
Workstations allow DNS flush/DHCP renew.
"""

from dataclasses import dataclass
from typing import List, Dict, Any, Tuple
from .asset_metadata_registry import EnterpriseAsset, AssetRole, CriticalityLevel
from .probe_catalog import DiagnosticProbe, RiskLevel


@dataclass
class PolicyEvaluationResult:
    allowed: bool
    reason: str
    requires_hitl: bool


class DynamicAssetPolicyEngine:
    """Evaluates probe execution against fine-grained asset role policies."""

    def evaluate_asset_probe_policy(
        self,
        asset: EnterpriseAsset,
        probe: DiagnosticProbe,
        hitl_approved: bool = False
    ) -> PolicyEvaluationResult:

        # 1. Read-Only probes are globally permitted across all roles
        if probe.read_only:
            return PolicyEvaluationResult(
                allowed=True,
                reason=f"Read-only probe '{probe.name}' allowed on {asset.role.value} ({asset.asset_id})",
                requires_hitl=False
            )

        # 2. Strict Role Rules
        if asset.role == AssetRole.DOMAIN_CONTROLLER:
            # Deny active restarts/modifications on Domain Controllers without explicit HITL
            if not hitl_approved:
                return PolicyEvaluationResult(
                    allowed=False,
                    reason=f"Active probe '{probe.name}' BLOCKED on Domain Controller {asset.hostname}: HITL approval required for Domain Infrastructure",
                    requires_hitl=True
                )

        if asset.role == AssetRole.DATABASE_SERVER:
            if probe.risk_level in (RiskLevel.LEVEL_3_MEDIUM_RISK, RiskLevel.LEVEL_4_HIGH_RISK) and not hitl_approved:
                return PolicyEvaluationResult(
                    allowed=False,
                    reason=f"Medium/High risk probe '{probe.name}' BLOCKED on Database Server {asset.hostname}: HITL required",
                    requires_hitl=True
                )

        # 3. Workstation / POS Terminal Rules
        if asset.role in (AssetRole.WORKSTATION, AssetRole.POS_TERMINAL):
            if probe.risk_level == RiskLevel.LEVEL_2_LOW_RISK:
                return PolicyEvaluationResult(
                    allowed=True,
                    reason=f"Low-risk active probe '{probe.name}' permitted on {asset.role.value}",
                    requires_hitl=False
                )

        # Default check for Level 4
        if probe.risk_level == RiskLevel.LEVEL_4_HIGH_RISK and not hitl_approved:
            return PolicyEvaluationResult(
                allowed=False,
                reason=f"Level 4 High-Risk probe '{probe.name}' requires Human-in-the-Loop approval",
                requires_hitl=True
            )

        return PolicyEvaluationResult(
            allowed=True,
            reason=f"Probe '{probe.name}' complies with {asset.role.value} policy",
            requires_hitl=False
        )
