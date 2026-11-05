"""
Do-Operator Module
Implements Judea Pearl's do(X = x) intervention operator by severing incoming edges
and forcing state mutation.
"""

from typing import Dict, Any, Optional
from .scm import StructuralCausalModel
from .causal_graph import CausalGraph


class DoOperator:
    def __init__(self, causal_graph: CausalGraph):
        self.graph = causal_graph

    def apply_do(self, target_variable: str, forced_value: Any) -> Dict[str, Any]:
        """
        Executes do(target_variable = forced_value):
        1. Severs incoming edges to target_variable.
        2. Forces target_variable = forced_value.
        3. Propagates effect downstream through non-severed edges.
        """
        # 1. Sever incoming edges
        self.graph.sever_incoming_edges(target_variable)

        # 2. Propagate effect with forced_value
        simulated_state = self.graph.propagate_causal_effect(target_variable, forced_value)

        # 3. Restore graph edges for next simulation
        self.graph.restore_all_edges()

        return simulated_state
