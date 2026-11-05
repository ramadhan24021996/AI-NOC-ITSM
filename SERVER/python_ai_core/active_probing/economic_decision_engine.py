"""
Economic Decision Engine Module
Solves economic trade-offs for candidate actions:
Cost = ActionCost + (OperationalRisk * AssetCriticality) + ((1 - SuccessProb) * DowntimeCost)
Selects the lowest-cost action path meeting operational targets.
"""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class ActionEconomicMetric:
    action_name: str
    action_cost: float
    operational_risk: float
    success_probability: float
    downtime_cost: float
    total_economic_cost: float


class EconomicDecisionEngine:
    """Calculates total economic cost matrix to select the optimal remediation path."""

    def calculate_economic_cost(
        self,
        action_name: str,
        action_cost: float,
        operational_risk: float,        # Scale 0.0 to 10.0
        success_probability: float,     # Scale 0.0 to 1.0
        downtime_cost: float = 100.0,
        asset_criticality_factor: float = 2.0
    ) -> ActionEconomicMetric:

        failure_prob = max(1.0 - success_probability, 0.0)
        risk_cost = operational_risk * asset_criticality_factor
        downtime_risk_cost = failure_prob * downtime_cost

        total = round(action_cost + risk_cost + downtime_risk_cost, 2)

        return ActionEconomicMetric(
            action_name=action_name,
            action_cost=action_cost,
            operational_risk=operational_risk,
            success_probability=success_probability,
            downtime_cost=downtime_cost,
            total_economic_cost=total
        )

    def select_lowest_cost_action(
        self,
        candidate_actions: List[Dict[str, Any]]
    ) -> ActionEconomicMetric:

        evaluated = [
            self.calculate_economic_cost(
                action_name=str(a.get("name", "Action")),
                action_cost=float(a.get("action_cost", 1.0)),
                operational_risk=float(a.get("risk", 2.0)),
                success_probability=float(a.get("success_prob", 0.90)),
                downtime_cost=float(a.get("downtime_cost", 50.0))
            )
            for a in candidate_actions
        ]

        return sorted(evaluated, key=lambda x: x.total_economic_cost)[0]
