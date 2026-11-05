"""
Telemetry Routing Module (routers/telemetry_router.py)

Routes telemetry streams to log stream compactor and anomaly detectors.
"""
import logging
from typing import Dict, Any

logger = logging.getLogger("TELEMETRY_ROUTER")


class TelemetryRouter:
    """Routes telemetry metrics to appropriate AI engines."""

    def route_telemetry(self, device_id: str, metric_class: str, payload: Dict[str, Any]) -> str:
        target_engine = "causal_dag_engine"
        if metric_class.upper() in {"CPU", "MEMORY", "DISK"}:
            target_engine = "telemetry_log_index_engine"
        elif metric_class.upper() in {"DNS", "DHCP", "TCP"}:
            target_engine = "rag_engine"
        logger.info(f"[TELEMETRY_ROUTER] Routed telemetry for {device_id} ({metric_class}) to {target_engine}")
        return target_engine
