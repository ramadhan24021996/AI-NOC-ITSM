"""
Time-Aware Causal Graph Module
Extends causal edges with propagation delay windows (e.g., max 5s propagation window).
Weakens causal strength if propagation delay exceeds expected threshold.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional
from datetime import datetime, timezone
import math


@dataclass
class TimeAwareCausalEdge:
    cause: str
    effect: str
    base_probability: float
    max_propagation_delay_sec: float = 15.0  # Max expected propagation window in seconds
    decay_rate: float = 0.05                  # Exponential decay rate per minute


class TimeAwareCausalGraph:
    def __init__(self):
        # (cause, effect) -> TimeAwareCausalEdge
        self._time_edges: Dict[Tuple[str, str], TimeAwareCausalEdge] = {}
        self._initialize_time_edges()

    def _initialize_time_edges(self):
        self.add_time_edge("RSSI", "PacketLoss", 0.95, max_propagation_delay_sec=5.0)
        self.add_time_edge("PacketLoss", "TCP_Retransmission", 0.92, max_propagation_delay_sec=10.0)
        self.add_time_edge("TCP_Retransmission", "DNS_Timeout", 0.90, max_propagation_delay_sec=15.0)
        self.add_time_edge("DNS_Timeout", "ConnectionTimeout", 0.88, max_propagation_delay_sec=15.0)
        self.add_time_edge("ConnectionTimeout", "HTTP_502", 0.85, max_propagation_delay_sec=20.0)

    def add_time_edge(self, cause: str, effect: str, base_prob: float, max_propagation_delay_sec: float = 15.0):
        self._time_edges[(cause, effect)] = TimeAwareCausalEdge(
            cause=cause,
            effect=effect,
            base_probability=base_prob,
            max_propagation_delay_sec=max_propagation_delay_sec
        )

    def calculate_effective_probability(self, cause: str, effect: str, actual_delay_sec: float) -> float:
        """
        Calculates time-decayed causal probability based on propagation delay.
        """
        edge = self._time_edges.get((cause, effect))
        if not edge:
            return 0.50

        if actual_delay_sec <= edge.max_propagation_delay_sec:
            return edge.base_probability

        # Calculate decay penalty for excessive delay (e.g. 30 minutes later)
        excess_seconds = actual_delay_sec - edge.max_propagation_delay_sec
        excess_minutes = excess_seconds / 60.0
        decay_factor = math.exp(-edge.decay_rate * excess_minutes)

        effective_prob = round(max(0.10, edge.base_probability * decay_factor), 2)
        return effective_prob
