"""
Utility-Based Decision Engine Module
Maximizes net utility function:
Utility = RecoveryScore + SLA_Weight + BusinessValue - OperationalRisk - DirectCost - DowntimeCost
Selects strategy path yielding maximum net utility.
"""

from dataclasses import dataclass
from typing import List, Dict, Any


@dataclass
class ActionUtilityScore:
    strategy_name: str
    recovery_score: float
    sla_benefit: float
    business_value: float
    operational_risk: float
    direct_cost: float
    downtime_cost: float
    net_utility_score: float


class UtilityDecisionEngine:
    """Evaluates utility functions to select the strategy maximizing net enterprise value."""

    def calculate_utility(
        self,
        strategy_name: str,
        recovery_score: float,
        sla_benefit: float,
        business_value: float,
        operational_risk: float,
        direct_cost: float,
        downtime_cost: float
    ) -> ActionUtilityScore:

        net_utility = round((recovery_score + sla_benefit + business_value) - (operational_risk + direct_cost + downtime_cost), 2)

        return ActionUtilityScore(
            strategy_name=strategy_name,
            recovery_score=recovery_score,
            sla_benefit=sla_benefit,
            business_value=business_value,
            operational_risk=operational_risk,
            direct_cost=direct_cost,
            downtime_cost=downtime_cost,
            net_utility_score=net_utility
        )

    def select_maximum_utility_strategy(
        self,
        candidate_options: List[Dict[str, Any]]
    ) -> ActionUtilityScore:

        evaluated = [
            self.calculate_utility(
                strategy_name=str(o.get("name", "Strategy")),
                recovery_score=float(o.get("recovery", 90.0)),
                sla_benefit=float(o.get("sla", 20.0)),
                business_value=float(o.get("value", 50.0)),
                operational_risk=float(o.get("risk", 5.0)),
                direct_cost=float(o.get("cost", 2.0)),
                downtime_cost=float(o.get("downtime", 10.0))
            )
            for o in candidate_options
        ]

        return sorted(evaluated, key=lambda x: x.net_utility_score, reverse=True)[0]
