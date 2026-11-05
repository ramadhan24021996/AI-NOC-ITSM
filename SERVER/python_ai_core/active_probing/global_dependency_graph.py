"""
Global End-to-End Dependency Graph Module
Models full L1-L7 multi-layer enterprise topology:
ISP ──► FIREWALL ──► CORE_ROUTER ──► SWITCH ──► ACCESS_POINT ──► ENDPOINT (PC / POS / PRINTER)
Projects backbone/infrastructure failures across all downstream dependent services.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional, Any


@dataclass
class TopologyNode:
    node_id: str
    name: str
    layer: str             # "ISP", "FIREWALL", "CORE_ROUTER", "SWITCH", "ACCESS_POINT", "ENDPOINT"
    parent_node_id: Optional[str] = None
    status: str = "HEALTHY"  # "HEALTHY", "DEGRADED", "FAILED"


@dataclass
class ImpactProjectionReport:
    root_cause_node_id: str
    impacted_layer: str
    total_affected_endpoints: int
    affected_endpoint_ids: List[str]
    projection_summary: str


class GlobalDependencyGraph:
    """Manages multi-layer enterprise network dependency topology and projects downstream impact."""

    def __init__(self):
        self.nodes: Dict[str, TopologyNode] = {}
        self.children_map: Dict[str, List[str]] = {}
        self._initialize_enterprise_topology()

    def _initialize_enterprise_topology(self):
        # Layer 1 - ISP & Core Backbone
        self._add_node(TopologyNode("ISP-MAIN-01", "Telkom Fiber Core", "ISP"))
        self._add_node(TopologyNode("FW-HQ-01", "PaloAlto Core Firewall", "FIREWALL", parent_node_id="ISP-MAIN-01"))
        self._add_node(TopologyNode("CORE-SW-01", "Cisco Core Router", "CORE_ROUTER", parent_node_id="FW-HQ-01"))

        # Access Switches & APs
        self._add_node(TopologyNode("SW-FLOOR-01", "Aruba Access Switch 01", "SWITCH", parent_node_id="CORE-SW-01"))
        self._add_node(TopologyNode("AP-RETAIL-01", "Cisco Meraki AP 01", "ACCESS_POINT", parent_node_id="SW-FLOOR-01"))

        # Endpoints
        self._add_node(TopologyNode("POS-KASIR-01", "Kasir Terminal 01", "ENDPOINT", parent_node_id="AP-RETAIL-01"))
        self._add_node(TopologyNode("POS-KASIR-02", "Kasir Terminal 02", "ENDPOINT", parent_node_id="AP-RETAIL-01"))
        self._add_node(TopologyNode("PRINTER-SPOOL-01", "Epson Receipt Printer", "ENDPOINT", parent_node_id="SW-FLOOR-01"))

    def _add_node(self, node: TopologyNode):
        self.nodes[node.node_id] = node
        if node.parent_node_id:
            if node.parent_node_id not in self.children_map:
                self.children_map[node.parent_node_id] = []
            self.children_map[node.parent_node_id].append(node.node_id)

    def project_failure_impact(self, failing_node_id: str) -> ImpactProjectionReport:
        """Traverses downstream tree to identify all affected endpoints if failing_node_id collapses."""
        if failing_node_id not in self.nodes:
            return ImpactProjectionReport(
                root_cause_node_id=failing_node_id,
                impacted_layer="UNKNOWN",
                total_affected_endpoints=0,
                affected_endpoint_ids=[],
                projection_summary=f"Node {failing_node_id} not found in global topology"
            )

        root = self.nodes[failing_node_id]
        root.status = "FAILED"

        affected_endpoints: List[str] = []
        queue = [failing_node_id]

        while queue:
            curr_id = queue.pop(0)
            children = self.children_map.get(curr_id, [])
            for child_id in children:
                child = self.nodes.get(child_id)
                if child:
                    child.status = "DEGRADED"
                    if child.layer == "ENDPOINT":
                        affected_endpoints.append(child_id)
                    queue.append(child_id)

        summary = (
            f"Backbone Failure Projection: Node '{root.name}' ({root.layer}) FAILED. "
            f"Cascaded degradation across {len(affected_endpoints)} downstream endpoint assets: {affected_endpoints}"
        )

        return ImpactProjectionReport(
            root_cause_node_id=failing_node_id,
            impacted_layer=root.layer,
            total_affected_endpoints=len(affected_endpoints),
            affected_endpoint_ids=affected_endpoints,
            projection_summary=summary
        )
