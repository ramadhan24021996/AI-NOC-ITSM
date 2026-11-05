"""
Causal Inference Engine Module
Infers causal relationships across multi-modal event timelines and isolates root causes from secondary symptoms.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Any
from .event_normalizer import NormalizedEvent
from .incident_cluster import IncidentCluster
from .correlation_engine import CorrelationResult


@dataclass
class CausalStep:
    step_number: int
    timestamp: str
    modality: str
    source: str
    event_code: str
    description: str


@dataclass
class CausalChain:
    cluster_id: str
    root_cause_event: NormalizedEvent
    causal_steps: List[CausalStep]
    narrative_summary: str
    suggested_rca: str
    affected_layer: str


class CausalInferenceEngine:
    def infer_causal_chain(self, cluster: IncidentCluster, corr_result: CorrelationResult) -> CausalChain:
        """
        Builds a chronological causal sequence from an incident cluster and correlation result.
        """
        events = sorted(cluster.event_sequence, key=lambda x: x.timestamp)
        steps: List[CausalStep] = []

        for idx, e in enumerate(events, start=1):
            m_val = e.modality.value if isinstance(e.modality, Enum) else str(e.modality)
            desc = f"[{m_val}] {e.source} reported {e.event_code} (Severity: {e.severity})"
            steps.append(CausalStep(
                step_number=idx,
                timestamp=e.timestamp,
                modality=m_val,
                source=e.source,
                event_code=e.event_code,
                description=desc
            ))

        root_evt = corr_result.root_event_candidate
        root_m = root_evt.modality.value if isinstance(root_evt.modality, Enum) else str(root_evt.modality)

        # Build human-readable narrative
        timeline_str = " -> ".join([f"{s.timestamp[11:19]} {s.event_code}" for s in steps[:5]])
        narrative = f"Incident initiated at {root_evt.timestamp} starting from {root_m} ({root_evt.source}). Chain: {timeline_str}"

        suggested_rca = f"Root cause identified in [{root_m}] layer from source '{root_evt.source}' (Event: {root_evt.event_code}). Secondary downstream errors in application/browser layers are consequential symptoms."

        return CausalChain(
            cluster_id=cluster.cluster_id,
            root_cause_event=root_evt,
            causal_steps=steps,
            narrative_summary=narrative,
            suggested_rca=suggested_rca,
            affected_layer=root_evt.layer
        )
