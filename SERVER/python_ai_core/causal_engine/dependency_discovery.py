"""
Dependency Discovery Module
Discovers dynamic cross-layer dependencies from L1 Physical to L7 Application
and enables cross-layer bottom-up & top-down graph traversal.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Tuple, Optional
from .scm import LayerType


@dataclass
class LayerDependency:
    source_node: str
    source_layer: LayerType
    target_node: str
    target_layer: LayerType
    dependency_type: str  # e.g. "REQUIRES_L3_NETWORK", "REQUIRES_L4_TRANSPORT"


class DependencyDiscovery:
    def __init__(self):
        # target_node -> List[LayerDependency]
        self._dependencies: Dict[str, List[LayerDependency]] = {}
        self._initialize_default_layer_matrix()

    def _initialize_default_layer_matrix(self):
        """Initializes default L1 - L7 cross-layer dependency matrix"""
        # L7 Application depends on L4/L3
        self.add_dependency("Printer_Offline", LayerType.L7_APPLICATION, "ConnectionTimeout", LayerType.L4_TRANSPORT, "REQUIRES_L4_TRANSPORT")
        self.add_dependency("POS_Error", LayerType.L7_APPLICATION, "HTTP_502", LayerType.L7_APPLICATION, "REQUIRES_HTTP")
        self.add_dependency("HTTP_502", LayerType.L7_APPLICATION, "ConnectionTimeout", LayerType.L4_TRANSPORT, "REQUIRES_L4_TRANSPORT")
        self.add_dependency("ConnectionTimeout", LayerType.L4_TRANSPORT, "DNS_Timeout", LayerType.L3_NETWORK, "REQUIRES_L3_DNS")
        self.add_dependency("DNS_Timeout", LayerType.L3_NETWORK, "PacketLoss", LayerType.L3_NETWORK, "REQUIRES_L3_NETWORK")
        self.add_dependency("PacketLoss", LayerType.L3_NETWORK, "RSSI", LayerType.L1_PHYSICAL, "REQUIRES_L1_PHYSICAL")
        self.add_dependency("PacketLoss", LayerType.L3_NETWORK, "FrameDrop", LayerType.L2_DATALINK, "REQUIRES_L2_DATALINK")

    def add_dependency(self, target_node: str, target_layer: LayerType, source_node: str, source_layer: LayerType, dep_type: str):
        dep = LayerDependency(source_node, source_layer, target_node, target_layer, dep_type)
        if target_node not in self._dependencies:
            self._dependencies[target_node] = []
        self._dependencies[target_node].append(dep)

    def traverse_bottom_up(self, target_node: str) -> List[LayerDependency]:
        """
        Traverses dependencies from L7 application symptom down to L1 physical root cause.
        """
        chain: List[LayerDependency] = []
        visited: Set[str] = set()
        queue = [target_node]

        while queue:
            curr = queue.pop(0)
            if curr in visited:
                continue
            visited.add(curr)

            if curr in self._dependencies:
                for dep in self._dependencies[curr]:
                    chain.append(dep)
                    queue.append(dep.source_node)

        return chain
