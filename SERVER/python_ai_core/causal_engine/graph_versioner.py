"""
Graph Versioner Module
Maintains versioned causal graph snapshots (v1.0, v1.1) with rollback capabilities.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from datetime import datetime, timezone
import json
from .causal_graph import CausalGraph


@dataclass
class GraphVersionSnapshot:
    version: str
    timestamp: str
    edges: List[Dict[str, Any]]
    description: str = ""


class GraphVersioner:
    def __init__(self, causal_graph: Optional[CausalGraph] = None):
        self.graph = causal_graph or CausalGraph()
        self.versions: Dict[str, GraphVersionSnapshot] = {}
        self.current_version = "v1.0"
        self.create_snapshot("v1.0", "Baseline Initial Causal Graph")

    def create_snapshot(self, version_name: str, description: str = "") -> GraphVersionSnapshot:
        """
        Creates snapshot of current graph state.
        """
        edges_data = []
        for cause, edge_list in self.graph.outgoing_edges.items():
            for e in edge_list:
                edges_data.append({
                    "cause": e.cause,
                    "effect": e.effect,
                    "probability": e.probability
                })

        snapshot = GraphVersionSnapshot(
            version=version_name,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            edges=edges_data,
            description=description
        )

        self.versions[version_name] = snapshot
        self.current_version = version_name
        return snapshot

    def rollback_to_version(self, version_name: str) -> bool:
        """
        Rolls back active graph to a specified version snapshot.
        """
        snapshot = self.versions.get(version_name)
        if not snapshot:
            return False

        # Clear current edges
        self.graph.outgoing_edges.clear()
        self.graph.incoming_edges.clear()

        # Re-populate from snapshot
        for ed in snapshot.edges:
            self.graph.add_edge(ed["cause"], ed["effect"], ed["probability"])

        self.current_version = version_name
        return True
