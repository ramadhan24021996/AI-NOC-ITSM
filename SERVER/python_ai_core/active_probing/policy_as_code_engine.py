"""
Policy-as-Code Engine Module
Evaluates declarative Policy-as-Code rules and risk scores:
Example:
asset.role == 'Domain Controller' AND business_hours == True
THEN deny: [RestartService, ResetNetworkStack]
require: [HITL, CAB_Approval]
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class PolicyRule:
    rule_id: str
    target_role: str
    business_hours_only: bool
    denied_actions: List[str]
    required_authorizations: List[str]
    description: str


@dataclass
class PolicyReasoningResult:
    action: str
    allowed: bool
    requires_hitl: bool
    requires_cab_approval: bool
    matched_rule_id: Optional[str]
    reasoning_summary: str


class PolicyAsCodeEngine:
    """Evaluates declarative Policy-as-Code rules and risk boundaries."""

    def __init__(self):
        self.rules: List[PolicyRule] = []
        self._initialize_default_rules()

    def _initialize_default_rules(self):
        self.rules.append(PolicyRule(
            rule_id="PAC-DC-01",
            target_role="Domain Controller",
            business_hours_only=True,
            denied_actions=["RestartService", "ResetNetworkStack", "DriverReplacement"],
            required_authorizations=["HITL", "CAB_APPROVAL"],
            description="Deny active restarts on Domain Controllers during business hours without CAB approval"
        ))
        self.rules.append(PolicyRule(
            rule_id="PAC-DB-01",
            target_role="Database Server",
            business_hours_only=False,
            denied_actions=["ResetNetworkStack", "RebootHost"],
            required_authorizations=["HITL"],
            description="Require HITL authorization for Database network changes"
        ))

    def evaluate_action_policy(
        self,
        asset_role: str,
        action_name: str,
        is_business_hours: bool = True,
        hitl_approved: bool = False,
        cab_approved: bool = False
    ) -> PolicyReasoningResult:

        for rule in self.rules:
            if rule.target_role.lower() in asset_role.lower():
                if rule.business_hours_only and not is_business_hours:
                    continue

                if action_name in rule.denied_actions:
                    has_auth = True
                    if "HITL" in rule.required_authorizations and not hitl_approved:
                        has_auth = False
                    if "CAB_APPROVAL" in rule.required_authorizations and not cab_approved:
                        has_auth = False

                    if not has_auth:
                        auth_req = ", ".join(rule.required_authorizations)
                        return PolicyReasoningResult(
                            action=action_name,
                            allowed=False,
                            requires_hitl="HITL" in rule.required_authorizations,
                            requires_cab_approval="CAB_APPROVAL" in rule.required_authorizations,
                            matched_rule_id=rule.rule_id,
                            reasoning_summary=f"Action '{action_name}' DENIED by Rule {rule.rule_id}: Requires [{auth_req}] authorization on {asset_role}"
                        )

        return PolicyReasoningResult(
            action=action_name,
            allowed=True,
            requires_hitl=False,
            requires_cab_approval=False,
            matched_rule_id=None,
            reasoning_summary=f"Action '{action_name}' PERMITTED on {asset_role} under Policy-as-Code"
        )
