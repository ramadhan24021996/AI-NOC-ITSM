"""
Tool Registry Service Interfaces for Enterprise AI Operations Platform
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from SERVER.shared.enums import ActionRiskLevel

@dataclass
class ToolManifest:
    tool_id: str
    name: str
    description: str
    version: str
    risk_level: ActionRiskLevel
    required_permissions: List[str] = field(default_factory=list)
    timeout_seconds: int = 30

class Tool(ABC):
    """Abstract interface for executable tools."""
    @property
    @abstractmethod
    def manifest(self) -> ToolManifest:
        pass

    @abstractmethod
    def execute(self, params: Dict[str, Any]) -> Dict[str, Any]:
        pass

class ToolExecutor(ABC):
    """Abstract interface for executing registered tools safely."""
    @abstractmethod
    def run_tool(self, tool_id: str, params: Dict[str, Any], user_role: str) -> Dict[str, Any]:
        pass

class PermissionChecker(ABC):
    """Abstract interface for evaluating tool permissions against RBAC."""
    @abstractmethod
    def check_permission(self, user_role: str, manifest: ToolManifest) -> bool:
        pass

class TimeoutManager(ABC):
    """Abstract interface for managing tool execution timeouts."""
    @abstractmethod
    def enforce_timeout(self, tool_id: str, timeout_seconds: int) -> None:
        pass
