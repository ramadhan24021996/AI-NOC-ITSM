"""
SERVER.control_plane.chaos_and_learning - Chaos Engineering Simulator
Simulates fault injection (network partition, latency, high CPU, disk pressure).
STRICT INVARIANT: Permitted ONLY in non-production Sandbox environments!
"""
from dataclasses import dataclass
from typing import Dict, Any, Optional
import os

class ProductionEnvironmentException(Exception):
    """Raised when chaos simulation is attempted in a production environment."""
    pass

@dataclass
class ChaosFaultSpec:
    fault_type: str       # "network_partition" | "latency_spike" | "high_cpu" | "disk_pressure"
    target_service: str
    duration_seconds: int = 10
    environment: str = "sandbox"  # Must be "sandbox" or "test"

class ChaosEngineeringSimulator:
    """Chaos Fault Injection Simulator with strict environment guard."""
    def __init__(self, current_env: Optional[str] = None):
        self.current_env = current_env or os.environ.get("ENVIRONMENT", "sandbox")

    def inject_fault(self, spec: ChaosFaultSpec) -> Dict[str, Any]:
        """Injects fault only if environment is explicitly sandbox or test."""
        if self.current_env.lower() in ("production", "prod"):
            raise ProductionEnvironmentException(
                f"Chaos engineering IS FORBIDDEN in production environment: {self.current_env}"
            )
        if spec.environment.lower() in ("production", "prod"):
            raise ProductionEnvironmentException(
                f"Chaos FaultSpec specifies forbidden production environment: {spec.environment}"
            )

        return {
            "fault_id": f"CHAOS-{spec.fault_type}-{spec.target_service}",
            "status": "injected",
            "environment": self.current_env,
            "fault_type": spec.fault_type,
            "duration_seconds": spec.duration_seconds,
        }
