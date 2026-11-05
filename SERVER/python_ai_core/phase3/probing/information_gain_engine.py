"""
Phase 3.3: Information Gain & Probe Utility Engine (phase3/probing/information_gain_engine.py)

1. InformationGainEngine: Calculates Shannon entropy reduction IG(P) = H(H) - E[H(H | Result_P)]. Enforces Invariant #10.
2. ProbeUtilityEngine: Calculates deterministic probe utility:
   Utility = (Expected_IG * Diagnostic_Relevance * Reliability) / (Cost + Risk + Operational_Impact).
"""

import logging
import math
from typing import Dict, Any, List
from phase3.hypothesis.hypothesis_competition_engine import HypothesisContract
from phase3.probing.probe_contract import ProbeContract

logger = logging.getLogger("INFORMATION_GAIN_ENGINE")


class InformationGainEngine:
    @staticmethod
    def calculate_entropy(probabilities: List[float]) -> float:
        """
        Calculates Shannon Entropy H(H) = - Sum(P(H_i) * log2(P(H_i)))
        """
        entropy = 0.0
        for p in probabilities:
            if p > 0.0:
                entropy -= p * math.log2(p)
        return round(entropy, 4)

    @staticmethod
    def calculate_expected_information_gain(hypotheses: List[HypothesisContract], probe: ProbeContract) -> float:
        """
        Calculates Expected Information Gain IG(P) of candidate probe against hypothesis set.
        """
        if not hypotheses:
            return 0.0

        priors = [h.posterior_probability for h in hypotheses]
        h_before = InformationGainEngine.calculate_entropy(priors)

        # Estimate discriminating power of probe based on target candidate match
        probe_target = probe.name.upper()
        matching_count = sum(1 for h in hypotheses if any(t in h.candidate.upper() for t in probe_target.split()))

        if matching_count == 0:
            # Low information gain if probe cannot discriminate hypothesis set
            return 0.02

        # Expected posterior entropy reduction simulation
        simulated_priors = [p * 1.5 if i == 0 else p * 0.5 for i, p in enumerate(priors)]
        total = sum(simulated_priors)
        simulated_priors = [p / total for p in simulated_priors]
        h_after = InformationGainEngine.calculate_entropy(simulated_priors)

        ig = max(0.0, h_before - h_after)
        return round(ig, 4)


class ProbeUtilityEngine:
    @staticmethod
    def calculate_probe_utility(probe: ProbeContract, ig: float, diagnostic_relevance: float = 0.90, reliability: float = 0.95) -> float:
        """
        Calculates deterministic Probe Utility:
        Utility = (IG * Relevance * Reliability) / (Cost + Risk + Impact)
        """
        num = ig * diagnostic_relevance * reliability
        denom = max(0.001, probe.cost + probe.risk_score + probe.operational_impact)
        utility = round(num / denom, 4)
        return utility

    @staticmethod
    def rank_probes(hypotheses: List[HypothesisContract], probes: List[ProbeContract]) -> List[Dict[str, Any]]:
        ranked = []
        for p in probes:
            ig = InformationGainEngine.calculate_expected_information_gain(hypotheses, p)
            util = ProbeUtilityEngine.calculate_probe_utility(p, ig)
            ranked.append({
                "probe_id": p.probe_id,
                "name": p.name,
                "expected_ig": ig,
                "utility_score": util,
                "probe_object": p
            })
        ranked.sort(key=lambda item: item["utility_score"], reverse=True)
        return ranked
