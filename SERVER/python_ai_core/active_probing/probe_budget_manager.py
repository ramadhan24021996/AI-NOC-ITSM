"""
Probe Budget Manager Module
Enforces resource limits per incident investigation:
Max ReadOnly probes (20), Max Active probes (5), Max High Risk (0 without HITL), Max Time (60s).
"""

from dataclasses import dataclass, field
from typing import Dict, Any
import time
from .probe_catalog import DiagnosticProbe, RiskLevel


@dataclass
class ProbeBudget:
    max_readonly_probes: int = 20
    max_active_probes: int = 5
    max_high_risk_probes: int = 0      # Requires HITL to exceed 0
    max_investigation_time_sec: float = 60.0

    readonly_probes_used: int = 0
    active_probes_used: int = 0
    high_risk_probes_used: int = 0
    start_time: float = field(default_factory=time.time)

    def elapsed_time_sec(self) -> float:
        return time.time() - self.start_time

    def is_time_exhausted(self) -> bool:
        return self.elapsed_time_sec() >= self.max_investigation_time_sec

    def can_execute(self, probe: DiagnosticProbe, hitl_approved: bool = False) -> tuple[bool, str]:
        if self.is_time_exhausted():
            return False, f"Investigation time budget exhausted ({round(self.elapsed_time_sec(), 1)}s >= {self.max_investigation_time_sec}s)"

        if probe.risk_level == RiskLevel.LEVEL_1_READ_ONLY:
            if self.readonly_probes_used >= self.max_readonly_probes:
                return False, f"ReadOnly probe budget exhausted ({self.readonly_probes_used}/{self.max_readonly_probes})"
        elif probe.risk_level in (RiskLevel.LEVEL_2_LOW_RISK, RiskLevel.LEVEL_3_MEDIUM_RISK):
            if self.active_probes_used >= self.max_active_probes:
                return False, f"Active probe budget exhausted ({self.active_probes_used}/{self.max_active_probes})"
        elif probe.risk_level == RiskLevel.LEVEL_4_HIGH_RISK:
            if not hitl_approved and self.high_risk_probes_used >= self.max_high_risk_probes:
                return False, "High-Risk Level 4 probe requires Human-in-the-Loop approval"

        return True, "BUDGET_AVAILABLE"

    def record_execution(self, probe: DiagnosticProbe):
        if probe.risk_level == RiskLevel.LEVEL_1_READ_ONLY:
            self.readonly_probes_used += 1
        elif probe.risk_level in (RiskLevel.LEVEL_2_LOW_RISK, RiskLevel.LEVEL_3_MEDIUM_RISK):
            self.active_probes_used += 1
        elif probe.risk_level == RiskLevel.LEVEL_4_HIGH_RISK:
            self.high_risk_probes_used += 1

    def status_summary(self) -> Dict[str, Any]:
        return {
            "readonly_used": f"{self.readonly_probes_used}/{self.max_readonly_probes}",
            "active_used": f"{self.active_probes_used}/{self.max_active_probes}",
            "high_risk_used": f"{self.high_risk_probes_used}/{self.max_high_risk_probes}",
            "elapsed_time_sec": round(self.elapsed_time_sec(), 2),
            "time_budget_sec": self.max_investigation_time_sec,
            "budget_exhausted": self.is_time_exhausted() or (
                self.readonly_probes_used >= self.max_readonly_probes and
                self.active_probes_used >= self.max_active_probes
            )
        }
