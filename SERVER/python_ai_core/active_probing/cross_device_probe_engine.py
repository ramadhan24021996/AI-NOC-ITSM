"""
Cross-Device Probe Engine Module
Executes diagnostic comparisons across multiple endpoint devices (e.g. PC001 vs PC002)
to isolate local client anomalies from infrastructure-wide gateway failures.
"""

from dataclasses import dataclass
from typing import Dict, List, Any
from .probe_catalog import ProbeCatalog
from .active_probe_executor import ActiveProbeExecutor, ProbeResult


@dataclass
class CrossDeviceAnalysisResult:
    target_device: str
    comparison_device: str
    target_probe_status: str
    comparison_probe_status: str
    isolation_scope: str      # "LOCAL_ENDPOINT_ISSUE", "INFRASTRUCTURE_GATEWAY_ISSUE", "UNCONCLUSIVE"
    confidence: float
    summary: str


class CrossDeviceProbeEngine:
    """Executes multi-endpoint comparative diagnostic probes."""

    def __init__(self, catalog: ProbeCatalog, executor: ActiveProbeExecutor):
        self.catalog = catalog
        self.executor = executor

    def analyze_cross_device_correlation(
        self,
        primary_device: str,
        comparison_device: str,
        probe_id: str,
        telemetry_context: Dict[str, Any]
    ) -> CrossDeviceAnalysisResult:
        probe = self.catalog.get_probe(probe_id)
        if not probe:
            return CrossDeviceAnalysisResult(
                target_device=primary_device,
                comparison_device=comparison_device,
                target_probe_status="UNKNOWN",
                comparison_probe_status="UNKNOWN",
                isolation_scope="UNCONCLUSIVE",
                confidence=0.50,
                summary=f"Probe ID {probe_id} not found in catalog"
            )

        # Primary Device Probe
        primary_ctx = dict(telemetry_context)
        primary_ctx["device_id"] = primary_device
        primary_res: ProbeResult = self.executor.execute_probe(probe, primary_ctx)

        # Comparison Device Probe
        comp_ctx = dict(telemetry_context)
        comp_ctx["device_id"] = comparison_device
        # Remove simulated failure for comparison device if present to test baseline
        if "simulated_failures" in comp_ctx:
            comp_ctx["simulated_failures"] = [f for f in comp_ctx["simulated_failures"] if comparison_device in str(f)]

        comp_res: ProbeResult = self.executor.execute_probe(probe, comp_ctx)

        # Analysis Scope Isolation Logic
        if primary_res.status == "FAILED" and comp_res.status == "PASSED":
            scope = "LOCAL_ENDPOINT_ISSUE"
            confidence = 0.96
            summary = f"Failure on {primary_device} while {comparison_device} succeeded. Root cause isolated to local endpoint."
        elif primary_res.status == "FAILED" and comp_res.status == "FAILED":
            scope = "INFRASTRUCTURE_GATEWAY_ISSUE"
            confidence = 0.98
            summary = f"Failure observed across both {primary_device} and {comparison_device}. Root cause isolated to shared infrastructure / gateway."
        else:
            scope = "LOCAL_ENDPOINT_ISSUE"
            confidence = 0.95
            summary = f"Normal execution across endpoints: Primary status {primary_res.status}, Comparison status {comp_res.status}."

        return CrossDeviceAnalysisResult(
            target_device=primary_device,
            comparison_device=comparison_device,
            target_probe_status=primary_res.status,
            comparison_probe_status=comp_res.status,
            isolation_scope=scope,
            confidence=confidence,
            summary=summary
        )
