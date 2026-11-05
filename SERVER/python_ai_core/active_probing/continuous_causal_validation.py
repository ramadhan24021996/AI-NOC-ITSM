"""
Continuous Causal Graph Validation Engine Module
Periodically re-evaluates Structural Causal Model (SCM) edges (A -> B) against historical & live incidents:
Edge weight updates, stale edge pruning, and causal drift alert triggering.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class CausalEdgeValidationStatus:
    edge_id: str
    source_var: str
    target_var: str
    prior_probability: float
    posterior_probability: float
    supporting_incidents_count: int
    contradicting_incidents_count: int
    status: str      # "VALIDATED", "WEIGHT_DECREASED", "PRUNED"
    drift_alert: bool


class ContinuousCausalValidation:
    """Continuously validates and prunes causal graph edges based on empirical incident telemetry."""

    def __init__(self):
        self.edge_history: Dict[str, CausalEdgeValidationStatus] = {}
        self._initialize_baseline_edges()

    def _initialize_baseline_edges(self):
        self.edge_history["RSSI_Drop->PacketLoss"] = CausalEdgeValidationStatus(
            edge_id="RSSI_Drop->PacketLoss",
            source_var="RSSI_Drop",
            target_var="PacketLoss",
            prior_probability=0.92,
            posterior_probability=0.94,
            supporting_incidents_count=284,
            contradicting_incidents_count=7,
            status="VALIDATED",
            drift_alert=False
        )
        self.edge_history["DNS_Timeout->TLS_Failure"] = CausalEdgeValidationStatus(
            edge_id="DNS_Timeout->TLS_Failure",
            source_var="DNS_Timeout",
            target_var="TLS_Failure",
            prior_probability=0.85,
            posterior_probability=0.40,
            supporting_incidents_count=12,
            contradicting_incidents_count=85,
            status="WEIGHT_DECREASED",
            drift_alert=True
        )

    def reevaluate_causal_edge(
        self,
        edge_id: str,
        recent_supporting_count: int,
        recent_contradicting_count: int
    ) -> CausalEdgeValidationStatus:
        edge = self.edge_history.get(edge_id)
        if not edge:
            edge = CausalEdgeValidationStatus(
                edge_id=edge_id,
                source_var=edge_id.split("->")[0] if "->" in edge_id else "VarA",
                target_var=edge_id.split("->")[1] if "->" in edge_id else "VarB",
                prior_probability=0.80,
                posterior_probability=0.80,
                supporting_incidents_count=recent_supporting_count,
                contradicting_incidents_count=recent_contradicting_count,
                status="VALIDATED",
                drift_alert=False
            )
            self.edge_history[edge_id] = edge

        edge.supporting_incidents_count += recent_supporting_count
        edge.contradicting_incidents_count += recent_contradicting_count

        total = edge.supporting_incidents_count + edge.contradicting_incidents_count
        if total > 0:
            new_prob = round(edge.supporting_incidents_count / total, 3)
            edge.posterior_probability = new_prob

            if new_prob < 0.30:
                edge.status = "PRUNED"
                edge.drift_alert = True
            elif new_prob < 0.70:
                edge.status = "WEIGHT_DECREASED"
                edge.drift_alert = True
            else:
                edge.status = "VALIDATED"
                edge.drift_alert = False

        return edge
