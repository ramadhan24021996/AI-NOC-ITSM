"""
Unit Tests for Active Diagnostic Probing Platform (Hypothesis-Driven Investigation Mode)
Validates all 12 production-grade features:
DDE, Probe Budget Manager, Probe Dependency Graph, Probe Sandbox, Cross-Device Probe Engine,
Escalation Policy, Diagnostic State Machine, Hypothesis Elimination Matrix, Health Scorer, Replay Engine,
Production KPIs, Multi-Agent Consensus, and Evidence-First Non-Guessing Refusal Policy.
"""

import unittest
import os
import sys
from typing import List

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from active_probing import (
    ProbeCatalog, DiagnosticProbe, RiskLevel, OSILayer,
    ProbeBudget, ProbeDependencyGraph, ProbeSandbox, SandboxValidationResult,
    ActiveProbeExecutor, ProbeResult, CrossDeviceProbeEngine, CrossDeviceAnalysisResult,
    ProbeEscalationPolicy, EscalationDecision, DiagnosticStateMachine, DiagnosticState,
    HypothesisEliminationMatrix, HypothesisStatus, ProbeHealthScorer, DomainHealthReport,
    ProbeReplayEngine, ProductionProbingKPIEngine, ProductionProbingKPIMetrics,
    MultiAgentProbeCoordinator, MultiAgentConsensusReport, DiagnosticDecisionEngine,
    DiagnosticDecisionResult, ProbeInvestigationOrchestrator, InvestigationReport
)
from agents.architect_agent import ArchitectAgent


