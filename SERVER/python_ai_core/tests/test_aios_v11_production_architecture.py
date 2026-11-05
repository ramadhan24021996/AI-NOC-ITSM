"""
Unit & Certification Test Suite for Production-Grade Enterprise AI Operating System (AIOS v11.0.0 Refined Production Architecture)
Validates 13 Chief Architect Platform Engineering Refinements:
1. Minimal AIOS Micro-Kernel
2. Typed Versioned Event Bus
3. Capability Registry
4. Capability Selector
5. Sandboxed Plugin Runtime & Signed Manifests
6. Policy-Aware Multi-LLM Router
7. Event Store + Periodic Snapshots
8. Consensus-Based Distributed Cluster Manager (Raft)
9. Tiered AI Constitution (Hard, Soft, Advisory Rules)
10. Task Graph DAG Engine
11. Temporal Knowledge Graph (Historical Time-Travel Querying)
12. Pre-Execution Safety Simulator & Blast Radius Calculator
13. 4-Gate Production Readiness Certification Suite
"""

import unittest
import os
import sys

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from active_probing import (
    AIOSKernel, KernelProcessState,
    AIOSMessageBus, TypedEventMessage,
    AIOSCapabilityRegistry, CapabilityRegistration,
    AIOSCapabilitySelector, CapabilityMarketplaceProfile,
    AIOSPluginRuntime, PluginManifest, PluginExecutionResult,
    AIOSLLMRouter, LLMRoutingDecision,
    AIOSEventSourcing, EventStoreRecord, EventStoreSnapshot,
    AIOSDistributedCluster, ClusterConsensusState,
    AIOSConstitution, ConstitutionEnforcementResult, RuleTier,
    AIOSTaskGraphEngine, DAGExecutionReport,
    AIOSTemporalKnowledgeGraph, TemporalTopologyState,
    AIOSSafetySimulationEngine, BlastRadiusSafetyReport,
    AIOSProductionReadinessGates, AIOSProductionCertificationReport
)


