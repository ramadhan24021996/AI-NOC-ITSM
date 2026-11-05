"""
Incident Graph Builder Module
Builds structured Incident Event Graphs from Fusion Stream timelines for GraphRAG ingestion.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any
import json
from .event_normalizer import NormalizedEvent
from .causal_inference import CausalChain


@dataclass
class GraphNode:
    id: str
    label: str
    modality: str
    source: str
    severity: str
    timestamp: str


@dataclass
class GraphEdge:
    source_id: str
    target_id: str
    relationship: str    # "PRECEDES", "CAUSED_BY", "CORRELATED_WITH"
    weight: float


@dataclass
class IncidentEventGraph:
    graph_id: str
    device_id: str
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    graphrag_context: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "graph_id": self.graph_id,
            "device_id": self.device_id,
            "nodes": [n.__dict__ for n in self.nodes],
            "edges": [e.__dict__ for e in self.edges],
            "graphrag_context": self.graphrag_context
        }


class IncidentGraphBuilder:
    def build_graph(self, causal_chain: CausalChain, events: List[NormalizedEvent]) -> IncidentEventGraph:
        """
        Constructs an IncidentEventGraph from normalized events and a causal chain.
        """
        sorted_events = sorted(events, key=lambda x: x.timestamp)
        nodes: List[GraphNode] = []
        edges: List[GraphEdge] = []

        # Create Nodes
        for e in sorted_events:
            m_val = e.modality.value if isinstance(e.modality, Enum) else str(e.modality)
            nodes.append(GraphNode(
                id=e.event_id,
                label=f"{e.source}:{e.event_code}",
                modality=m_val,
                source=e.source,
                severity=str(e.severity),
                timestamp=e.timestamp
            ))

        # Create Edges along timeline
        for i in range(len(sorted_events) - 1):
            curr_evt = sorted_events[i]
            next_evt = sorted_events[i + 1]

            rel = "CAUSED_BY" if i == 0 else "PRECEDES"
            weight = 0.95 if i == 0 else 0.80

            edges.append(GraphEdge(
                source_id=curr_evt.event_id,
                target_id=next_evt.event_id,
                relationship=rel,
                weight=weight
            ))

        # Format GraphRAG Prompt Context string
        graphrag_lines = [
            f"=== INCIDENT EVENT GRAPH (GraphRAG Context): {causal_chain.cluster_id} ===",
            f"Device: {causal_chain.root_cause_event.device_id}",
            f"Root Cause Event: [{causal_chain.root_cause_event.modality}] {causal_chain.root_cause_event.source} -> {causal_chain.root_cause_event.event_code}",
            f"Affected Layer: {causal_chain.affected_layer}",
            "Sequential Causality Graph:"
        ]
        for e in edges:
            graphrag_lines.append(f"  ({e.source_id}) --[{e.relationship}]--> ({e.target_id})")

        graphrag_lines.append(f"Narrative: {causal_chain.narrative_summary}")
        graphrag_lines.append(f"Suggested RCA: {causal_chain.suggested_rca}")

        graphrag_context = "\n".join(graphrag_lines)

        return IncidentEventGraph(
            graph_id=f"GRAPH-{causal_chain.cluster_id}",
            device_id=causal_chain.root_cause_event.device_id,
            nodes=nodes,
            edges=edges,
            graphrag_context=graphrag_context
        )
