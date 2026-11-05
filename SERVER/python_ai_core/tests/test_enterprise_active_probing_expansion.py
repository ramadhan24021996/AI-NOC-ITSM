"""
Unit & Certification Test Suite for Enterprise Active Diagnostic Probing Platform Expansion
Validates all 12 Next-Gen Enterprise Capabilities:
1. OpenTelemetry Observability
2. Dynamic Asset Policy Engine
3. Enterprise Asset Metadata Registry
4. Bayesian Confidence Updating
5. Predictive Probe Recommendation
6. Autonomous Probe Optimization
7. Multi-Site Correlation Engine
8. Digital Twin Simulation
9. Incident Knowledge Evolution
10. Enterprise Probing Decision Explainer
11. Chaos Engineering Simulator
12. Production Certification Suite
"""

import unittest
import os
import sys

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from active_probing import (
    OpenTelemetryObservability, OTelProbeSpan,
    AssetMetadataRegistry, EnterpriseAsset, AssetRole, CriticalityLevel,
    DynamicAssetPolicyEngine, PolicyEvaluationResult,
    BayesianConfidenceUpdater, BayesianUpdateResult,
    PredictiveProbeRecommender, ProbeRecommendation,
    AutonomousProbeOptimizer, ProbeEfficiencyMetric,
    MultiSiteCorrelationEngine, MultiSiteCorrelationReport,
    ProbingDigitalTwinSimulator, DigitalTwinSimulationReport,
    IncidentKnowledgeEvolution, KnowledgeEvolutionReport,
    EnterpriseProbingExplainer, EnterpriseExplainabilityReport,
    ChaosEngineeringSimulator, ChaosFaultInjection,
    ProductionCertificationSuite, FullCertificationReport, CertificationScenarioResult,
    ProbeCatalog
)