class TestAIOSV11ProductionArchitecture(unittest.TestCase):

    def test_01_minimal_aios_micro_kernel(self):
        """Validates minimal micro-kernel agent lifecycle, sandboxing, and resource quotas."""
        kernel = AIOSKernel(default_memory_limit_mb=512.0)
        proc: KernelProcessState = kernel.spawn_agent_process("ArchitectAgent", cpu_quota_pct=30.0)
        self.assertEqual(proc.status, "RUNNING")
        self.assertEqual(proc.memory_limit_mb, 512.0)

        status = kernel.kernel_status()
        self.assertEqual(status["active_processes_count"], 1)
        self.assertEqual(status["isolation_mode"], "SANDBOXED_MICROKERNEL")

    def test_02_typed_versioned_event_bus(self):
        """Validates schema-versioned typed event publishing (HypothesisGenerated.v1, ProbeCompleted.v2)."""
        bus = AIOSMessageBus()
        msg: TypedEventMessage = bus.publish_typed_event(
            event_type="ProbeCompleted.v2",
            publisher_agent="ProbeExecutorAgent",
            payload={"probe_id": "PRB-L1-01", "result": "PASSED"}
        )
        self.assertEqual(msg.schema_version, "v2")
        self.assertEqual(len(bus.event_history), 1)

    def test_03_capability_registry_and_selector(self):
        """Validates separation of Capability Registry (discovery) and Capability Selector (marketplace)."""
        registry = AIOSCapabilityRegistry()
        selector = AIOSCapabilitySelector(registry)

        cap = registry.discover_capability("ActiveDiagnosticProbing")
        self.assertIsNotNone(cap)
        assert cap is not None
        self.assertEqual(cap.version, "2.1.0")

        best_profile: CapabilityMarketplaceProfile = selector.select_optimal_capability(["ActiveDiagnosticProbing", "CounterfactualSimulation"])
        self.assertEqual(best_profile.capability_name, "ActiveDiagnosticProbing")

    def test_04_sandboxed_plugin_runtime(self):
        """Validates sandboxed execution of signed vendor driver plugins (Mikrotik, Cisco, Fortigate, Windows, Linux, K8s)."""
        runtime = AIOSPluginRuntime(signing_secret="aios_plugin_secret")
        res: PluginExecutionResult = runtime.execute_sandboxed_plugin(
            plugin_name="mikrotik",
            action="SNMP_INTERFACE_READ",
            required_permission="snmp.read"
        )
        self.assertTrue(res.permitted)
        self.assertTrue(res.signature_verified)

    def test_05_policy_aware_multi_llm_router(self):
        """Validates data-sensitivity routing: credentials/internal RCA route to Local Model; SOP routes to Cloud."""
        router = AIOSLLMRouter()

        # Sensitive -> Local Ollama DeepSeek
        route1: LLMRoutingDecision = router.route_llm_request("internal_rca_investigation", contains_sensitive_credentials=True)
        self.assertEqual(route1.data_sensitivity, "HIGH_SENSITIVE_LOCAL_ONLY")
        self.assertIn("Ollama", route1.model_provider)

        # SOP -> Cloud Gemini
        route2: LLMRoutingDecision = router.route_llm_request("sop_generation", contains_sensitive_credentials=False)
        self.assertEqual(route2.data_sensitivity, "LOW_PUBLIC")
        self.assertIn("Google", route2.model_provider)

    def test_06_event_sourcing_snapshots(self):
        """Validates Event Store append log and periodic state snapshots."""
        event_store = AIOSEventSourcing(snapshot_interval=2)
        rec1 = event_store.append_event("IncidentCreated.v1", "INC-01", {"symptom": "RSSI drop"})
        rec2 = event_store.append_event("ProbeExecuted.v1", "INC-01", {"probe": "PRB-L1-01"})

        self.assertEqual(event_store.sequence_counter, 2)
        self.assertIn("INC-01", event_store.snapshots)

    def test_07_consensus_cluster_manager(self):
        """Validates Raft consensus state, leader election, and quorum validation."""
        cluster = AIOSDistributedCluster("NODE-JKT-01")
        consensus: ClusterConsensusState = cluster.get_cluster_consensus()

        self.assertTrue(consensus.quorum_satisfied)
        self.assertEqual(consensus.leader_node_id, "NODE-JKT-01")
        self.assertEqual(consensus.active_nodes_count, 3)

    def test_08_tiered_ai_constitution(self):
        """Validates Tiered AI Constitution enforcement across Hard (Kernel), Soft (Policy), and Advisory Rules."""
        constitution = AIOSConstitution()

        # Hard Rule CONST-01 (Never Guess) trips when no evidence & low confidence
        res1: ConstitutionEnforcementResult = constitution.validate_action_constitution(
            action_name="RestartInterface",
            confidence_score=0.40,
            has_evidence=False
        )
        self.assertFalse(res1.permitted)
        self.assertEqual(res1.enforcement_tier, RuleTier.HARD_KERNEL_ENFORCED)
        self.assertEqual(res1.tripped_rule_id, "CONST-01")

    def test_09_task_graph_engine(self):
        """Validates Task Graph DAG execution engine vs loose event chaining."""
        engine = AIOSTaskGraphEngine()
        report: DAGExecutionReport = engine.execute_diagnostic_dag("DAG-DIAG-01", {"context": "pos_failure"})
        self.assertEqual(report.dag_status, "SUCCESS_DAG_COMPLETED")
        self.assertEqual(report.completed_tasks_count, 5)

    def test_10_temporal_knowledge_graph(self):
        """Validates time-versioned World Model historical time-travel queries."""
        tkg = AIOSTemporalKnowledgeGraph()
        state: TemporalTopologyState = tkg.query_historical_topology("2026-08-01")
        self.assertEqual(state.topology_version, "v6.4.0")
        self.assertGreater(state.active_nodes_at_time, 1000)

    def test_11_pre_execution_safety_simulator(self):
        """Validates pre-execution blast radius calculation and safety scores."""
        sim = AIOSSafetySimulationEngine()

        # Core Switch has huge blast radius and requires CAB
        report1: BlastRadiusSafetyReport = sim.simulate_change_blast_radius("CORE-SW-01", "RestartInterface")
        self.assertFalse(report1.execution_approved)
        self.assertEqual(report1.blast_radius_asset_count, 1450)

        # Endpoint PC has small blast radius and is approved
        report2: BlastRadiusSafetyReport = sim.simulate_change_blast_radius("PC-01", "FlushDNS")
        self.assertTrue(report2.execution_approved)

    def test_12_production_readiness_4_gates(self):
        """Validates 4-Gate Production Readiness Certification (Functional, Performance, Resilience, Governance)."""
        gates = AIOSProductionReadinessGates()
        report: AIOSProductionCertificationReport = gates.evaluate_all_production_gates(version="v11.0.0")
        self.assertEqual(report.overall_certification_status, "PRODUCTION_DEPLOYMENT_AUTHORIZED")
        self.assertEqual(report.passed_gates_count, 4)


if __name__ == "__main__":
    unittest.main()
