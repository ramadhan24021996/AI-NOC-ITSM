"""
Multi-Scenario Counterfactual Simulator Module
Executes compound interventions do(X=False, Y=False) to isolate multi-cause compound incidents.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from .counterfactual import CounterfactualSimulator, CounterfactualResult


@dataclass
class CompoundCounterfactualResult:
    scenario_name: str
    target_variables: List[str]
    real_world_state: Dict[str, Any]
    counterfactual_state: Dict[str, Any]
    primary_symptom_resolved: bool
    compound_impact_score: float


class MultiScenarioCounterfactualSimulator:
    def __init__(self, simulator: Optional[CounterfactualSimulator] = None):
        self.simulator = simulator or CounterfactualSimulator()

    def simulate_compound_scenario(
        self,
        target_variables: List[str],
        real_world_state: Dict[str, Any],
        primary_symptom: str = "POS_Error"
    ) -> CompoundCounterfactualResult:
        """
        Runs compound intervention: do(Var1 = Normal, Var2 = Normal, ...)
        """
        # Apply do-operator sequentially across target variables
        graph = self.simulator.graph

        # Set real world state
        for k, v in real_world_state.items():
            graph.scm.set_value(k, v)

        # Sever incoming edges and apply normal values to all target variables
        for var_name in target_variables:
            graph.sever_incoming_edges(var_name)
            var = graph.scm.get_variable(var_name)
            normal_val = var.default_normal_value if var else False
            sim_state = graph.propagate_causal_effect(var_name, normal_val)

        # Restore graph edges
        graph.restore_all_edges()

        sym_normal = graph.scm.get_variable(primary_symptom).default_normal_value if graph.scm.get_variable(primary_symptom) else False
        sym_cf_val = sim_state.get(primary_symptom, sym_normal)
        resolved = (sym_cf_val == sym_normal)

        scenario_name = " + ".join([f"do({v}=NORMAL)" for v in target_variables])

        return CompoundCounterfactualResult(
            scenario_name=scenario_name,
            target_variables=target_variables,
            real_world_state=real_world_state,
            counterfactual_state=sim_state,
            primary_symptom_resolved=resolved,
            compound_impact_score=0.98 if resolved else 0.40
        )
