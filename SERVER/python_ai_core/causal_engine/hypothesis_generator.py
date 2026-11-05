"""
Hypothesis Generator Module
Extracts anomalous variables from real-world incident state to generate root cause hypotheses.
"""

from typing import Dict, List, Any, Optional
from .scm import StructuralCausalModel


class HypothesisGenerator:
    def __init__(self, scm: Optional[StructuralCausalModel] = None):
        self.scm = scm or StructuralCausalModel()

    def generate_hypotheses(self, real_world_state: Dict[str, Any]) -> List[str]:
        """
        Returns list of variable names that are anomalous in real_world_state.
        """
        hypotheses = []
        for var_name, val in real_world_state.items():
            var = self.scm.get_variable(var_name)
            if var and val != var.default_normal_value:
                hypotheses.append(var_name)
        return hypotheses
