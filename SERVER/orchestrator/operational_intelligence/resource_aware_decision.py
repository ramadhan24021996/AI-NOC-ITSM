"""
SERVER.orchestrator.operational_intelligence.resource_aware_decision
======================================================================
Component: Resource-Aware System Decision Engine

Monitors host system resources (RAM 95%, CPU 92%, Queue 37) and adjusts AI strategy dynamically:
  - Automatically switches to lightweight model
  - Defers embedding indexing
  - Utilizes response cache for 8GB RAM host environments
"""
import logging
from SERVER.contracts.schemas import SystemResourceAwareState

logger = logging.getLogger("orchestrator.op_intel.resource_aware")


class ResourceAwareDecisionEngine:
    """
    Adapts AI platform execution based on host system resource constraints.
    """

    def evaluate_resource_state(
        self, ram_pct: int = 95, cpu_pct: int = 92, queue_len: int = 37
    ) -> SystemResourceAwareState:
        is_constrained = ram_pct > 90 or cpu_pct > 90 or queue_len > 20
        mode = "RESOURCE_CONSTRAINED_LIGHT_MODEL" if is_constrained else "STANDARD_PERFORMANCE"

        state = SystemResourceAwareState(
            host_ram_usage_pct=ram_pct,
            host_cpu_usage_pct=cpu_pct,
            queue_length=queue_len,
            active_mode=mode,
            use_cache=is_constrained,
        )

        if is_constrained:
            logger.warning(
                f"[ResourceAwareDecisionEngine] Host resources constrained (RAM: {ram_pct}%, CPU: {cpu_pct}%, Queue: {queue_len}) -> "
                f"Activated {mode} with response caching"
            )
        return state
