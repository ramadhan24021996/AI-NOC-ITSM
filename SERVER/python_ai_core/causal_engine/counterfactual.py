"""
Counterfactual Simulator Module
Executes parallel counterfactual world simulations ("What if X = FALSE?")
to eliminate secondary symptoms and isolate true root causes.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from .scm import StructuralCausalModel
from .causal_graph import CausalGraph
from .do_operator import DoOperator


@dataclass
class CounterfactualResult:
    target_variable: str
    intervention_value: Any
    real_world_state: Dict[str, Any]
    counterfactual_state: Dict[str, Any]
    primary_symptom_resolved: bool   # e.g. True if POS_Error resolved
    is_root_cause_candidate: bool
    impact_score: float               # 0.0 to 1.0


class CounterfactualSimulator:
    def __init__(self, causal_graph: Optional[CausalGraph] = None):
        self.graph = causal_graph or CausalGraph()
        self.do_op = DoOperator(self.graph)

    def simulate_counterfactual(
        self,
        target_variable: str,
        real_world_state: Dict[str, Any],
        primary_symptom: str = "POS_Error"
    ) -> CounterfactualResult:
        """
        Runs counterfactual question: "What if target_variable were NORMAL?"
        do(target_variable = default_normal_value)
        """
        # Set real-world state into graph SCM
        for var_name, val in real_world_state.items():
            self.graph.scm.set_value(var_name, val)

        var = self.graph.scm.get_variable(target_variable)
        normal_val = var.default_normal_value if var else False

        # Apply do(target_variable = normal_val)
        counterfactual_state = self.do_op.apply_do(target_variable, normal_val)

        # Check if primary symptom (e.g. POS_Error) was resolved in counterfactual world
        sym_normal_val = self.graph.scm.get_variable(primary_symptom).default_normal_value if self.graph.scm.get_variable(primary_symptom) else False
        sym_cf_val = counterfactual_state.get(primary_symptom, sym_normal_val)
        primary_symptom_resolved = (sym_cf_val == sym_normal_val)

        # Calculate impact score (% of anomalous variables returned to normal)
        anomalous_real = [k for k, v in real_world_state.items() if var and self.graph.scm.get_variable(k) and v != self.graph.scm.get_variable(k).default_normal_value]
        anomalous_cf = [k for k, v in counterfactual_state.items() if var and self.graph.scm.get_variable(k) and v != self.graph.scm.get_variable(k).default_normal_value]

        resolved_count = len(anomalous_real) - len(anomalous_cf)
        impact_score = round(max(0.0, float(resolved_count) / float(max(1, len(anomalous_real)))), 2)

        # Is root cause if primary symptom is resolved AND impact score > 0.30
        is_root_cause = primary_symptom_resolved and (impact_score >= 0.30 or target_variable in ["PacketLoss", "RSSI", "BroadcastStorm"])

        return CounterfactualResult(
            target_variable=target_variable,
            intervention_value=normal_val,
            real_world_state=real_world_state,
            counterfactual_state=counterfactual_state,
            primary_symptom_resolved=primary_symptom_resolved,
            is_root_cause_candidate=is_root_cause,
            impact_score=impact_score
        )
