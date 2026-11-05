"""
SERVER.python_ai_core.cognition.remediation_delta_verifier
===========================================================
Post-Remediation Verification & Telemetry Delta Collector.
Compares Pre-vs-Post metrics (CPU delta, RAM delta, Spooler queue count)
to objectively verify if remediation succeeded, and records closed-loop feedback.
"""

import logging
import time
from dataclasses import dataclass, field
from typing import Dict, Any, Optional

logger = logging.getLogger("REMEDIATION_DELTA_VERIFIER")


@dataclass
class RemediationDeltaDTO:
    """DTO representing Pre vs Post Remediation Telemetry Delta."""
    incident_id: str
    device_id: str
    sop_id: str
    pre_cpu_pct: float
    post_cpu_pct: float
    pre_ram_pct: float
    post_ram_pct: float
    pre_spooler_count: int
    post_spooler_count: int
    is_verified_success: bool = False
    cpu_reduction_pct: float = 0.0
    ram_reduction_pct: float = 0.0
    verdict_summary: str = ""
    timestamp: str = field(default_factory=lambda: time.strftime("%Y-%m-%dT%H:%M:%SZ"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "incident_id": self.incident_id,
            "device_id": self.device_id,
            "sop_id": self.sop_id,
            "pre_cpu_pct": round(self.pre_cpu_pct, 2),
            "post_cpu_pct": round(self.post_cpu_pct, 2),
            "pre_ram_pct": round(self.pre_ram_pct, 2),
            "post_ram_pct": round(self.post_ram_pct, 2),
            "pre_spooler_count": self.pre_spooler_count,
            "post_spooler_count": self.post_spooler_count,
            "is_verified_success": self.is_verified_success,
            "cpu_reduction_pct": round(self.cpu_reduction_pct, 2),
            "ram_reduction_pct": round(self.ram_reduction_pct, 2),
            "verdict_summary": self.verdict_summary,
            "timestamp": self.timestamp,
        }


def safe_float(val: Any, default: float = 0.0) -> float:
    if val is None:
        return default
    try:
        return float(val)
    except (ValueError, TypeError):
        return default


def safe_int(val: Any, default: int = 0) -> int:
    if val is None:
        return default
    try:
        return int(val)
    except (ValueError, TypeError):
        return default


class RemediationDeltaVerifier:
    """Verifies remediation success by comparing Pre vs Post Telemetry."""

    @classmethod
    def verify_delta(
        cls,
        incident_id: str,
        device_id: str,
        sop_id: str,
        pre_telemetry: Dict[str, Any],
        post_telemetry: Dict[str, Any]
    ) -> RemediationDeltaDTO:
        """Calculates telemetry delta and evaluates remediation success."""
        raw_pre_cpu = pre_telemetry.get("cpu_usage_pct") if pre_telemetry.get("cpu_usage_pct") is not None else pre_telemetry.get("cpu", 0.0)
        pre_cpu = safe_float(raw_pre_cpu, 0.0)

        raw_post_cpu = post_telemetry.get("cpu_usage_pct") if post_telemetry.get("cpu_usage_pct") is not None else post_telemetry.get("cpu", 0.0)
        post_cpu = safe_float(raw_post_cpu, 0.0)

        raw_pre_ram = pre_telemetry.get("ram_usage_pct") if pre_telemetry.get("ram_usage_pct") is not None else pre_telemetry.get("memory", 0.0)
        pre_ram = safe_float(raw_pre_ram, 0.0)

        raw_post_ram = post_telemetry.get("ram_usage_pct") if post_telemetry.get("ram_usage_pct") is not None else post_telemetry.get("memory", 0.0)
        post_ram = safe_float(raw_post_ram, 0.0)

        pre_spool = safe_int(pre_telemetry.get("spooler_queue_count"), 0)
        post_spool = safe_int(post_telemetry.get("spooler_queue_count"), 0)

        cpu_diff = pre_cpu - post_cpu
        ram_diff = pre_ram - post_ram
        spool_cleared = pre_spool > 0 and post_spool == 0

        # Success conditions
        success = (cpu_diff > 10.0) or (ram_diff > 10.0) or spool_cleared or (post_cpu < 50.0 and post_ram < 80.0)

        summary = (
            f"Remediasi {sop_id} pada {device_id} Sukses: CPU {pre_cpu:.1f}% -> {post_cpu:.1f}%, "
            f"RAM {pre_ram:.1f}% -> {post_ram:.1f}%, Spooler Queue {pre_spool} -> {post_spool}."
        ) if success else (
            f"Remediasi {sop_id} pada {device_id} Belum Optimal: CPU {post_cpu:.1f}%, RAM {post_ram:.1f}%."
        )

        dto = RemediationDeltaDTO(
            incident_id=incident_id,
            device_id=device_id,
            sop_id=sop_id,
            pre_cpu_pct=pre_cpu,
            post_cpu_pct=post_cpu,
            pre_ram_pct=pre_ram,
            post_ram_pct=post_ram,
            pre_spooler_count=pre_spool,
            post_spooler_count=post_spool,
            is_verified_success=success,
            cpu_reduction_pct=cpu_diff,
            ram_reduction_pct=ram_diff,
            verdict_summary=summary,
        )

        logger.info(f"[REMEDIATION_VERIFIER] Incident {incident_id} ({device_id}): Success={success} | Summary='{summary}'")
        return dto
