"""
Enterprise Graph Configuration Registry
Centralized registry for weights, thresholds, policies, timeouts, retries, ranking weights, and cache TTLs.
"""

import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("GRAPH_CONFIG_REGISTRY")

DEFAULT_GRAPH_CONFIG = {
    "node_criticality_weight": 0.15,
    "telemetry_anomaly_weight": 0.25,
    "historical_failure_weight": 0.10,
    "time_decay_half_life_min": 60.0,
    "traversal_cutoff_depth": 4,
    "cache_ttl_sec": 300,
    "hitl_confidence_threshold": 0.80,
    "auto_execute_confidence_threshold": 0.95,
    "max_retry_attempts": 3,
    "circuit_breaker_error_threshold": 5
}

class GraphConfigRegistry:
    """
    Centralized Configuration Registry
    Prevents hardcoded configuration values across python AI core services.
    """

    def __init__(self, custom_config: Optional[Dict[str, Any]] = None):
        self.config = {**DEFAULT_GRAPH_CONFIG, **(custom_config or {})}

    def get(self, key: str, default: Any = None) -> Any:
        return self.config.get(key, default)

    def set(self, key: str, value: Any):
        self.config[key] = value
        logger.info("[CONFIG REGISTRY] Updated config parameter %s = %s", key, value)