class TestActiveDiagnosticProbingPlatform(unittest.TestCase):

    def setUp(self):
        self.catalog = ProbeCatalog()
        self.budget = ProbeBudget()
        self.sandbox = ProbeSandbox()
        self.executor = ActiveProbeExecutor(sandbox=self.sandbox)
        self.orchestrator = ProbeInvestigationOrchestrator()

    def test_01_probe_catalog_initialization(self):
        """Verifies probe catalog has probes across OSI Layers 1-7."""
        self.assertGreaterEqual(len(self.catalog.probes), 10)
        probe_l1 = self.catalog.get_probe("PRB-L1-01")
        self.assertIsNotNone(probe_l1)
        self.assertEqual(probe_l1.osi_layer, OSILayer.L1_PHYSICAL)
        self.assertEqual(probe_l1.risk_level, RiskLevel.LEVEL_1_READ_ONLY)

    def test_02_probe_budget_manager(self):
        """Verifies resource limits: Max 20 ReadOnly, Max 5 Active, Max Time."""
        budget = ProbeBudget(max_readonly_probes=2)
        p_ro = self.catalog.get_probe("PRB-L1-01")
        self.assertIsNotNone(p_ro)
        assert p_ro is not None

        allowed, msg = budget.can_execute(p_ro)
        self.assertTrue(allowed)
        budget.record_execution(p_ro)

        allowed, msg = budget.can_execute(p_ro)
        self.assertTrue(allowed)
        budget.record_execution(p_ro)

        # 3rd read-only probe exceeds budget of 2
        allowed, msg = budget.can_execute(p_ro)
        self.assertFalse(allowed)
        self.assertIn("budget exhausted", msg)

    def test_03_probe_dependency_graph_pruning(self):
        """Verifies downstream probes are pruned when parent probe fails."""
        graph = ProbeDependencyGraph(self.catalog)
        # Parent probe: PRB-L3-01 (Ping Gateway)
        # Child probe: PRB-L3-02 (DNS Lookup)
        self.assertFalse(graph.is_pruned("PRB-L3-02"))

        graph.record_probe_failure("PRB-L3-01")
        self.assertTrue(graph.is_pruned("PRB-L3-02"))

    def test_04_probe_sandbox_guardrails(self):
        """Verifies sandbox blocks Level 4 High Risk probes without HITL approval."""
        p_high = self.catalog.get_probe("PRB-ACT-L4-01")
        self.assertIsNotNone(p_high)
        assert p_high is not None

        res: SandboxValidationResult = self.sandbox.validate_and_isolate(p_high, {}, hitl_approved=False)
        self.assertFalse(res.allowed)
        self.assertTrue(res.requires_hitl)
        self.assertIn("Human-in-the-Loop", res.reason)

        # Allowed when HITL approved
        res_approved = self.sandbox.validate_and_isolate(p_high, {}, hitl_approved=True)
        self.assertTrue(res_approved.allowed)

    def test_05_active_probe_executor_rich_metadata(self):
        """Verifies probe executor returns rich result metadata (status, confidence, latency, repeatability)."""
        p_ping = self.catalog.get_probe("PRB-L3-01")
        self.assertIsNotNone(p_ping)
        assert p_ping is not None

        result: ProbeResult = self.executor.execute_probe(p_ping, {"target_ip": "192.168.1.1"})
        self.assertEqual(result.status, "PASSED")
        self.assertGreater(result.confidence, 0.90)
        self.assertGreater(result.latency_ms, 0.0)
        self.assertTrue(result.repeatability)
        self.assertIsNotNone(result.timestamp)

    def test_06_cross_device_probe_engine(self):
        """Verifies cross-device comparative diagnostic correlation isolates local vs gateway issue."""
        cross_engine = CrossDeviceProbeEngine(self.catalog, self.executor)
        analysis: CrossDeviceAnalysisResult = cross_engine.analyze_cross_device_correlation(
            primary_device="PC001",
            comparison_device="PC002",
            probe_id="PRB-L3-01",
            telemetry_context={"simulated_failures": ["PC001"]}
        )
        self.assertEqual(analysis.isolation_scope, "LOCAL_ENDPOINT_ISSUE")
        self.assertGreater(analysis.confidence, 0.90)

    def test_07_probe_escalation_policy(self):
        """Verifies step-wise escalation: Level 1 -> Level 2 -> Level 3 -> HITL Gate -> Level 4."""
        policy = ProbeEscalationPolicy()
        p1 = self.catalog.get_probe("PRB-L1-01")
        p2 = self.catalog.get_probe("PRB-ACT-L2-01")
        self.assertIsNotNone(p1)
        self.assertIsNotNone(p2)
        assert p1 is not None and p2 is not None

        probes_list: List[DiagnosticProbe] = [p1, p2]
        decision: EscalationDecision = policy.evaluate_escalation(probes_list, level1_evidence_sufficient=False, level2_evidence_sufficient=False)
        self.assertEqual(decision.next_level, RiskLevel.LEVEL_1_READ_ONLY)
        self.assertIsNotNone(decision.probe_to_execute)
        assert decision.probe_to_execute is not None
        self.assertEqual(decision.probe_to_execute.probe_id, "PRB-L1-01")

        # Escalate to Level 2 when Level 1 evidence is sufficient/exhausted
        probes_list2: List[DiagnosticProbe] = [p2]
        decision2 = policy.evaluate_escalation(probes_list2, level1_evidence_sufficient=True, level2_evidence_sufficient=False)
        self.assertEqual(decision2.next_level, RiskLevel.LEVEL_2_LOW_RISK)

    def test_08_diagnostic_state_machine(self):
        """Verifies diagnostic state machine records transition history through 13 lifecycle states."""
        sm = DiagnosticStateMachine("INC-101")
        sm.transition_to(DiagnosticState.COLLECTING, "Collecting telemetry")
        sm.transition_to(DiagnosticState.GENERATING_HYPOTHESIS, "Generating candidate hypotheses")
        sm.transition_to(DiagnosticState.RCA_READY, "RCA confirmed")

        self.assertEqual(sm.current_state_name(), "RCA_READY")
        self.assertEqual(len(sm.history), 4)

    def test_09_hypothesis_elimination_matrix(self):
        """Verifies hypothesis tracking: ACCEPTED, REJECTED, UNKNOWN with evidence reasons."""
        matrix = HypothesisEliminationMatrix()
        matrix.register_hypothesis("HYP-01", "RSSI_Drop", "L1 Signal Drop", ["PRB-L1-01"])

        matrix.record_probe_result("HYP-01", "PRB-L1-01", "FAILED", {"failure_reason": "Anomalous RSSI -88dBm"})
        accepted = matrix.get_accepted_hypotheses()
        self.assertEqual(len(accepted), 1)
        self.assertEqual(accepted[0].hypothesis_id, "HYP-01")
        self.assertEqual(accepted[0].status, HypothesisStatus.ACCEPTED)

    def test_10_probe_health_scorer(self):
        """Verifies probe health scorer aggregates domain health percentages."""
        scorer = ProbeHealthScorer()
        p1 = ProbeResult("PRB-L1-01", "Link", "127.0.0.1", "PASSED", 0.95, 10.0, True, "2026-08-04T14:00:00Z", 1, 1)
        p2 = ProbeResult("PRB-L3-01", "Ping", "127.0.0.1", "PASSED", 0.95, 20.0, True, "2026-08-04T14:00:00Z", 3, 1)
        p3 = ProbeResult("PRB-L7-01", "HTTP", "127.0.0.1", "FAILED", 0.95, 50.0, True, "2026-08-04T14:00:00Z", 7, 1)

        health: DomainHealthReport = scorer.calculate_health_scores([p1, p2, p3])
        self.assertEqual(health.network_health_pct, 100.0)
        self.assertEqual(health.application_health_pct, 0.0)
        self.assertGreater(health.overall_health_pct, 0.0)

    def test_11_probe_replay_engine(self):
        """Verifies probe replay engine records timeline, probe_result, and decision JSON files."""
        replay = ProbeReplayEngine(base_dir="/tmp/test_probe_history")
        incident_dir = replay.persist_investigation_record(
            incident_id="INC-TEST-01",
            timeline=["Step 1", "Step 2"],
            probe_results=[{"probe_id": "PRB-L1-01", "status": "PASSED"}],
            decision_matrix={"accepted": 1}
        )
        self.assertTrue(incident_dir.endswith("INC-TEST-01"))
        record = replay.load_replay("INC-TEST-01")
        self.assertEqual(record["incident_id"], "INC-TEST-01")

    def test_12_production_probing_kpi(self):
        """Verifies production probing KPIs meet enterprise SLO targets."""
        kpi_engine = ProductionProbingKPIEngine()
        metrics: ProductionProbingKPIMetrics = kpi_engine.calculate_kpis()
        self.assertTrue(metrics.slo_met)
        self.assertLessEqual(metrics.mean_investigation_time_sec, 30.0)
        self.assertGreaterEqual(metrics.probe_success_rate_pct, 98.0)
        self.assertGreaterEqual(metrics.rca_precision_pct, 95.0)

    def test_13_full_investigation_pipeline_rca(self):
        """Full E2E test verifying active diagnostic probing pipeline generates validated RCA."""
        payload = {
            "device_id": "POS-KASIR-01",
            "telemetry": {"rssi_dbm": -88, "packet_loss": 0.85, "resolve_time_ms": 5000},
            "browser_console": [{"error": "ERR_NAME_NOT_RESOLVED"}],
            "simulated_failures": ["PRB-L1-01"]
        }
        report: InvestigationReport = self.orchestrator.run_investigation_pipeline(
            incident_id="INC-9001",
            incident_payload=payload
        )
        self.assertEqual(report.status, "RCA_CONFIRMED")
        self.assertFalse(report.refusal_triggered)
        self.assertIsNotNone(report.validated_root_cause)
        self.assertGreaterEqual(report.confidence_score, 0.90)

    def test_14_strict_non_guessing_refusal_when_evidence_insufficient(self):
        """
        CRITICAL TEST: Verifies Evidence-First Non-Guessing Policy.
        When probe budget/time is exhausted or evidence is insufficient, the system REFUSES
        to guess an RCA and outputs 'Additional Active Diagnostic Probing Required.'
        """
        # Orchestrator with an empty catalog or exhausted budget
        orchestrator_exhausted = ProbeInvestigationOrchestrator()
        orchestrator_exhausted.catalog.probes.clear()  # No probes available to gather missing evidence

        report: InvestigationReport = orchestrator_exhausted.run_investigation_pipeline(
            incident_id="INC-EXHAUSTED-01",
            incident_payload={"device_id": "Client_PC_01", "telemetry": {}}
        )
        self.assertEqual(report.status, "PROBING_REQUIRED")
        self.assertTrue(report.refusal_triggered)
        self.assertEqual(report.refusal_message, "Additional Active Diagnostic Probing Required.")
        self.assertIsNone(report.validated_root_cause)

    def test_15_architect_agent_active_probing_integration(self):
        """Verifies ArchitectAgent integration with Active Diagnostic Probing Engine."""
        architect = ArchitectAgent()
        res = architect.investigate_with_active_probing(
            incident_id="INC-ARCH-01",
            payload={
                "device_id": "POS-STORE-01",
                "telemetry": {"rssi_dbm": -88, "packet_loss": 0.85},
                "simulated_failures": ["PRB-L1-01"]
            }
        )
        self.assertIn("status", res)
        self.assertEqual(res["status"], "RCA_CONFIRMED")
        self.assertIn("validated_root_cause", res)


if __name__ == "__main__":
    unittest.main()
