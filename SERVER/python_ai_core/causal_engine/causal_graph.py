"""
Causal Graph Module
Manages directed cause-and-effect relationships and edge probability weights.
Edges carry rich audit metadata for full traceability and confidence explainability.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Tuple, Any
from datetime import datetime, timezone
from .scm import StructuralCausalModel, CausalVariable


@dataclass
class CausalEdge:
    """Rich Auditable Causal Edge with full provenance metadata."""
    cause: str
    effect: str
    probability: float           # Current effective causal probability (0.0 - 1.0)
    # Rich Audit Metadata
    causal_probability: float = field(default=0.0)   # Baseline causal probability
    evidence_count: int = 0                           # Total observations supporting this edge
    last_verified: str = ""                           # ISO8601 timestamp of last verification
    supporting_incidents: int = 0                     # # of incidents confirming this causality
    contradicting_incidents: int = 0                  # # of incidents contradicting this causality
    confidence: float = 0.0                           # Derived confidence: supporting/(supporting+contradicting)
    severed: bool = False                             # True if do-operator has severed this edge

    def audit_dict(self) -> Dict[str, Any]:
        """Returns full audit metadata dictionary for inspection and logging."""
        return {
            "edge": f"{self.cause} -> {self.effect}",
            "causal_probability": self.causal_probability,
            "evidence_count": self.evidence_count,
            "last_verified": self.last_verified,
            "supporting_incidents": self.supporting_incidents,
            "contradicting_incidents": self.contradicting_incidents,
            "confidence": self.confidence,
        }

    def refresh_confidence(self):
        """Recalculates derived confidence from supporting vs contradicting evidence."""
        total = self.supporting_incidents + self.contradicting_incidents
        if total > 0:
            self.confidence = round(self.supporting_incidents / total, 3)
        else:
            self.confidence = self.causal_probability


class CausalGraph:
    def __init__(self, scm: Optional[StructuralCausalModel] = None):
        self.scm = scm or StructuralCausalModel()
        # cause -> List[CausalEdge]
        self.outgoing_edges: Dict[str, List[CausalEdge]] = {}
        # effect -> List[CausalEdge]
        self.incoming_edges: Dict[str, List[CausalEdge]] = {}
        self._initialize_default_edges()

    def _initialize_default_edges(self):
        """Initializes default cause-and-effect edges between SCM variables"""
        self.add_edge("RSSI", "PacketLoss", 0.95)
        self.add_edge("PacketLoss", "TCP_Retransmission", 0.92)
        self.add_edge("PacketLoss", "GatewayLatency", 0.88)
        self.add_edge("TCP_Retransmission", "DNS_Timeout", 0.90)
        self.add_edge("DNS_Timeout", "ConnectionTimeout", 0.88)
        self.add_edge("ConnectionTimeout", "HTTP_502", 0.85)
        self.add_edge("HTTP_502", "POS_Error", 0.90)
        self.add_edge("POS_Error", "Printer_Offline", 0.75)

        # L2 edges
        self.add_edge("BroadcastStorm", "CRC_Error", 0.85)
        self.add_edge("CRC_Error", "FrameDrop", 0.90)
        self.add_edge("FrameDrop", "PacketLoss", 0.95)

        # L5/L6 edges
        self.add_edge("CertExpired", "TLS_Failure", 0.98)
        self.add_edge("TLS_Failure", "ConnectionTimeout", 0.92)

    def add_edge(
        self,
        cause: str,
        effect: str,
        probability: float,
        evidence_count: int = 0,
        supporting_incidents: int = 0,
        contradicting_incidents: int = 0
    ):
        now_ts = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        edge = CausalEdge(
            cause=cause,
            effect=effect,
            probability=probability,
            causal_probability=probability,
            evidence_count=evidence_count,
            last_verified=now_ts,
            supporting_incidents=supporting_incidents,
            contradicting_incidents=contradicting_incidents,
            confidence=probability,
        )
        edge.refresh_confidence()

        if cause not in self.outgoing_edges:
            self.outgoing_edges[cause] = []
        self.outgoing_edges[cause].append(edge)

        if effect not in self.incoming_edges:
            self.incoming_edges[effect] = []
        self.incoming_edges[effect].append(edge)

    def get_edge_audit(self, cause: str, effect: str) -> Optional[Dict[str, Any]]:
        """Returns full audit metadata for a specific causal edge."""
        if cause in self.outgoing_edges:
            for edge in self.outgoing_edges[cause]:
                if edge.effect == effect:
                    return edge.audit_dict()
        return None

    def record_incident_outcome(self, cause: str, effect: str, confirmed: bool):
        """Updates edge audit trail based on confirmed or contradicted incident outcome."""
        if cause in self.outgoing_edges:
            for edge in self.outgoing_edges[cause]:
                if edge.effect == effect:
                    edge.evidence_count += 1
                    edge.last_verified = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    if confirmed:
                        edge.supporting_incidents += 1
                    else:
                        edge.contradicting_incidents += 1
                    edge.refresh_confidence()

    def update_edge_from_drift(self, cause: str, effect: str, updated_probability: float, drift_delta: float = 0.0):
        """
        Dynamically adjusts causal edge weights based on telemetry drift analysis.
        """
        found = False
        if cause in self.outgoing_edges:
            for edge in self.outgoing_edges[cause]:
                if edge.effect == effect:
                    edge.probability = max(0.01, min(1.0, updated_probability))
                    edge.causal_probability = edge.probability
                    edge.evidence_count += 1
                    edge.last_verified = datetime.now(timezone.utc).strftime("%Y-%m-%d")
                    edge.refresh_confidence()
                    found = True
                    break
        if not found:
            self.add_edge(cause, effect, updated_probability, evidence_count=1)

    def sever_incoming_edges(self, variable_name: str):
        """Severs all incoming edges to variable_name (used by do-operator)"""
        if variable_name in self.incoming_edges:
            for edge in self.incoming_edges[variable_name]:
                edge.severed = True

    def restore_all_edges(self):
        """Restores all severed edges"""
        for edge_list in self.outgoing_edges.values():
            for edge in edge_list:
                edge.severed = False

    def get_children(self, cause: str) -> List[Tuple[str, float]]:
        """Returns non-severed downstream effect variables and edge probabilities"""
        results = []
        if cause in self.outgoing_edges:
            for edge in self.outgoing_edges[cause]:
                if not edge.severed:
                    results.append((edge.effect, edge.probability))
        return results

    def propagate_causal_effect(self, root_cause: str, root_value: Any) -> Dict[str, Any]:
        """
        Propagates state mutations downstream along non-severed causal edges.
        Returns simulated state of all SCM variables.
        """
        simulated_values: Dict[str, Any] = {
            k: v.value for k, v in self.scm.variables.items()
        }
        simulated_values[root_cause] = root_value

        queue = [root_cause]
        visited: Set[str] = set()

        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)

            curr_val = simulated_values[curr]
            children = self.get_children(curr)

            for child_name, prob in children:
                # If current node is anomalous or mutated, mutate child if probability threshold met
                if curr_val != self.scm.variables[curr].default_normal_value:
                    if prob >= 0.50:
                        # Mutate child to anomalous value
                        child_var = self.scm.variables.get(child_name)
                        if child_var:
                            if isinstance(child_var.default_normal_value, bool):
                                simulated_values[child_name] = True
                            elif isinstance(child_var.default_normal_value, (int, float)):
                                simulated_values[child_name] = child_var.default_normal_value * 2
                            queue.append(child_name)
                else:
                    # If current node is NORMAL (due to intervention), downstream node resets to normal if not forced
                    child_var = self.scm.variables.get(child_name)
                    if child_var:
                        simulated_values[child_name] = child_var.default_normal_value
                        queue.append(child_name)

        return simulated_values
