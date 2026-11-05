"""
Phase 4.1 Remediation Score Calculator (phase4/remediation/remediation_score_calculator.py)

Calculates 6-factor deterministic remediation score for candidates that passed Hard Safety Gate.
Enforces INVARIANT #29 (Safety Precedes Optimization).
Score Formula:
Score(R_k) = w1*CausalFit + w2*EvidenceSupport + w3*HistSuccess + w4*CFDelta - w5*Risk - w6*BlastRadius
"""

import logging
from typing import Dict, Any, Optional
from phase3.remediation.remediation_contract import RemediationContract
from phase4.remediation.remediation_scoring_policy import RemediationScoringPolicy

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("REMEDIATION_SCORE_CALCULATOR")


class RemediationScoreCalculator:
    def __init__(self, policy: Optional[RemediationScoringPolicy] = None):
        self.policy = policy or RemediationScoringPolicy()

    def calculate_score(
        self,
        contract: RemediationContract,
        causal_fit: float = 0.90,
        evidence_support: float = 0.85,
        historical_success: float = 0.90,
        counterfactual_delta: float = 0.80
    ) -> float:
        """
        Calculates 6-factor deterministic score:
        Score = w1*CF + w2*ES + w3*HS + w4*CFD - w5*Risk - w6*Blast
        """
        w1 = self.policy.w_causal_fit
        w2 = self.policy.w_evidence_support
        w3 = self.policy.w_historical_success
        w4 = self.policy.w_counterfactual_delta
        w5 = self.policy.w_risk
        w6 = self.policy.w_blast_radius

        risk_penalty = contract.risk_score
        blast_penalty = float(contract.blast_radius.get("max_affected_nodes", 1)) / float(self.policy.max_blast_radius)

        score = (w1 * causal_fit) + (w2 * evidence_support) + (w3 * historical_success) + (w4 * counterfactual_delta) - (w5 * risk_penalty) - (w6 * blast_penalty)
        score = max(0.0, min(1.0, round(score, 4)))

        logger.info(f"[SCORE CALCULATED] Candidate '{contract.contract_id}' Score: {score} (CausalFit={causal_fit}, EvidenceSupport={evidence_support}, Risk={risk_penalty})")
        return score
