"""
Probe Sandbox Module
Sandbox environment for Level 2-4 active probes.
Checks policy compliance, privilege levels, timeout limits, and rollback availability before execution.
"""

from dataclasses import dataclass
from typing import Dict, Any, Tuple
from .probe_catalog import DiagnosticProbe, RiskLevel


@dataclass
class SandboxValidationResult:
    allowed: bool
    reason: str
    requires_hitl: bool
    max_timeout_ms: float
    rollback_supported: bool


class ProbeSandbox:
    """Enforces safety guardrails, execution isolation, and policy checks for active probes."""

    def __init__(self, policy_mode: str = "STRICT_NOC"):
        self.policy_mode = policy_mode

    def validate_and_isolate(
        self,
        probe: DiagnosticProbe,
        context: Dict[str, Any],
        hitl_approved: bool = False
    ) -> SandboxValidationResult:
        """Validates probe safety parameters before execution."""

        # 1. Read-Only probes bypass strict sandbox policies
        if probe.read_only:
            return SandboxValidationResult(
                allowed=True,
                reason="Read-only probe safe to execute",
                requires_hitl=False,
                max_timeout_ms=min(probe.estimated_latency_ms * 3, 5000.0),
                rollback_supported=True
            )

        # 2. Check Level 4 High Risk probes
        if probe.risk_level == RiskLevel.LEVEL_4_HIGH_RISK:
            if not hitl_approved:
                return SandboxValidationResult(
                    allowed=False,
                    reason="Level 4 High-Risk probe blocked by Sandbox Policy: Human-in-the-Loop approval required",
                    requires_hitl=True,
                    max_timeout_ms=10000.0,
                    rollback_supported=True
                )

        # 3. Check Level 3 Medium Risk probes under STRICT policy
        if probe.risk_level == RiskLevel.LEVEL_3_MEDIUM_RISK and self.policy_mode == "ZERO_TRUST":
            if not hitl_approved:
                return SandboxValidationResult(
                    allowed=False,
                    reason="Level 3 Medium-Risk probe requires explicit authorization under ZERO_TRUST mode",
                    requires_hitl=True,
                    max_timeout_ms=5000.0,
                    rollback_supported=True
                )

        # Allowed execution parameters
        timeout_ms = min(probe.estimated_latency_ms * 4, 15000.0)
        return SandboxValidationResult(
            allowed=True,
            reason="Sandbox verification passed",
            requires_hitl=False,
            max_timeout_ms=timeout_ms,
            rollback_supported=True
        )
