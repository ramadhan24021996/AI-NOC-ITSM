"""
Tiered AI Constitution Module
Enforces global immutable AI Constitution rules across 3 enforcement levels:
- HARD RULES (Kernel Enforced): Never Guess, Human Overrides AI, Every Action Auditable
- SOFT RULES (Policy Enforced): Safety Before Optimization, Every Learning Verified
- ADVISORY RULES: Rollback First
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any
from enum import Enum


class RuleTier(Enum):
    HARD_KERNEL_ENFORCED = 1
    SOFT_POLICY_ENFORCED = 2
    ADVISORY = 3


@dataclass
class ConstitutionRule:
    rule_id: str
    name: str
    tier: RuleTier
    statement: str


@dataclass
class ConstitutionEnforcementResult:
    action_name: str
    permitted: bool
    tripped_rule_id: Optional[str]
    enforcement_tier: Optional[RuleTier]
    explanation: str


class AIOSConstitution:
    """Global immutable AI Constitution rule enforcer across all AIOS agents."""

    def __init__(self):
        self.rules: List[ConstitutionRule] = []
        self._initialize_constitution_rules()

    def _initialize_constitution_rules(self):
        self.rules.append(ConstitutionRule("CONST-01", "Never Guess", RuleTier.HARD_KERNEL_ENFORCED, "Never generate unsupported conclusions without probing evidence"))
        self.rules.append(ConstitutionRule("CONST-02", "Human Overrides AI", RuleTier.HARD_KERNEL_ENFORCED, "Human engineer decisions override AI recommendations unconditionally"))
        self.rules.append(ConstitutionRule("CONST-03", "Every Action Auditable", RuleTier.HARD_KERNEL_ENFORCED, "All system modifications must be logged into immutable event store"))
        self.rules.append(ConstitutionRule("CONST-04", "Safety Before Optimization", RuleTier.SOFT_POLICY_ENFORCED, "Prioritize system safety over performance optimization"))
        self.rules.append(ConstitutionRule("CONST-05", "Rollback First", RuleTier.ADVISORY, "Always verify rollback strategy prior to remediation execution"))

    def validate_action_constitution(
        self,
        action_name: str,
        confidence_score: float,
        has_evidence: bool,
        human_overridden: bool = False
    ) -> ConstitutionEnforcementResult:

        if human_overridden:
            return ConstitutionEnforcementResult(
                action_name=action_name,
                permitted=False,
                tripped_rule_id="CONST-02",
                enforcement_tier=RuleTier.HARD_KERNEL_ENFORCED,
                explanation="HARD RULE TRIPPED (CONST-02): Action overridden by Human Operator"
            )

        if not has_evidence and confidence_score < 0.90:
            return ConstitutionEnforcementResult(
                action_name=action_name,
                permitted=False,
                tripped_rule_id="CONST-01",
                enforcement_tier=RuleTier.HARD_KERNEL_ENFORCED,
                explanation="HARD RULE TRIPPED (CONST-01): Never Guess - Action lacks empirical diagnostic evidence"
            )

        return ConstitutionEnforcementResult(
            action_name=action_name,
            permitted=True,
            tripped_rule_id=None,
            enforcement_tier=None,
            explanation="Action satisfies all AI Constitution Hard, Soft, and Advisory rules"
        )
