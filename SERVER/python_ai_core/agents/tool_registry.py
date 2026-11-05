"""
Enterprise Tool Registry (Phase 3 Capability 5)
Registers all available diagnostic and remediation tools with metadata:
- Tool Name & Category
- Required Permissions (RBAC)
- Risk Score (0-100)
- Execution Timeout (seconds)
- Rollback Script Handler
- Supported Operating System Platforms
"""

import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger("TOOL_REGISTRY")

class ToolDefinition:
    def __init__(
        self,
        name: str,
        category: str,
        permission: str,
        risk_score: int,
        timeout_sec: int,
        rollback_tool: Optional[str] = None,
        platform: str = "ALL"
    ):
        self.name = name
        self.category = category
        self.permission = permission
        self.risk_score = risk_score
        self.timeout_sec = timeout_sec
        self.rollback_tool = rollback_tool
        self.platform = platform

class ToolRegistry:
    """
    Enterprise Central Tool Registry
    Enforces risk scoring and rollback availability for agent tools.
    """

    def __init__(self):
        self.tools: Dict[str, ToolDefinition] = {
            "ping": ToolDefinition("ping", "NETWORK", "READ_ONLY", risk_score=5, timeout_sec=5),
            "traceroute": ToolDefinition("traceroute", "NETWORK", "READ_ONLY", risk_score=5, timeout_sec=15),
            "dns_lookup": ToolDefinition("dns_lookup", "NETWORK", "READ_ONLY", risk_score=5, timeout_sec=5),
            "reset_switch_port": ToolDefinition("reset_switch_port", "NETWORK_L2", "ADMIN", risk_score=65, timeout_sec=10, rollback_tool="enable_switch_port"),
            "restart_service": ToolDefinition("restart_service", "OS", "SYSTEM_ADMIN", risk_score=45, timeout_sec=30, rollback_tool="start_service"),
            "flush_dns": ToolDefinition("flush_dns", "NETWORK_L3", "ADMIN", risk_score=20, timeout_sec=5),
            "clear_spooler": ToolDefinition("clear_spooler", "PRINTER", "ADMIN", risk_score=30, timeout_sec=15, rollback_tool="start_spooler")
        }

    def get_tool(self, tool_name: str) -> Optional[ToolDefinition]:
        """Retrieves tool definition by name."""
        return self.tools.get(tool_name.lower())

    def list_tools_by_risk(self, max_risk: int) -> List[ToolDefinition]:
        """Returns tools with risk score <= max_risk."""
        return [t for t in self.tools.values() if t.risk_score <= max_risk]
