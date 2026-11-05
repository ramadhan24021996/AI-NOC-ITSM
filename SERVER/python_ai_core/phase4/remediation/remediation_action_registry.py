"""
Phase 4.1 Remediation Action Registry (phase4/remediation/remediation_action_registry.py)

Registers structured ACTION_IDs for deterministic remediation contracts.
Blocks 100% arbitrary shell command string execution attempts from LLM.
"""

import dataclasses
import hashlib
import json
import logging
from typing import Dict, Any, Optional, List

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("REMEDIATION_ACTION_REGISTRY")


@dataclasses.dataclass
class ActionContract:
    action_id: str
    name: str
    description: str
    target_category: str
    execution_type: str  # e.g., RESTART_SERVICE, RELOAD_CONFIG, FAILOVER
    allowed_targets: List[str]
    default_risk: float
    default_blast_radius: int
    rollback_supported: bool
    action_hash: str = ""

    def __post_init__(self):
        if not self.action_hash:
            raw = f"{self.action_id}:{self.execution_type}:{self.default_risk}:{self.rollback_supported}"
            self.action_hash = hashlib.sha256(raw.encode("utf-8")).hexdigest()


class ActionRegistry:
    def __init__(self):
        self.actions: Dict[str, ActionContract] = {}
        self._register_default_actions()

    def _register_default_actions(self):
        defaults = [
            ActionContract("NET-DHCP-RESTART-001", "Restart DHCP Service", "Restarts DHCP daemon safely", "NETWORK", "RESTART_SERVICE", ["dhcp-service", "router", "srv-prod-db-01"], 0.20, 1, True),
            ActionContract("RESTART-APP-SERVICE-001", "Restart Application Service", "Restarts app service process", "APP", "RESTART_SERVICE", ["app", "server", "srv-prod-db-01"], 0.20, 1, True),
            ActionContract("RELOAD-CONFIG-001", "Reload Service Configuration", "Reloads config without process restart", "CONFIG", "RELOAD_CONFIG", ["app", "server", "srv-prod-db-01"], 0.10, 1, True),
            ActionContract("RESTART-DB-POOL-001", "Restart DB Connection Pool", "Restarts DB connection pooler", "DATABASE", "RESTART_POOL", ["db", "srv-prod-db-01"], 0.25, 1, True),
            ActionContract("FAILOVER-SECONDARY-001", "Failover to Secondary Node", "Triggers node failover", "CLUSTER", "FAILOVER", ["cluster", "srv-prod-db-01"], 0.40, 2, True),
        ]
        for a in defaults:
            self.actions[a.action_id] = a
            logger.debug(f"[ACTION REGISTRY] Registered Action ID: '{a.action_id}' ({a.name})")

    def lookup_action(self, action_id: str) -> Optional[ActionContract]:
        return self.actions.get(action_id)

    def is_registered(self, action_id: str) -> bool:
        return action_id in self.actions
