"""
Fusion Orchestrator Module
Master entry point and orchestrator for the Enterprise Multi-Modal Temporal Cross-Correlation Engine.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Any, Optional
import logging
from .event_normalizer import EventNormalizer, NormalizedEvent
from .event_deduplicator import EventDeduplicator
from .temporal_window import TemporalWindowEngine, TemporalWindow
from .incident_cluster import IncidentClusterEngine, IncidentCluster
from .correlation_engine import CrossCorrelationEngine, CorrelationResult
from .causal_inference import CausalInferenceEngine, CausalChain
from .confidence_engine import ConfidenceEngine, HypothesisRank
from .graph_builder import IncidentGraphBuilder, IncidentEventGraph

logger = logging.getLogger(__name__)


@dataclass
class FusionResult:
    incident_cluster: IncidentCluster
    correlation_result: CorrelationResult
    causal_chain: CausalChain
    hypothesis_ranks: List[HypothesisRank]
    event_graph: IncidentEventGraph
    graphrag_prompt_context: str


class FusionOrchestrator:
    def __init__(self, window_size_seconds: float = 30.0, deduplicate_window_seconds: float = 1.5):
        self.normalizer = EventNormalizer()
        self.deduplicator = EventDeduplicator(window_seconds=deduplicate_window_seconds)
        self.window_engine = TemporalWindowEngine(window_size_seconds=window_size_seconds)
        self.cluster_engine = IncidentClusterEngine()
        self.correlation_engine = CrossCorrelationEngine()
        self.causal_engine = CausalInferenceEngine()
        self.confidence_engine = ConfidenceEngine()
        self.graph_builder = IncidentGraphBuilder()

    def process_raw_event(self, raw_payload: Dict[str, Any]) -> Optional[FusionResult]:
        """
        Processes a single raw event payload through the entire Fusion Stream pipeline.
        Returns a complete FusionResult when a temporal window boundary completes.
        """
        # 1. Normalize
        normalized_evt = self.normalizer.normalize(raw_payload)

        # 2. Deduplicate
        is_dup, count = self.deduplicator.is_duplicate(normalized_evt)
        if is_dup:
            logger.debug(f"[FusionStream] Suppressed duplicate event burst ({count}x): {normalized_evt.event_code}")

        # 3. Add to Temporal Window Buffer
        window = self.window_engine.add_event(normalized_evt)

        # 4. If window completes, process fusion pipeline
        if window:
            return self.process_temporal_window(window)

        return None

    def process_temporal_window(self, window: TemporalWindow) -> FusionResult:
        """
        Processes a completed temporal window through clustering, correlation, causal inference, and graph building.
        """
        # Cluster
        cluster = self.cluster_engine.cluster_window(window)

        # Correlate
        corr_result = self.correlation_engine.correlate(cluster)

        # Infer Causality
        causal_chain = self.causal_engine.infer_causal_chain(cluster, corr_result)

        # Rank Hypotheses
        ranks = self.confidence_engine.rank_hypotheses(causal_chain, window.events)

        # Build Graph
        graph = self.graph_builder.build_graph(causal_chain, window.events)

        logger.info(f"[FusionStream] Successfully synthesized FusionResult for cluster '{cluster.cluster_id}' with {len(window.events)} events. Root cause: {causal_chain.root_cause_event.event_code}")

        return FusionResult(
            incident_cluster=cluster,
            correlation_result=corr_result,
            causal_chain=causal_chain,
            hypothesis_ranks=ranks,
            event_graph=graph,
            graphrag_prompt_context=graph.graphrag_context
        )

    def force_flush(self) -> List[FusionResult]:
        """
        Flushes all active temporal windows and returns completed FusionResults.
        """
        results = []
        windows = self.window_engine.flush_all()
        for win in windows:
            res = self.process_temporal_window(win)
            results.append(res)
        return results
