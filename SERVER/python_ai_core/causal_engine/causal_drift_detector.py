"""
Causal Drift Detector Module
Detects topological drift when old causal edges no longer match recent observations.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Tuple, Optional
from .causal_graph import CausalGraph


@dataclass
class DriftReport:
    cause: str
    effect: str
    historical_probability: float
    recent_observation_rate: float
    drift_detected: bool
    recommended_action: str   # "RENAME_EDGE", "DECAY_WEIGHT", "REMOVE_EDGE"


class CausalDriftDetector:
    def __init__(self, causal_graph: CausalGraph):
        self.graph = causal_graph
        self._recent_observations: Dict[Tuple[str, str], List[bool]] = {}

    def record_observation(self, cause: str, effect: str, effect_occurred: bool):
        """Records recent observation of whether effect occurred following cause"""
        key = (cause, effect)
        if key not in self._recent_observations:
            self._recent_observations[key] = []
        self._recent_observations[key].append(effect_occurred)
        # Keep last 50 observations
        if len(self._recent_observations[key]) > 50:
            self._recent_observations[key].pop(0)

    def detect_drift(self, cause: str, effect: str) -> DriftReport:
        """
        Detects if edge probability has drifted significantly from historical baseline.
        """
        key = (cause, effect)
        obs = self._recent_observations.get(key, [])
        if len(obs) < 5:
            return DriftReport(cause, effect, 0.90, 0.90, False, "INSUFFICIENT_DATA")

        recent_rate = float(sum(obs)) / float(len(obs))

        hist_prob = 0.90
        if cause in self.graph.outgoing_edges:
            for e in self.graph.outgoing_edges[cause]:
                if e.effect == effect:
                    hist_prob = e.probability

        drift = abs(hist_prob - recent_rate) > 0.30

        action = "DECAY_WEIGHT" if drift else "NO_ACTION"

        return DriftReport(
            cause=cause,
            effect=effect,
            historical_probability=hist_prob,
            recent_observation_rate=round(recent_rate, 2),
            drift_detected=drift,
            recommended_action=action
        )
