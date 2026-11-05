"""
SERVER.orchestrator.cognitive.conflict_resolver
================================================
Component: Conflict Resolver

Detects and resolves metric discrepancies between disparate data sources:
Example: Netdata CPU 20% vs Agent CPU 98% -> Selects higher-authority Agent/Probe
and produces ConflictResolutionResult explanation.
"""
import logging
from typing import Dict, Any
from SERVER.contracts.schemas import ConflictResolutionResult

logger = logging.getLogger("orchestrator.cognitive.conflict")


class ConflictResolver:
    """
    Resolves telemetry / metric discrepancies between sources based on source authority.
    """

    # Source authority priority ranking
    AUTHORITY_RANK = {
        "agent": 100,
        "active_probe": 90,
        "netdata": 80,
        "user_claim": 50,
    }

    def resolve_telemetry_conflict(
        self, telemetry_context: Dict[str, Any]
    ) -> ConflictResolutionResult:
        netdata_cpu = telemetry_context.get("netdata_cpu_usage")
        agent_cpu = telemetry_context.get("agent_cpu_usage") or telemetry_context.get("cpu_usage")

        if netdata_cpu is not None and agent_cpu is not None:
            try:
                v_netdata = float(netdata_cpu)
                v_agent = float(agent_cpu)
                if abs(v_netdata - v_agent) > 30.0:  # Significant discrepancy (>30%)
                    # Resolve to higher-authority Agent measurement
                    explanation = (
                        f"Konflik metrik dideteksi: Netdata mencatat CPU {v_netdata}% vs Agent mencatat CPU {v_agent}%. "
                        "Menggunakan pengukuran Host Agent (otoritas lebih tinggi)."
                    )
                    logger.info(f"[ConflictResolver] Conflict resolved: {explanation}")
                    return ConflictResolutionResult(
                        has_conflict=True,
                        resolved_value=v_agent,
                        authority_source="Host Agent",
                        explanation=explanation,
                    )
            except (ValueError, TypeError):
                pass

        return ConflictResolutionResult(has_conflict=False)
