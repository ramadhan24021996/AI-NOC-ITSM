"""
Cross Correlation Engine Module
Calculates cross-modal correlation scores and dependency weights across event pairs.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Tuple, Any
from datetime import datetime
from .event_normalizer import NormalizedEvent, ModalityType, SeverityLevel
from .incident_cluster import IncidentCluster


@dataclass
class EventPairCorrelation:
    source_event_id: str
    target_event_id: str
    time_delta_ms: float
    correlation_score: float
    cause_direction: str  # "SOURCE_PRECEDES_TARGET" or "PARALLEL"


@dataclass
class CorrelationResult:
    cluster_id: str
    top_correlated_pairs: List[EventPairCorrelation]
    root_event_candidate: NormalizedEvent
    overall_confidence: float


class CrossCorrelationEngine:
    def __init__(self):
        # Modality Precedence Weights (Higher weight = higher likelihood of being root cause)
        self.modality_weights: Dict[str, float] = {
            "HARDWARE": 1.0,
            "NETWORK": 0.95,
            "OS": 0.85,
            "SECURITY": 0.80,
            "APPLICATION": 0.70,
            "BROWSER": 0.50,
            "USER": 0.40
        }

    def correlate(self, cluster: IncidentCluster) -> CorrelationResult:
        """
        Calculates correlation matrix across all events in an incident cluster.
        """
        events = sorted(cluster.event_sequence, key=lambda x: x.timestamp)
        if not events:
            dummy_evt = NormalizedEvent(
                event_id="EMPTY", timestamp="", device_id=cluster.primary_device_id,
                layer="L4", modality=ModalityType.APPLICATION, source="SYSTEM",
                event_code="NO_EVENT", severity=SeverityLevel.INFO
            )
            return CorrelationResult(cluster.cluster_id, [], dummy_evt, 0.0)

        pairs: List[EventPairCorrelation] = []

        # Compare adjacent and pair events
        for i in range(len(events)):
            for j in range(i + 1, len(events)):
                e1 = events[i]
                e2 = events[j]

                t1 = self._parse_ts(e1.timestamp)
                t2 = self._parse_ts(e2.timestamp)
                dt_ms = abs((t2 - t1).total_seconds() * 1000.0)

                # Time decay score (1.0 for 0ms, down to 0.1 for 30,000ms)
                time_score = max(0.05, 1.0 - (dt_ms / 30000.0))

                # Modality affinity score
                m1_name = e1.modality.value if isinstance(e1.modality, Enum) else str(e1.modality)
                m2_name = e2.modality.value if isinstance(e2.modality, Enum) else str(e2.modality)
                w1 = self.modality_weights.get(m1_name, 0.5)
                w2 = self.modality_weights.get(m2_name, 0.5)

                score = round(time_score * 0.6 + ((w1 + w2) / 2.0) * 0.4, 4)

                direction = "SOURCE_PRECEDES_TARGET" if t1 <= t2 else "TARGET_PRECEDES_SOURCE"

                pairs.append(EventPairCorrelation(
                    source_event_id=e1.event_id,
                    target_event_id=e2.event_id,
                    time_delta_ms=dt_ms,
                    correlation_score=score,
                    cause_direction=direction
                ))

        # Root event candidate is the earliest event with highest modality weight
        root_candidate = events[0]
        max_root_score = -1.0
        for e in events:
            m_name = e.modality.value if isinstance(e.modality, Enum) else str(e.modality)
            weight = self.modality_weights.get(m_name, 0.5)
            # Add severity bonus
            sev_bonus = 0.3 if e.severity in [SeverityLevel.HIGH, SeverityLevel.CRITICAL] else 0.0
            total_score = weight + sev_bonus
            if total_score > max_root_score:
                max_root_score = total_score
                root_candidate = e

        overall_conf = min(0.99, max(0.50, max_root_score * 0.85))

        return CorrelationResult(
            cluster_id=cluster.cluster_id,
            top_correlated_pairs=sorted(pairs, key=lambda x: x.correlation_score, reverse=True)[:10],
            root_event_candidate=root_candidate,
            overall_confidence=overall_conf
        )

    def _parse_ts(self, iso_str: str) -> datetime:
        try:
            clean_str = iso_str.replace("Z", "+00:00")
            return datetime.fromisoformat(clean_str)
        except Exception:
            return datetime.now()
