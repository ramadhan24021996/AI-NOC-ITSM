"""
SERVER.enterprise.capability_registry - Agent Capability Registry
Declarative registry of what each agent type is capable of.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Optional

@dataclass
class AgentCapability:
    agent_id: str
    agent_type: str
    capabilities: List[str]
    max_risk_level: str
    requires_hitl_for: List[str] = field(default_factory=list)
    description: str = ""

class CapabilityRegistry:
    """In-memory capability registry for agent types."""
    def __init__(self):
        self._registry: Dict[str, AgentCapability] = {}

    def register(self, capability: AgentCapability) -> None:
        self._registry[capability.agent_id] = capability

    def get(self, agent_id: str) -> Optional[AgentCapability]:
        return self._registry.get(agent_id)

    def list_all(self) -> List[AgentCapability]:
        return list(self._registry.values())

    def can_perform(self, agent_id: str, capability: str) -> bool:
        cap = self._registry.get(agent_id)
        return cap is not None and capability in cap.capabilities
