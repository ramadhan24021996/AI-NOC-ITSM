"""
Probe Health Scorer Module
Aggregates probe execution results into domain health scores (Network Health %, System Health %, App Health %).
"""

from dataclasses import dataclass
from typing import List, Dict, Any
from .active_probe_executor import ProbeResult


@dataclass
class DomainHealthReport:
    network_health_pct: float
    system_health_pct: float
    application_health_pct: float
    overall_health_pct: float
    summary: str


class ProbeHealthScorer:
    """Calculates overall infrastructure domain health percentage from diagnostic probe outcomes."""

    def calculate_health_scores(self, probe_results: List[ProbeResult]) -> DomainHealthReport:
        if not probe_results:
            return DomainHealthReport(
                network_health_pct=100.0,
                system_health_pct=100.0,
                application_health_pct=100.0,
                overall_health_pct=100.0,
                summary="No probes executed; baseline health assumed 100%"
            )

        net_results = [r for r in probe_results if r.osi_layer in (1, 2, 3, 4)]
        sys_results = [r for r in probe_results if r.osi_layer in (5, 6)]
        app_results = [r for r in probe_results if r.osi_layer == 7]

        def _calc_pct(results: List[ProbeResult]) -> float:
            if not results:
                return 100.0
            valid = [r for r in results if r.status in ("PASSED", "FAILED")]
            if not valid:
                return 100.0
            passed = sum(1 for r in valid if r.status == "PASSED")
            return round((passed / len(valid)) * 100.0, 1)

        net_pct = _calc_pct(net_results)
        sys_pct = _calc_pct(sys_results)
        app_pct = _calc_pct(app_results)

        overall = round((net_pct * 0.4) + (sys_pct * 0.3) + (app_pct * 0.3), 1)

        return DomainHealthReport(
            network_health_pct=net_pct,
            system_health_pct=sys_pct,
            application_health_pct=app_pct,
            overall_health_pct=overall,
            summary=f"Domain Health: Network={net_pct}%, System={sys_pct}%, App={app_pct}% (Overall={overall}%)"
        )
