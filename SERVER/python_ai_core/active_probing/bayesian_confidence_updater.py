"""
Bayesian Confidence Updater Module
Implements sequential Bayesian posterior confidence calculation:
P(H | E) = (P(E | H) * P(H)) / P(E)
Updates hypothesis confidence step-by-step as evidence is observed.
"""

from dataclasses import dataclass
from typing import Dict, Any


@dataclass
class BayesianUpdateResult:
    prior_confidence: float
    posterior_confidence: float
    probe_id: str
    probe_status: str
    likelihood: float
    evidence_probability: float


class BayesianConfidenceUpdater:
    """Calculates sequential Bayesian posterior updating for candidate hypotheses."""

    def update_hypothesis_confidence(
        self,
        prior_confidence: float,
        probe_id: str,
        probe_status: str,
        probe_sensitivity: float = 0.95,  # P(Probe FAILED | Hypothesis True)
        probe_false_positive_rate: float = 0.05  # P(Probe FAILED | Hypothesis False)
    ) -> BayesianUpdateResult:

        # Ensure prior is within bounds [0.01, 0.99]
        prior = max(min(prior_confidence, 0.99), 0.01)

        if probe_status == "FAILED":
            # Probe failed (anomaly observed):
            # Likelihood P(E=FAILED | H=True) = sensitivity
            likelihood = probe_sensitivity
            # P(E=FAILED | H=False) = false_positive_rate
            p_evidence = (likelihood * prior) + (probe_false_positive_rate * (1.0 - prior))
            posterior = (likelihood * prior) / p_evidence if p_evidence > 0 else prior
        elif probe_status == "PASSED":
            # Probe passed (normal observed):
            # Likelihood P(E=PASSED | H=True) = 1 - sensitivity
            likelihood = 1.0 - probe_sensitivity
            # P(E=PASSED | H=False) = 1 - false_positive_rate
            p_evidence = (likelihood * prior) + ((1.0 - probe_false_positive_rate) * (1.0 - prior))
            posterior = (likelihood * prior) / p_evidence if p_evidence > 0 else prior
        else:
            # SKIPPED or BLOCKED
            likelihood = 1.0
            p_evidence = 1.0
            posterior = prior

        posterior = round(max(min(posterior, 0.99), 0.01), 3)

        return BayesianUpdateResult(
            prior_confidence=prior,
            posterior_confidence=posterior,
            probe_id=probe_id,
            probe_status=probe_status,
            likelihood=likelihood,
            evidence_probability=p_evidence
        )
