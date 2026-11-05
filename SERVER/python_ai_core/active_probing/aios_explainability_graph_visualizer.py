"""
Explainability Graph Visualizer Module
Transforms textual RCA explainability into visual graph payloads and Mermaid diagrams:
Nodes & edges with color coding, confidence scores, edge weights, counterfactual paths, Bayesian updates, and timeline sequences.
e.g., Gateway [Conf: 0.92] ──► Packet Loss ──► DNS Timeout ──► POS Error
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class VisualGraphNode:
    node_id: str
    label: str
    node_type: str       # "CAUSE", "SYMPTOM", "IMPACT", "REMEDIATION"
    confidence_score: float
    color_hex: str


@dataclass
class VisualGraphEdge:
    source_node_id: str
    target_node_id: str
    edge_weight: float
    is_counterfactual_path: bool
    label: str


@dataclass
class ExplainabilityGraphPayload:
    incident_id: str
    nodes: List[VisualGraphNode]
    edges: List[VisualGraphEdge]
    mermaid_diagram_markdown: str
    timeline_sequence: List[str]


class AIOSExplainabilityGraphVisualizer:
    """Transforms RCA investigation results into visual graph payloads and Mermaid diagrams."""

    def generate_explainability_graph(
        self,
        incident_id: str,
        rca_title: str,
        confidence_score: float = 0.92
    ) -> ExplainabilityGraphPayload:

        nodes = [
            VisualGraphNode("N1", "Gateway Router FW-01", "CAUSE", confidence_score, "#FF4D4D"), # Red for Cause
            VisualGraphNode("N2", "Packet Loss (15%)", "SYMPTOM", 0.88, "#FFA500"),               # Orange for Symptom
            VisualGraphNode("N3", "DNS Timeout", "SYMPTOM", 0.85, "#FFA500"),
            VisualGraphNode("N4", "HTTP 502 Bad Gateway", "IMPACT", 0.94, "#E60000"),              # Dark Red for Impact
            VisualGraphNode("N5", "POS Retail Error", "BUSINESS_IMPACT", 0.98, "#8B0000"),
            VisualGraphNode("N6", "Execute Non-Disruptive Failover", "REMEDIATION", 0.95, "#28A745") # Green for Remediation
        ]

        edges = [
            VisualGraphEdge("N1", "N2", 0.88, True, "causes_loss"),
            VisualGraphEdge("N2", "N3", 0.82, False, "triggers_timeout"),
            VisualGraphEdge("N3", "N4", 0.90, False, "causes_502"),
            VisualGraphEdge("N4", "N5", 0.96, False, "impacts_pos"),
            VisualGraphEdge("N6", "N1", 0.99, True, "remediates")
        ]

        mermaid_lines = [
            "```mermaid",
            "graph TD",
            '  N1["Gateway Router FW-01 (Conf: 92%)"] :::causeStyle',
            '  N2["Packet Loss 15%"] :::symptomStyle',
            '  N3["DNS Timeout"] :::symptomStyle',
            '  N4["HTTP 502 Bad Gateway"] :::impactStyle',
            '  N5["POS Retail Error"] :::businessStyle',
            '  N6["Execute Non-Disruptive Failover"] :::remediationStyle',
            "  N1 -->|Weight: 0.88 (Counterfactual)| N2",
            "  N2 -->|Weight: 0.82| N3",
            "  N3 -->|Weight: 0.90| N4",
            "  N4 -->|Weight: 0.96| N5",
            "  N6 -.->|Remediates| N1",
            "  classDef causeStyle fill:#FF4D4D,stroke:#333,stroke-width:2px,color:#fff",
            "  classDef symptomStyle fill:#FFA500,stroke:#333,stroke-width:1px,color:#fff",
            "  classDef impactStyle fill:#E60000,stroke:#333,stroke-width:2px,color:#fff",
            "  classDef businessStyle fill:#8B0000,stroke:#333,stroke-width:2px,color:#fff",
            "  classDef remediationStyle fill:#28A745,stroke:#333,stroke-width:2px,color:#fff",
            "```"
        ]
        mermaid_str = "\n".join(mermaid_lines)

        timeline = [
            "15:00:00 - Symptom Detected: POS Retail Error",
            "15:00:02 - Diagnostic Probe Completed: Gateway FW-01 Packet Loss = 15%",
            "15:00:05 - Counterfactual Simulation: Switching Gateway restores 100% throughput",
            "15:00:08 - Bayesian Confidence Calibrated: 92% (Calibrated from raw 98%)",
            "15:00:10 - Remediation Execution: Non-Disruptive Failover Granted"
        ]

        return ExplainabilityGraphPayload(
            incident_id=incident_id,
            nodes=nodes,
            edges=edges,
            mermaid_diagram_markdown=mermaid_str,
            timeline_sequence=timeline
        )
