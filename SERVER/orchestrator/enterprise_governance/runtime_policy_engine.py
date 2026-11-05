"""
SERVER.orchestrator.enterprise_governance.runtime_policy_engine
================================================================
Component: Runtime Policy Engine

Evaluates dynamic YAML operational policies without requiring code redeployment:
  autonomous_execution:
    LOW: true
    MEDIUM: false
    HIGH: false
  maintenance_window:
    start: 22:00
    end: 04:00
  approval:
    restart_database: required
  max_parallel_investigation: 5
"""
import logging
from typing import Dict, Any
from SERVER.contracts.schemas import RuntimePolicyConfig

logger = logging.getLogger("orchestrator.governance.policy")


class RuntimePolicyEngine:
    """
    Evaluates runtime policies dynamically to control AI execution boundaries.
    """

    def __init__(self):
        self._config = RuntimePolicyConfig()

    def get_active_policy(self) -> RuntimePolicyConfig:
        return self._config

    def update_policy(self, updates: Dict[str, Any]) -> RuntimePolicyConfig:
        for k, v in updates.items():
            if hasattr(self._config, k):
                setattr(self._config, k, v)
        logger.info(f"[RuntimePolicyEngine] Policy updated: {updates}")
        return self._config

    def is_action_allowed_autonomously(self, risk_level: str) -> bool:
        if risk_level == "LOW":
            return self._config.autonomous_execution_low
        elif risk_level == "MEDIUM":
            return self._config.autonomous_execution_med
        return self._config.autonomous_execution_high
