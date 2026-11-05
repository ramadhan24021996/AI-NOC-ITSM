"""
AI Safety Layer Module
Enforces hard safety guardrails:
1. Prevents concurrent destructive actions on dual-redundant asset pairs
2. Enforces mandatory rollback path validation
3. Freezes autonomous execution when uncertainty spikes (Confidence < 50%)
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Any


@dataclass
class SafetyGuardrailResult:
    action_permitted: bool
    safety_rule_tripped: str
    active_concurrent_changes: int
    rollback_path_validated: bool
    safety_summary: str


class AISafetyLayer:
    """Enforces safety guardrails across AI automation execution paths."""

    def __init__(self):
        self.active_remediations: Set[str] = set()
        self.redundant_pairs = {
            "FW-HQ-01": "FW-HQ-02",
            "CORE-SW-01": "CORE-SW-02"
        }

    def validate_action_safety(
        self,
        target_asset_id: str,
        action_name: str,
        confidence_score: float,
        has_rollback_plan: bool = True
    ) -> SafetyGuardrailResult:

        # 1. Uncertainty freeze guardrail
        if confidence_score < 0.50:
            return SafetyGuardrailResult(
                action_permitted=False,
                safety_rule_tripped="SAFETY-RULE-01: Low-Confidence Freeze (<50%)",
                active_concurrent_changes=len(self.active_remediations),
                rollback_path_validated=has_rollback_plan,
                safety_summary="BLOCKED: Automation frozen due to low confidence (<50%)"
            )

        # 2. Dual-redundant simultaneous action guardrail
        partner = self.redundant_pairs.get(target_asset_id)
        if partner and partner in self.active_remediations:
            return SafetyGuardrailResult(
                action_permitted=False,
                safety_rule_tripped="SAFETY-RULE-02: Dual-Redundant Simultaneous Change Blocked",
                active_concurrent_changes=len(self.active_remediations),
                rollback_path_validated=has_rollback_plan,
                safety_summary=f"BLOCKED: Redundant pair partner '{partner}' is currently undergoing remediation"
            )

        # 3. Rollback plan guardrail
        if not has_rollback_plan and action_name not in ("Ping", "ReadLog", "CheckDNS"):
            return SafetyGuardrailResult(
                action_permitted=False,
                safety_rule_tripped="SAFETY-RULE-03: Mandatory Rollback Path Missing",
                active_concurrent_changes=len(self.active_remediations),
                rollback_path_validated=False,
                safety_summary="BLOCKED: Active remediation lacks verified rollback path"
            )

        return SafetyGuardrailResult(
            action_permitted=True,
            safety_rule_tripped="NONE",
            active_concurrent_changes=len(self.active_remediations),
            rollback_path_validated=True,
            safety_summary="PERMITTED: Action satisfies all AI Safety Guardrails"
        )
