"""
Autonomous Probe Optimizer Module
Tracks probe efficiency metrics (Success Rate %, Avg Latency ms, Expected Information Gain)
to dynamically optimize probe selection and ranking over time.
"""

from dataclasses import dataclass
from typing import Dict, List, Any
from .probe_catalog import ProbeCatalog, DiagnosticProbe


@dataclass
class ProbeEfficiencyMetric:
    probe_id: str
    probe_name: str
    execution_count: int
    success_count: int
    success_rate_pct: float
    avg_latency_ms: float
    efficiency_score: float  # (success_rate * EIG) / (latency_ms + 1)


class AutonomousProbeOptimizer:
    """Dynamically ranks and optimizes diagnostic probe ordering based on empirical efficiency."""

    def __init__(self, catalog: ProbeCatalog):
        self.catalog = catalog
        self.metrics: Dict[str, ProbeEfficiencyMetric] = {}
        self._initialize_baseline_metrics()

    def _initialize_baseline_metrics(self):
        for probe_id, probe in self.catalog.probes.items():
            eff = (0.95 * probe.expected_information_gain) / (probe.estimated_latency_ms + 1.0) * 100.0
            self.metrics[probe_id] = ProbeEfficiencyMetric(
                probe_id=probe_id,
                probe_name=probe.name,
                execution_count=100,
                success_count=95,
                success_rate_pct=95.0,
                avg_latency_ms=probe.estimated_latency_ms,
                efficiency_score=round(eff, 2)
            )

    def record_probe_execution(self, probe_id: str, success: bool, latency_ms: float):
        m = self.metrics.get(probe_id)
        if m:
            m.execution_count += 1
            if success:
                m.success_count += 1
            m.success_rate_pct = round((m.success_count / m.execution_count) * 100.0, 1)
            m.avg_latency_ms = round((m.avg_latency_ms * 0.9) + (latency_ms * 0.1), 1)

            probe = self.catalog.get_probe(probe_id)
            eig = probe.expected_information_gain if probe else 0.8
            eff = (m.success_rate_pct / 100.0 * eig) / (m.avg_latency_ms + 1.0) * 100.0
            m.efficiency_score = round(eff, 2)

    def rank_probes_by_efficiency(self, probe_ids: List[str]) -> List[str]:
        def _score(pid: str) -> float:
            return self.metrics[pid].efficiency_score if pid in self.metrics else 0.0

        return sorted(probe_ids, key=_score, reverse=True)
