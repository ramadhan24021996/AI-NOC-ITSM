"""
Causal Model Builder Module
Automated discovery & continuous building of Causal Models from telemetry trends.
Proposes new cause-and-effect edges based on historical co-occurrence and temporal precedence.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from datetime import datetime
from .causal_graph import CausalGraph, CausalEdge
from .scm import StructuralCausalModel


@dataclass
class ProposedCausalEdge:
    cause: str
    effect: str
    proposed_probability: float
    historical_occurrences: int
    validation_status: str   # "PROPOSED", "VALIDATED", "REJECTED"


class CausalModelBuilder:
    def __init__(self, causal_graph: Optional[CausalGraph] = None):
        self.graph = causal_graph or CausalGraph()
        self._historical_co_occurrences: Dict[Tuple[str, str], int] = {}
        self.proposed_edges: List[ProposedCausalEdge] = []

    def record_occurrence(self, cause: str, effect: str):
        """Records historical occurrence of cause preceding effect"""
        key = (cause, effect)
        self._historical_co_occurrences[key] = self._historical_co_occurrences.get(key, 0) + 1

    def discover_new_edges(self, min_occurrences: int = 3) -> List[ProposedCausalEdge]:
        """
        Discovers new causal edges from historical co-occurrences.
        """
        new_proposals: List[ProposedCausalEdge] = []

        for (cause, effect), count in self._historical_co_occurrences.items():
            if count >= min_occurrences:
                prob = min(0.95, round(0.50 + (count * 0.05), 2))
                proposal = ProposedCausalEdge(
                    cause=cause,
                    effect=effect,
                    proposed_probability=prob,
                    historical_occurrences=count,
                    validation_status="PROPOSED"
                )
                new_proposals.append(proposal)

        self.proposed_edges = new_proposals
        return new_proposals

    def validate_and_apply_proposal(self, cause: str, effect: str) -> bool:
        """
        Validates and applies a proposed edge to the active CausalGraph.
        """
        for p in self.proposed_edges:
            if p.cause == cause and p.effect == effect:
                p.validation_status = "VALIDATED"
                self.graph.add_edge(cause, effect, p.proposed_probability)
                return True
        return False
