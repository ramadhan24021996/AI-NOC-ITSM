"""
Master Enterprise Knowledge Pipeline Orchestrator Module
Orchestrates the entire closed-loop Knowledge Evolution Pipeline upon incident closure:
Incident Closed ──► Evidence Package ──► Knowledge Extraction ──► Memory Graph Evolution ──►
Causal Edge Evolution ──► Auto SOP Vault ──► 10-Stage Promotion ──► Multi-Graph Sync ──► Message Bus Event
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any

from .unified_evidence_package import EvidencePackageBuilder, UnifiedEvidencePackage
from .incident_knowledge_extractor import IncidentKnowledgeExtractor, StructuredKnowledgeObject
from .memory_graph_evolution import MemoryGraphEvolution, MemoryEvolutionReport
from .causal_graph_evolution import CausalGraphEvolution, CausalEdgeWeightUpdate
from .auto_sop_vault_generator import AutoSOPVaultGenerator, GeneratedVaultDocuments
from .knowledge_promotion_pipeline import KnowledgePromotionPipeline, KnowledgeCandidateState, KnowledgeLifecycleStage
from .human_feedback_learning import HumanFeedbackLearning, GranularFeedbackCategory, GranularFeedbackRecord
from .multi_graph_synchronizer import MultiGraphSynchronizer, MultiGraphSyncReport
from .self_evolution_engine import SelfEvolutionEngine, SelfEvolutionReport
from .aios_message_bus import AIOSMessageBus, TypedEventMessage
from .aios_event_sourcing import AIOSEventSourcing


@dataclass
class EnterpriseKnowledgePipelineReport:
    incident_id: str
    evidence_package_id: str
    knowledge_object_id: str
    memory_evolution_summary: str
    causal_edge_updated: str
    generated_vault_files_count: int
    promotion_stage: str
    multi_graph_sync_nodes: int
    published_bus_events: List[str]
    pipeline_status: str


class EnterpriseKnowledgePipelineOrchestrator:
    """Master Orchestrator managing end-to-end Enterprise Knowledge Evolution."""

    def __init__(self, message_bus: Optional[AIOSMessageBus] = None):
        self.evidence_builder = EvidencePackageBuilder()
        self.knowledge_extractor = IncidentKnowledgeExtractor()
        self.memory_graph = MemoryGraphEvolution()
        self.causal_graph = CausalGraphEvolution()
        self.vault_generator = AutoSOPVaultGenerator()
        self.promotion_pipeline = KnowledgePromotionPipeline()
        self.feedback_learning = HumanFeedbackLearning()
        self.graph_sync = MultiGraphSynchronizer()
        self.self_evolution = SelfEvolutionEngine()
        self.message_bus = message_bus or AIOSMessageBus()
        self.event_store = AIOSEventSourcing()

    def execute_knowledge_evolution_pipeline(
        self,
        incident_id: str,
        investigation_data: Dict[str, Any],
        operator_approved_promotion: bool = True
    ) -> EnterpriseKnowledgePipelineReport:

        # Step 1: Evidence Package Builder
        evid_pkg: UnifiedEvidencePackage = self.evidence_builder.build_unified_evidence_package(incident_id, investigation_data)

        # Step 2: Knowledge Extraction Engine
        k_obj: StructuredKnowledgeObject = self.knowledge_extractor.extract_knowledge_object(evid_pkg)

        # Step 3: Memory Graph Evolution
        mem_report: MemoryEvolutionReport = self.memory_graph.evolve_memory_graph(k_obj, has_reflection_bias=True)

        # Step 4: Causal Graph Edge Evolution
        causal_update: CausalEdgeWeightUpdate = self.causal_graph.evolve_edge_weight("APChannelNoise", "POSDelay", verification_success=True)

        # Step 5: Auto SOP & Multi-Document Vault Generator
        vault_docs: GeneratedVaultDocuments = self.vault_generator.generate_document_vault(k_obj)

        # Step 6: 10-Stage Knowledge Promotion Pipeline
        cand: KnowledgeCandidateState = self.promotion_pipeline.create_knowledge_candidate(k_obj.knowledge_id, k_obj.validated_root_cause)

        # Advance DRAFT -> SANDBOX -> SIMULATED -> VALIDATED -> HUMAN_REVIEW -> PRODUCTION
        for stage in [
            KnowledgeLifecycleStage.SANDBOX,
            KnowledgeLifecycleStage.SIMULATED,
            KnowledgeLifecycleStage.VALIDATED,
            KnowledgeLifecycleStage.HUMAN_REVIEW,
            KnowledgeLifecycleStage.PRODUCTION
        ]:
            cand = self.promotion_pipeline.promote_candidate(cand.candidate_id, stage, operator_approved=operator_approved_promotion)

        # Step 7: Multi-Graph Synchronization
        sync_report: MultiGraphSyncReport = self.graph_sync.synchronize_all_graphs(incident_id, ["AP-RETAIL-01", "POS-TERM-01"])

        # Step 8: Publish Typed Message Bus Events
        bus_events = []
        msg1 = self.message_bus.publish_typed_event("KnowledgeCandidateCreated.v1", "KnowledgePipelineOrchestrator", {"candidate_id": cand.candidate_id})
        msg2 = self.message_bus.publish_typed_event("KnowledgePromoted.v1", "KnowledgePipelineOrchestrator", {"candidate_id": cand.candidate_id, "stage": cand.current_stage.name})
        bus_events.extend([msg1.event_type, msg2.event_type])

        # Step 9: Event Store Record
        self.event_store.append_event("KnowledgeEvolutionCompleted.v1", incident_id, {"candidate_id": cand.candidate_id})

        return EnterpriseKnowledgePipelineReport(
            incident_id=incident_id,
            evidence_package_id=evid_pkg.evidence_package_id,
            knowledge_object_id=k_obj.knowledge_id,
            memory_evolution_summary=mem_report.evolution_summary,
            causal_edge_updated=f"{causal_update.cause_node}->{causal_update.effect_node} weight={causal_update.updated_weight}",
            generated_vault_files_count=len(vault_docs.generated_file_paths),
            promotion_stage=cand.current_stage.name,
            multi_graph_sync_nodes=sync_report.total_nodes_updated,
            published_bus_events=bus_events,
            pipeline_status="SUCCESS_KNOWLEDGE_EVOLUTION_COMPLETED"
        )
