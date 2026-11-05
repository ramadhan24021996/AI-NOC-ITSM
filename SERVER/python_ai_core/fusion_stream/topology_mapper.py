"""
Topology Mapper Module
Maps infrastructure dependencies and blast-radius propagation across layers.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Any


@dataclass
class TopologyNode:
    device_id: str
    layer: str
    dependencies: List[str] = field(default_factory=list)


class TopologyMapper:
    def __init__(self):
        # Default dependency mapping: Child -> Parent dependencies
        self._topology_graph: Dict[str, List[str]] = {}

    def register_dependency(self, child_device: str, parent_device: str):
        if child_device not in self._topology_graph:
            self._topology_graph[child_device] = []
        if parent_device not in self._topology_graph[child_device]:
            self._topology_graph[child_device].append(parent_device)

    def get_blast_radius(self, root_device_id: str) -> List[str]:
        """
        Finds all downstream devices/services affected if root_device_id fails.
        """
        affected: Set[str] = set()
        queue = [root_device_id]

        while queue:
            curr = queue.pop(0)
            for child, parents in self._topology_graph.items():
                if curr in parents and child not in affected:
                    affected.add(child)
                    queue.append(child)

        return list(affected)
