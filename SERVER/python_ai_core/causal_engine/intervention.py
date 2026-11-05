"""
Virtual Intervention Runner Module
Executes agent-specific virtual interventions (Network Agent, DNS Agent, Browser Agent, App Agent).
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
from .counterfactual import CounterfactualSimulator, CounterfactualResult


@dataclass
class AgentIntervention:
    agent_name: str         # e.g. "NetworkAgent", "DNSAgent", "BrowserAgent", "AppAgent"
    target_variable: str    # e.g. "PacketLoss", "DNS_Timeout", "Chrome_Crash", "POS_Error"
    result: CounterfactualResult


class VirtualInterventionRunner:
    def __init__(self, simulator: Optional[CounterfactualSimulator] = None):
        self.simulator = simulator or CounterfactualSimulator()

    def run_multi_agent_interventions(
        self,
        real_world_state: Dict[str, Any],
        primary_symptom: str = "POS_Error"
    ) -> List[AgentIntervention]:
        """
        Runs parallel virtual interventions across domain agents.
        """
        agent_targets = [
            ("NetworkAgent", "PacketLoss"),
            ("NetworkAgent", "RSSI"),
            ("DNSAgent", "DNS_Timeout"),
            ("BrowserAgent", "Chrome_Crash"),
            ("AppAgent", "Printer_Offline"),
            ("AppAgent", "POS_Error"),
        ]

        interventions: List[AgentIntervention] = []

        for agent_name, var_name in agent_targets:
            if var_name in real_world_state:
                res = self.simulator.simulate_counterfactual(
                    target_variable=var_name,
                    real_world_state=real_world_state,
                    primary_symptom=primary_symptom
                )
                interventions.append(AgentIntervention(
                    agent_name=agent_name,
                    target_variable=var_name,
                    result=res
                ))

        return interventions
