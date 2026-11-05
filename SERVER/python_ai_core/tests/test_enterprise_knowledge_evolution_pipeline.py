"""
Unit & Integration Test Suite for Self-Evolving RCA & Enterprise Knowledge Evolution Pipeline (AIOS v11.1.0 Evolution)
Validates 10 Core Evolution Subsystem Components:
1. Unified Evidence Package Builder
2. Incident Knowledge Extractor
3. 6-Layer Memory Graph Evolution Engine (including Reflection Memory)
4. Statistical Causal Edge Weight Evolution
5. Auto SOP & Multi-Document Vault Generator (/docs/SOP_VAULT/)
6. 10-Stage Knowledge Promotion Pipeline Lifecycle
7. 12-Category Granular Human Feedback Engine & Learning Queue
8. Multi-Graph Synchronizer (9 Domain Graphs)
9. Self Evolution Engine (GraphRAG, Prompt, Probe Order Tuning)
10. Master Enterprise Knowledge Pipeline Orchestrator
"""

import unittest
import os
import sys

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from active_probing import (
    EvidencePackageBuilder, UnifiedEvidencePackage,
    IncidentKnowledgeExtractor, StructuredKnowledgeObject,
    MemoryGraphEvolution, MemoryEvolutionReport, ReflectionMemoryEntry,
    CausalGraphEvolution, CausalEdgeWeightUpdate,
    AutoSOPVaultGenerator, GeneratedVaultDocuments,
    KnowledgePromotionPipeline, KnowledgeCandidateState, KnowledgeLifecycleStage,
    HumanFeedbackLearning, GranularFeedbackCategory, GranularFeedbackRecord,
    MultiGraphSynchronizer, MultiGraphSyncReport,
    SelfEvolutionEngine, SelfEvolutionReport,
    EnterpriseKnowledgePipelineOrchestrator, EnterpriseKnowledgePipelineReport
)


