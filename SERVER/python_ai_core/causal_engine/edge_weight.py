"""
Dynamic Edge Weight Learner Module
Updates causal edge probabilities based on NOC operator feedback (Confirmed vs False RCA).
"""

from typing import Dict, Tuple
from .causal_graph import CausalGraph


class DynamicEdgeWeightLearner:
    def __init__(self, causal_graph: CausalGraph):
        self.graph = causal_graph

    def update_weight(self, cause: str, effect: str, confirmed: bool) -> float:
        """
        Increases edge weight if confirmed=True, decreases if confirmed=False.
        """
        if cause in self.graph.outgoing_edges:
            for edge in self.graph.outgoing_edges[cause]:
                if edge.effect == effect:
                    if confirmed:
                        edge.probability = min(0.99, round(edge.probability + 0.05, 2))
                    else:
                        edge.probability = max(0.10, round(edge.probability - 0.10, 2))
                    return edge.probability
        return 0.50
