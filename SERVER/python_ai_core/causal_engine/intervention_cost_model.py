"""
Intervention Cost Model Module
Evaluates downtime risk, execution cost, and rollback complexity for candidate remediation actions.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any
from .intervention_planner import ActionableRemediationStep


@dataclass
class EvaluatedAction:
    action: ActionableRemediationStep
    downtime_level: str        # "LOW", "MEDIUM", "HIGH"
    risk_level: str            # "LOW", "MEDIUM", "HIGH"
    rollback_complexity: str  # "EASY", "MODERATE", "HARD"
    net_benefit_score: float   # 0.0 to 100.0


class InterventionCostModel:
    def evaluate_remediation_cost(self, action: ActionableRemediationStep) -> EvaluatedAction:
        """
        Evaluates risk/reward ratio of an actionable remediation step.
        """
        # Assign risk metrics based on action type
        if "Flush" in action.action_name or "Restart Interface" in action.action_name:
            downtime = "LOW"
            risk = "LOW"
            rollback = "EASY"
            score = 92.0
        elif "Restart POS" in action.action_name or "Restart Service" in action.action_name:
            downtime = "MEDIUM"
            risk = "LOW"
            rollback = "EASY"
            score = 80.0
        elif "Switch Wireless AP" in action.action_name:
            downtime = "MEDIUM"
            risk = "MEDIUM"
            rollback = "MODERATE"
            score = 75.0
        else:
            downtime = "HIGH"
            risk = "HIGH"
            rollback = "HARD"
            score = 50.0

        return EvaluatedAction(
            action=action,
            downtime_level=downtime,
            risk_level=risk,
            rollback_complexity=rollback,
            net_benefit_score=score
        )
