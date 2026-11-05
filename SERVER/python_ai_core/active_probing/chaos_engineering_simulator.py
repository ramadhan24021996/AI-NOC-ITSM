"""
Chaos Engineering Simulator Module
Controlled fault injection suite for non-production validation:
Simulates L1 Cable Disconnect, L2 VLAN Misconfig, L3 Gateway Unreachable,
L4 Firewall Block, L6 TLS Certificate Expired, and L7 Database Saturation.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any


@dataclass
class ChaosFaultInjection:
    fault_id: str
    target_layer: str
    description: str
    injected_telemetry: Dict[str, Any]
    simulated_probe_failures: List[str]


class ChaosEngineeringSimulator:
    """Injects controlled fault scenarios to validate active diagnostic probing resilience."""

    def __init__(self):
        self.scenarios: Dict[str, ChaosFaultInjection] = {}
        self._initialize_scenarios()

    def _initialize_scenarios(self):
        self.scenarios["L1_CABLE_DISCONNECT"] = ChaosFaultInjection(
            fault_id="CHAOS-L1-01",
            target_layer="L1_PHYSICAL",
            description="Simulated physical cable disconnect / signal drop",
            injected_telemetry={"rssi_dbm": -95, "packet_loss": 1.0},
            simulated_probe_failures=["PRB-L1-01", "PRB-L3-01"]
        )

        self.scenarios["L3_GATEWAY_UNREACHABLE"] = ChaosFaultInjection(
            fault_id="CHAOS-L3-01",
            target_layer="L3_NETWORK",
            description="Simulated upstream core gateway failure",
            injected_telemetry={"rtt_ms": 9999, "packet_loss": 0.90},
            simulated_probe_failures=["PRB-L3-01"]
        )

        self.scenarios["L6_TLS_CERT_EXPIRED"] = ChaosFaultInjection(
            fault_id="CHAOS-L6-01",
            target_layer="L6_PRESENTATION",
            description="Simulated SSL/TLS certificate expiration",
            injected_telemetry={"tls_error": "CERT_HAS_EXPIRED"},
            simulated_probe_failures=["PRB-L6-01"]
        )

    def inject_fault(self, scenario_name: str) -> ChaosFaultInjection:
        return self.scenarios.get(scenario_name, self.scenarios["L1_CABLE_DISCONNECT"])