class TestEnterpriseActiveProbingExpansion(unittest.TestCase):

    def setUp(self):
        self.catalog = ProbeCatalog()

    def test_01_opentelemetry_observability(self):
        """Validates OpenTelemetry trace_id, span_id, correlation_id, and span lifecycle."""
        otel = OpenTelemetryObservability(incident_id="INC-OTEL-100")
        span = otel.start_probe_span("PRB-L3-01", "Gateway Ping", "POS-KASIR-01")
        self.assertIsNotNone(span.trace_id)
        self.assertIsNotNone(span.span_id)
        self.assertIn("CORR-", span.correlation_id)
        self.assertIn("INV-", span.investigation_id)

        otel.end_probe_span(span.span_id, "OK", {"probe_status": "PASSED"})
        summary = otel.get_trace_summary()
        self.assertEqual(summary["total_spans"], 1)
        self.assertEqual(summary["spans"][0]["status_code"], "OK")

    def test_02_asset_metadata_registry(self):
        """Validates enterprise asset metadata, criticality levels, and SLA targets."""
        registry = AssetMetadataRegistry()
        dc_asset = registry.get_asset("DC-HQ-01")
        self.assertEqual(dc_asset.role, AssetRole.DOMAIN_CONTROLLER)
        self.assertEqual(dc_asset.criticality, CriticalityLevel.CRITICAL)
        self.assertEqual(dc_asset.sla_response_minutes, 5)

    def test_03_dynamic_asset_policy(self):
        """Validates role-specific probe execution policies (e.g. Domain Controller vs Workstation)."""
        policy_engine = DynamicAssetPolicyEngine()
        registry = AssetMetadataRegistry()

        dc_asset = registry.get_asset("DC-HQ-01")
        workstation_asset = registry.get_asset("Client_PC_01")
        p_act = self.catalog.get_probe("PRB-ACT-L2-01")  # Flush DNS
        self.assertIsNotNone(p_act)
        assert p_act is not None

        # Active probe denied on Domain Controller without HITL
        dc_res: PolicyEvaluationResult = policy_engine.evaluate_asset_probe_policy(dc_asset, p_act, hitl_approved=False)
        self.assertFalse(dc_res.allowed)
        self.assertTrue(dc_res.requires_hitl)

        # Active low-risk probe allowed on Workstation
        ws_res: PolicyEvaluationResult = policy_engine.evaluate_asset_probe_policy(workstation_asset, p_act, hitl_approved=False)
        self.assertTrue(ws_res.allowed)

    def test_04_bayesian_confidence_updating(self):
        """Validates sequential Bayesian posterior calculation upon probe evidence."""
        updater = BayesianConfidenceUpdater()
        # Prior = 0.50, Probe FAILED (anomaly observed)
        res1: BayesianUpdateResult = updater.update_hypothesis_confidence(
            prior_confidence=0.50,
            probe_id="PRB-L1-01",
            probe_status="FAILED",
            probe_sensitivity=0.95,
            probe_false_positive_rate=0.05
        )
        self.assertGreater(res1.posterior_confidence, 0.90)

        # Subsequent PASSED probe on unrelated hypothesis drops posterior
        res2: BayesianUpdateResult = updater.update_hypothesis_confidence(
            prior_confidence=0.50,
            probe_id="PRB-L3-01",
            probe_status="PASSED",
            probe_sensitivity=0.95,
            probe_false_positive_rate=0.05
        )
        self.assertLess(res2.posterior_confidence, 0.10)

    def test_05_predictive_probe_recommender(self):
        """Validates pattern-driven probe sequence optimization."""
        recommender = PredictiveProbeRecommender(self.catalog)
        rec: ProbeRecommendation = recommender.recommend_sequence({"symptom": "Printer Spooler service crashed"})
        self.assertEqual(rec.pattern_matched, "PRINTER_SPOOLER")
        self.assertIn("PRB-L7-03", rec.recommended_probe_sequence)

    def test_06_autonomous_probe_optimizer(self):
        """Validates empirical probe efficiency scoring and dynamic ranking."""
        optimizer = AutonomousProbeOptimizer(self.catalog)
        # Record low latency fast probe vs slow probe
        optimizer.record_probe_execution("PRB-L1-01", success=True, latency_ms=10.0)
        optimizer.record_probe_execution("PRB-ACT-L4-01", success=False, latency_ms=8000.0)

        ranked = optimizer.rank_probes_by_efficiency(["PRB-ACT-L4-01", "PRB-L1-01"])
        self.assertEqual(ranked[0], "PRB-L1-01")

    def test_07_multi_site_correlation_engine(self):
        """Validates multi-site correlation distinguishing local client vs Cloud vs ISP outage."""
        engine = MultiSiteCorrelationEngine()
        outcomes = {
            "SITE_JAKARTA": "FAILED",
            "SITE_SURABAYA": "FAILED",
            "ISP_GATEWAY": "FAILED"
        }
        report: MultiSiteCorrelationReport = engine.correlate_sites(outcomes)
        self.assertEqual(report.impact_scope, "ISP_DISRUPTION")
        self.assertGreaterEqual(report.confidence, 0.95)

    def test_08_probing_digital_twin_simulator(self):
        """Validates pre-probe virtual simulation for Level 3-4 active probes."""
        simulator = ProbingDigitalTwinSimulator()
        p_high = self.catalog.get_probe("PRB-ACT-L4-01")
        self.assertIsNotNone(p_high)
        assert p_high is not None

        rep: DigitalTwinSimulationReport = simulator.simulate_probe(p_high, {"criticality": "CRITICAL"})
        self.assertFalse(rep.simulation_passed)
        self.assertFalse(rep.safety_approved)

    def test_09_incident_knowledge_evolution(self):
        """Validates closed-loop GraphRAG and SOP evolution from incident replay records."""
        evolution = IncidentKnowledgeEvolution()
        rep: KnowledgeEvolutionReport = evolution.process_incident_replay_evolution(
            incident_id="INC-EVO-01",
            replay_record={"timeline": ["L1_Signal_Drop"]}
        )
        self.assertTrue(rep.policy_updated)
        self.assertGreater(rep.similarity_score, 0.90)

    def test_10_enterprise_probing_explainer(self):
        """Validates 5-point enterprise decision explainability generation."""
        explainer = EnterpriseProbingExplainer()
        exp: EnterpriseExplainabilityReport = explainer.generate_explanation(
            selected_probe_name="Physical Link & RSSI Check",
            skipped_probe_names=["HTTP HEAD Endpoint Probe"],
            eliminated_hypotheses=[{"hypothesis_id": "HYP-02", "description": "Gateway Unreachable"}],
            prior_confidence=0.50,
            posterior_confidence=0.96,
            remediation_action="Reconnect Wireless Interface"
        )
        self.assertIn("Physical Link & RSSI Check", exp.why_probe_selected)
        self.assertIn("HTTP HEAD Endpoint Probe", exp.why_probes_skipped[0])
        self.assertIn("50.0%", exp.why_confidence_shifted)
        self.assertIn("96.0%", exp.why_confidence_shifted)

    def test_11_chaos_engineering_simulator(self):
        """Validates controlled fault injection for L1-L7 active probing resilience."""
        chaos = ChaosEngineeringSimulator()
        fault: ChaosFaultInjection = chaos.inject_fault("L1_CABLE_DISCONNECT")
        self.assertEqual(fault.target_layer, "L1_PHYSICAL")
        self.assertIn("PRB-L1-01", fault.simulated_probe_failures)

    def test_12_production_certification_suite(self):
        """Validates real-world scenario certification suite across L1-L7 failure modes."""
        suite = ProductionCertificationSuite()
        report: FullCertificationReport = suite.run_full_certification()
        self.assertEqual(report.certification_status, "CERTIFIED_ENTERPRISE_READY")
        self.assertEqual(report.passed_scenarios, len(report.results))


if __name__ == "__main__":
    unittest.main()
