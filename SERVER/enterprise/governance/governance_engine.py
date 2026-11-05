"""
SERVER.enterprise.governance - Governance-as-Code Engine
Declarative governance policy evaluation interface.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Dict, Any, List, Optional
from SERVER.shared.enums import ActionRiskLevel

@dataclass
class GovernancePolicy:
    policy_id: str
    name: str
    min_evidence_score: float
    required_risk_level: ActionRiskLevel
    requires_hitl: bool
    description: str = ""

class GovernancePolicyEngine(ABC):
    """Abstract governance policy evaluation engine."""

    @abstractmethod
    def evaluate(
        self,
        action_type: str,
        evidence_score: float,
        user_role: str,
        risk_level: ActionRiskLevel,
    ) -> bool:
        """Returns True if action is permitted under current governance policies."""
        pass

    @abstractmethod
    def get_applicable_policy(self, action_type: str) -> Optional[GovernancePolicy]:
        pass

    @abstractmethod
    def list_policies(self) -> List[GovernancePolicy]:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 5.3
# ══════════════════════════════════════════════════════════════════════════════
import logging
_glog = logging.getLogger("enterprise.governance")

class RuleBasedGovernancePolicyEngine(GovernancePolicyEngine):
    """
    Rule-based governance engine with 5 built-in production policies.
    Policies are loaded from in-memory registry (upgradeable to DB/YAML).
    """

    DEFAULT_POLICIES = [
        GovernancePolicy("POL-001","LOW_RISK_AUTO_APPROVE",   0.60, ActionRiskLevel.LOW_RISK,      False,"Auto-approve low-risk actions with sufficient evidence"),
        GovernancePolicy("POL-002","MEDIUM_RISK_AI_APPROVE",  0.72, ActionRiskLevel.MEDIUM_RISK,   False,"AI-approved medium-risk actions above evidence threshold"),
        GovernancePolicy("POL-003","HIGH_RISK_HITL_REQUIRED", 0.80, ActionRiskLevel.HIGH_RISK,     True, "High-risk actions always require human approval"),
        GovernancePolicy("POL-004","CRITICAL_BLOCK",          0.90, ActionRiskLevel.CRITICAL_RISK, True, "Critical actions require senior operator approval"),
        GovernancePolicy("POL-005","EVIDENCE_FLOOR",          0.50, ActionRiskLevel.LOW_RISK,      False,"Minimum evidence floor — reject if below 0.50"),
    ]

    def __init__(self, extra_policies: Optional[List[GovernancePolicy]] = None):
        self._policies: Dict[str, GovernancePolicy] = {
            p.policy_id: p for p in self.DEFAULT_POLICIES
        }
        for p in (extra_policies or []):
            self._policies[p.policy_id] = p

    def evaluate(self, action_type: str, evidence_score: float,
                 user_role: str, risk_level: ActionRiskLevel) -> bool:
        policy = self.get_applicable_policy(action_type) or self._get_by_risk(risk_level)
        if not policy:
            _glog.warning("[GovernanceEngine] No policy found for action=%s risk=%s — DENY by default", action_type, risk_level)
            return False

        if evidence_score < policy.min_evidence_score:
            _glog.info("[GovernanceEngine] DENIED: evidence %.2f < policy floor %.2f (policy=%s)",
                       evidence_score, policy.min_evidence_score, policy.policy_id)
            return False

        if policy.requires_hitl and user_role not in ("operator", "senior_operator", "admin"):
            _glog.info("[GovernanceEngine] HITL_REQUIRED: role=%s not authorized for policy=%s", user_role, policy.policy_id)
            return False

        _glog.info("[GovernanceEngine] APPROVED: action=%s evidence=%.2f policy=%s", action_type, evidence_score, policy.policy_id)
        return True

    def get_applicable_policy(self, action_type: str) -> Optional[GovernancePolicy]:
        """Match action_type keyword to policy name (case-insensitive substring)."""
        action_upper = action_type.upper()
        for pol in self._policies.values():
            if action_upper in pol.name.upper() or pol.name.upper() in action_upper:
                return pol
        return None

    def _get_by_risk(self, risk_level: ActionRiskLevel) -> Optional[GovernancePolicy]:
        for pol in self._policies.values():
            if pol.required_risk_level == risk_level:
                return pol
        return None

    def list_policies(self) -> List[GovernancePolicy]:
        return list(self._policies.values())
