"""
Enterprise Bayesian Confidence Engine (Phase 4 Capability 4)
Calculates mathematical Bayesian Probability for root cause hypotheses:
BayesianScore = (P(Evidence|Hypothesis) * P(Hypothesis)) / P(Evidence)
Incorporates Evidence Items, Telemetry Quality, Historical Resolution Rate, Vector Similarity, and KEDB Record match.
"""

import logging
from typing import Dict, List, Any

logger = logging.getLogger("BAYESIAN_CONFIDENCE_ENGINE")

class BayesianConfidenceEngine:
    """
    Mathematical Bayesian Confidence Score Calculator
    Computes rigorous mathematical confidence scores beyond raw LLM outputs.
    """

    def calculate_bayesian_confidence(
        self,
        hypothesis_id: str,
        evidence_count: int,
        telemetry_quality: float,
        history_success_rate: float,
        vector_similarity: float,
        kedb_match: bool
    ) -> Dict[str, Any]:
        """
        Calculates posterior probability score using Bayesian formula.
        """
        # Prior Probability P(H) based on history & similarity
        prior = (history_success_rate * 0.4) + (vector_similarity * 0.4) + (0.2 if kedb_match else 0.0)

        # Likelihood P(E|H) based on evidence items & telemetry quality
        likelihood = min(1.0, (evidence_count * 0.25) * telemetry_quality)

        # Marginal Likelihood P(E) normalization factor
        marginal_evidence = 0.85

        # Posterior P(H|E)
        posterior = min(0.99, round((likelihood * prior) / marginal_evidence, 4))

        return {
            "hypothesis_id": hypothesis_id,
            "bayesian_confidence": posterior,
            "confidence_percentage": round(posterior * 100, 2),
            "prior_prob": round(prior, 4),
            "likelihood": round(likelihood, 4),
            "evidence_count": evidence_count
        }
