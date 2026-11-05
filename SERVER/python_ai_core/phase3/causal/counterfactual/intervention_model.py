"""
Phase 3.5: Intervention Model (phase3/causal/counterfactual/intervention_model.py)

Defines "What-If" Interventions (e.g., Pearl's do-calculus intervention do(X = x_hypothetical)).
"""

import logging
from typing import Dict, Any, Optional
from phase3.causal.counterfactual.counterfactual_contract import CounterfactualIntervention

logger = logging.getLogger("INTERVENTION_MODEL")


class InterventionModel:
    @staticmethod
    def create_do_intervention(target_entity: str, variable_name: str, original_val: Any, hypothetical_val: Any) -> CounterfactualIntervention:
        """
        Creates a structured do(X = x_hypothetical) intervention contract.
        """
        inter = CounterfactualIntervention(
            target_entity=target_entity,
            variable_name=variable_name,
            original_value=original_val,
            hypothetical_value=hypothetical_val,
            intervention_type="DO_INTERVENTION"
        )
        logger.info(f"[INTERVENTION MODEL] Created intervention do({target_entity}.{variable_name} = {hypothetical_val}) [Original: {original_val}]")
        return inter
