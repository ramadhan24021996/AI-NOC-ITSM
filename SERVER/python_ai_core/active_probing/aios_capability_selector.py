"""
Capability Selector Module
Evaluates performance ratings, confidence scores, and execution costs to select optimal capabilities.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from .aios_capability_registry import AIOSCapabilityRegistry, CapabilityRegistration


@dataclass
class CapabilityMarketplaceProfile:
    capability_name: str
    performance_score: float   # 0.0 to 100.0
    confidence_rating: float   # 0.0 to 1.0
    execution_cost_usd: float


class AIOSCapabilitySelector:
    """Selects the optimal capability based on performance metrics, confidence, and cost."""

    def __init__(self, registry: AIOSCapabilityRegistry):
        self.registry = registry
        self.marketplace_profiles: Dict[str, CapabilityMarketplaceProfile] = {
            "ActiveDiagnosticProbing": CapabilityMarketplaceProfile("ActiveDiagnosticProbing", 96.5, 0.98, 0.02),
            "CounterfactualSimulation": CapabilityMarketplaceProfile("CounterfactualSimulation", 94.0, 0.92, 0.05)
        }

    def select_optimal_capability(
        self,
        candidate_names: List[str]
    ) -> CapabilityMarketplaceProfile:

        profiles = [
            self.marketplace_profiles.get(name, CapabilityMarketplaceProfile(name, 80.0, 0.80, 0.10))
            for name in candidate_names
        ]

        # Highest (performance * confidence) / cost
        return sorted(profiles, key=lambda p: (p.performance_score * p.confidence_rating) / (p.execution_cost_usd + 0.001), reverse=True)[0]
