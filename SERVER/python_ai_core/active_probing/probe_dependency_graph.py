"""
Probe Dependency Graph Module
Prunes downstream probes when a prerequisite probe fails.
For instance, if Ping Gateway fails, downstream probes like DNS Lookup, HTTP HEAD,
and Browser Login are automatically pruned to prevent unnecessary probe load.
"""

from typing import Dict, List, Set, Optional
from .probe_catalog import ProbeCatalog, DiagnosticProbe


class ProbeDependencyGraph:
    """Manages probe execution hierarchy and prunes unreachable downstream probes."""

    def __init__(self, catalog: Optional[ProbeCatalog] = None):
        self.catalog = catalog or ProbeCatalog()
        # probe_id -> List[child_probe_ids]
        self.children_map: Dict[str, List[str]] = {}
        self.failed_probes: Set[str] = set()
        self.pruned_probes: Set[str] = set()
        self._build_dependency_tree()

    def _build_dependency_tree(self):
        for probe_id, probe in self.catalog.probes.items():
            if probe.parent_probe_id:
                parent = probe.parent_probe_id
                if parent not in self.children_map:
                    self.children_map[parent] = []
                self.children_map[parent].append(probe_id)

    def record_probe_failure(self, failed_probe_id: str):
        """Records a probe failure and recursively prunes all dependent downstream probes."""
        self.failed_probes.add(failed_probe_id)

        # Queue for breadth-first pruning of downstream dependencies
        queue = list(self.children_map.get(failed_probe_id, []))
        while queue:
            child_id = queue.pop(0)
            if child_id not in self.pruned_probes:
                self.pruned_probes.add(child_id)
                # Recursively add grand-children
                queue.extend(self.children_map.get(child_id, []))

    def is_pruned(self, probe_id: str) -> bool:
        """Returns True if probe has been pruned due to upstream dependency failure."""
        return probe_id in self.pruned_probes

    def get_pruned_reason(self, probe_id: str) -> Optional[str]:
        if probe_id in self.pruned_probes:
            return f"Pruned automatically because parent prerequisite probe failed ({list(self.failed_probes)})"
        return None