class TestEnterpriseKnowledgeEvolutionPipeline(unittest.TestCase):

    def test_01_evidence_package_builder(self):
        """Validates structured evidence collection across timeline, telemetry, PCAP, probes, and world model."""
        builder = EvidencePackageBuilder()
        pkg: UnifiedEvidencePackage = builder.build_unified_evidence_package("INC-TEST-001", {"timeline": ["Initiated", "Resolved"]})
        self.assertEqual(pkg.evidence_package_id, "EVID-PKG-INC-TEST-001")
        self.assertGreater(len(pkg.investigation_timeline), 0)
        self.assertIn("rssi_dbm", pkg.multi_modal_telemetry)

    def test_02_incident_knowledge_extractor(self):
        """Validates conversion of evidence packages into formal Knowledge Objects."""
        builder = EvidencePackageBuilder()
        pkg = builder.build_unified_evidence_package("INC-TEST-002", {})
        extractor = IncidentKnowledgeExtractor()
        k_obj: StructuredKnowledgeObject = extractor.extract_knowledge_object(pkg)

        self.assertEqual(k_obj.knowledge_id, "KOBJ-INC-TEST-002")
        self.assertIn("Wireless AP", k_obj.validated_root_cause)
        self.assertGreater(len(k_obj.lessons_learned), 0)

    def test_03_memory_graph_evolution(self):
        """Validates 6-layer memory evolution (Working, Episodic, Semantic, Procedural, Causal, & Reflection Memory)."""
        extractor = IncidentKnowledgeExtractor()
        builder = EvidencePackageBuilder()
        k_obj = extractor.extract_knowledge_object(builder.build_unified_evidence_package("INC-TEST-003", {}))

        mem = MemoryGraphEvolution()
        report: MemoryEvolutionReport = mem.evolve_memory_graph(k_obj, has_reflection_bias=True)

        self.assertTrue(report.working_memory_updated)
        self.assertEqual(report.reflection_entries_added, 1)
        self.assertEqual(len(mem.reflection_memory), 1)

    def test_04_causal_graph_evolution(self):
        """Validates statistical edge weight adjustments (+boost / -penalty) and deprecation without overwriting."""
        causal = CausalGraphEvolution()

        # Boost on verification success
        edge1: CausalEdgeWeightUpdate = causal.evolve_edge_weight("APChannelNoise", "POSDelay", verification_success=True)
        self.assertEqual(edge1.status, "BOOSTED")
        self.assertGreater(edge1.updated_weight, edge1.previous_weight)

        # Decay on false RCA
        edge2: CausalEdgeWeightUpdate = causal.evolve_edge_weight("Gateway", "PacketLoss", verification_success=False, is_false_rca=True)
        self.assertEqual(edge2.status, "DECAYED")
        self.assertLess(edge2.updated_weight, edge2.previous_weight)

    def test_05_auto_sop_vault_generator(self):
        """Validates auto-generation of 7 structured markdown documents under /docs/SOP_VAULT/."""
        extractor = IncidentKnowledgeExtractor()
        builder = EvidencePackageBuilder()
        k_obj = extractor.extract_knowledge_object(builder.build_unified_evidence_package("INC-TEST-005", {}))

        gen = AutoSOPVaultGenerator()
        docs: GeneratedVaultDocuments = gen.generate_document_vault(k_obj)

        self.assertEqual(docs.incident_id, "INC-TEST-005")
        self.assertGreater(len(docs.generated_file_paths), 0)
        for path in docs.generated_file_paths:
            self.assertTrue(os.path.exists(path))

    def test_06_10_stage_knowledge_promotion_pipeline(self):
        """Validates progressive 10-stage Knowledge Lifecycle (Draft -> Sandbox -> Validated -> Production)."""
        pipeline = KnowledgePromotionPipeline()
        cand: KnowledgeCandidateState = pipeline.create_knowledge_candidate("KOBJ-01", "Non-Disruptive Channel Switch")
        self.assertEqual(cand.current_stage, KnowledgeLifecycleStage.DRAFT)

        # Advance to PRODUCTION
        for stage in [
            KnowledgeLifecycleStage.SANDBOX,
            KnowledgeLifecycleStage.SIMULATED,
            KnowledgeLifecycleStage.VALIDATED,
            KnowledgeLifecycleStage.HUMAN_REVIEW,
            KnowledgeLifecycleStage.PRODUCTION
        ]:
            cand = pipeline.promote_candidate(cand.candidate_id, stage, operator_approved=True)

        self.assertEqual(cand.current_stage, KnowledgeLifecycleStage.PRODUCTION)
        self.assertTrue(cand.is_production_active)

    def test_07_12_category_granular_human_feedback(self):
        """Validates 12 granular human feedback categories (Wrong RCA, Wrong Probe, Wrong Risk, etc.)."""
        fb = HumanFeedbackLearning()
        rec: GranularFeedbackRecord = fb.submit_granular_feedback(
            incident_id="INC-TEST-007",
            operator_id="OP-909",
            category=GranularFeedbackCategory.WRONG_RCA,
            operator_notes="RCA missed upstream ISP latency spike",
            corrective_guidance="Prioritize WAN BGP probe before AP channel sweep"
        )
        self.assertEqual(rec.category, GranularFeedbackCategory.WRONG_RCA)

        proc = fb.process_learning_queue()
        self.assertEqual(proc["total_feedback_processed"], 1)

    def test_08_multi_graph_synchronizer(self):
        """Validates atomic synchronization across 9 domain graphs."""
        sync = MultiGraphSynchronizer()
        report: MultiGraphSyncReport = sync.synchronize_all_graphs("INC-TEST-008", ["AP-01", "SW-01"])
        self.assertEqual(report.synchronized_graphs_count, 9)
        self.assertEqual(report.sync_status, "ATOMIC_MULTI_GRAPH_SYNC_SUCCESS")

    def test_09_self_evolution_engine(self):
        """Validates closed-loop self-tuning of GraphRAG prompts, probe order, and Bayesian priors."""
        engine = SelfEvolutionEngine()
        report: SelfEvolutionReport = engine.trigger_self_evolution_cycle("CYCLE-2026-08")
        self.assertTrue(report.constitution_compliant)
        self.assertGreater(report.bayesian_priors_recalibrated, 0)

    def test_10_master_enterprise_knowledge_pipeline_orchestrator(self):
        """Validates master end-to-end Enterprise Knowledge Evolution Pipeline execution."""
        orchestrator = EnterpriseKnowledgePipelineOrchestrator()
        report: EnterpriseKnowledgePipelineReport = orchestrator.execute_knowledge_evolution_pipeline(
            incident_id="INC-E2E-999",
            investigation_data={"timeline": ["Detected", "Probed", "Resolved"]},
            operator_approved_promotion=True
        )

        self.assertEqual(report.pipeline_status, "SUCCESS_KNOWLEDGE_EVOLUTION_COMPLETED")
        self.assertEqual(report.promotion_stage, "PRODUCTION")
        self.assertGreater(report.generated_vault_files_count, 0)
        self.assertIn("KnowledgePromoted.v1", report.published_bus_events)


if __name__ == "__main__":
    unittest.main()
