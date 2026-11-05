"""
Causal Edge Weight Evolution Engine Module
Statistically adjusts causal edge weights without overwriting edges:
Calculates posterior weights based on verification success (+boost) or false RCA (-penalty),
and manages edge deprecation/retirement lifecycles.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class CausalEdgeWeightUpdate:
    cause_node: str
    effect_node: str
    previous_weight: float
    updated_weight: float
    sample_count: int
    status: str   # "ACTIVE", "BOOSTED", "DECAYED", "DEPRECATED", "RETIRED"


class CausalGraphEvolution:
    """Manages statistical edge weight updates and non-destructive causal graph evolution."""

    def __init__(self):
        self.edges: Dict[str, CausalEdgeWeightUpdate] = {
            "Gateway->PacketLoss": CausalEdgeWeightUpdate("Gateway", "PacketLoss", 0.72, 0.72, 100, "ACTIVE"),
            "APChannelNoise->POSDelay": CausalEdgeWeightUpdate("APChannelNoise", "POSDelay", 0.65, 0.65, 50, "ACTIVE")
        }

    def evolve_edge_weight(
        self,
        cause_node: str,
        effect_node: str,
        verification_success: bool,
        is_false_rca: bool = False
    ) -> CausalEdgeWeightUpdate:

        key = f"{cause_node}->{effect_node}"
        edge = self.edges.get(key, CausalEdgeWeightUpdate(cause_node, effect_node, 0.50, 0.50, 1, "ACTIVE"))

        prev = edge.updated_weight
        n = edge.sample_count + 1

        if is_false_rca:
            new_w = max(0.01, prev - 0.25)
            status = "DECAYED" if new_w >= 0.20 else "DEPRECATED"
        elif verification_success:
            new_w = min(0.99, prev + 0.05)
            status = "BOOSTED"
        else:
            new_w = max(0.01, prev - 0.05)
            status = "DECAYED"

        if new_w < 0.10:
            status = "RETIRED"

        updated = CausalEdgeWeightUpdate(
            cause_node=cause_node,
            effect_node=effect_node,
            previous_weight=prev,
            updated_weight=round(new_w, 4),
            sample_count=n,
            status=status
        )
        self.edges[key] = updated
        return updated
