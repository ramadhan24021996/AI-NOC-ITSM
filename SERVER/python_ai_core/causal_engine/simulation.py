"""
Parallel Simulation Runner Module
Runs parallel counterfactual simulations across multi-agent domains.
"""

from typing import Dict, List, Any
from .counterfactual import CounterfactualSimulator
from .intervention import VirtualInterventionRunner, AgentIntervention


class ParallelSimulationRunner:
    def __init__(self):
        self.runner = VirtualInterventionRunner()

    def run_simulations(self, real_world_state: Dict[str, Any], primary_symptom: str = "POS_Error") -> List[AgentIntervention]:
        return self.runner.run_multi_agent_interventions(real_world_state, primary_symptom)
