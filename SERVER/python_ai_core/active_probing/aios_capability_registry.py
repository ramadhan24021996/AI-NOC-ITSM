"""
Capability Registry Module
Manages dynamic discovery, dependency graphs, and versioning of system capabilities.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any


@dataclass
class CapabilityRegistration:
    capability_name: str
    version: str
    owner_agent: str
    dependencies: List[str]
    description: str
    required_privilege: str = "NORMAL"   # "NORMAL", "ADMIN", "ROOT", "WMI", "SSH"


class AIOSCapabilityRegistry:
    """Registry managing capability discovery, versioning, privilege verification, and dependency tracking."""

    def __init__(self):
        self.capabilities: Dict[str, CapabilityRegistration] = {}
        self._initialize_baseline_capabilities()

    def _initialize_baseline_capabilities(self):
        self.register_capability(CapabilityRegistration(
            capability_name="ActiveDiagnosticProbing",
            version="2.1.0",
            owner_agent="ProbeExecutorAgent",
            dependencies=["ProbeSandbox", "ProbeBudget"],
            description="Executes L1-L4 active diagnostic network probes",
            required_privilege="ADMIN"
        ))
        self.register_capability(CapabilityRegistration(
            capability_name="CounterfactualSimulation",
            version="1.4.0",
            owner_agent="CausalIntelligenceAgent",
            dependencies=["StructuralCausalModel"],
            description="Performs multi-scenario do-operator counterfactual simulations",
            required_privilege="NORMAL"
        ))

    def register_capability(self, reg: CapabilityRegistration):
        self.capabilities[reg.capability_name] = reg

    def discover_capability(self, capability_name: str) -> Optional[CapabilityRegistration]:
        return self.capabilities.get(capability_name)

    def verify_agent_privilege(self, capability_name: str, agent_privilege: str) -> bool:
        """
        Verifies whether the target agent/relay has sufficient privileges (e.g. ADMIN/ROOT) to execute capability.
        """
        cap = self.discover_capability(capability_name)
        if not cap:
            return False
        
        req = cap.required_privilege.upper()
        agent_p = agent_privilege.upper()

        if req in ["NORMAL"]:
            return True
        if req in ["ADMIN", "ROOT"] and agent_p in ["ADMIN", "ROOT", "SYSTEM"]:
            return True
        if req == agent_p:
            return True

        return False
