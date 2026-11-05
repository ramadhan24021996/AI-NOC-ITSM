"""
Unit Tests for Production-Ready Enterprise Causal AI Engine & Validation Platform
"""

import unittest
from causal_engine import (
    NegativeEvidenceEngine, ContradictingEvidence,
    CausalValidator, ValidationResult,
    TimeAwareCausalGraph, TimeAwareCausalEdge,
    MultiScenarioCounterfactualSimulator, CompoundCounterfactualResult,
    InterventionCostModel, EvaluatedAction, ActionableRemediationStep,
    CausalDriftDetector, DriftReport,
    GraphVersioner, GraphVersionSnapshot,
    ShadowModeEngine, ShadowEvaluationRecord,
    ProductionKPIEngine, ProductionKPIMetrics,
    CausalGraph
)


class TestCausalProductionValidation(unittest.TestCase):
    def test_negative_evidence(self):
        engine = NegativeEvidenceEngine()
        payload = {"telemetry": {"rtt_ms": 1, "packet_loss": 0.0}}
        contradiction = engine.evaluate_contradictions("PacketLoss", payload)
        self.assertIsNotNone(contradiction)
        assert contradiction is not None
        self.assertEqual(contradiction.variable_name, "PacketLoss")
        self.assertGreater(contradiction.penalty_score, 0.0)

    def test_causal_validator(self):
        validator = CausalValidator()
        payload = {"telemetry": {"rtt_ms": 1, "packet_loss": 0.0}}
        res = validator.validate_hypothesis("PacketLoss", payload)
        self.assertFalse(res.is_valid)
        self.assertEqual(len(res.contradictions), 1)

    def test_time_aware_causal_graph(self):
        tag = TimeAwareCausalGraph()
        prob_normal = tag.calculate_effective_probability("RSSI", "PacketLoss", actual_delay_sec=2.0)
        self.assertEqual(prob_normal, 0.95)

        prob_delayed = tag.calculate_effective_probability("RSSI", "PacketLoss", actual_delay_sec=1800.0) # 30 min delay
        self.assertLess(prob_delayed, 0.50)

    def test_multi_scenario_counterfactual(self):
        simulator = MultiScenarioCounterfactualSimulator()
        real_world = {"PacketLoss": 0.85, "DNS_Timeout": True, "POS_Error": True}
        res = simulator.simulate_compound_scenario(["PacketLoss", "DNS_Timeout"], real_world, primary_symptom="POS_Error")
        self.assertTrue(res.primary_symptom_resolved)
        self.assertIn("do(PacketLoss=NORMAL)", res.scenario_name)

    def test_intervention_cost_model(self):
        cost_model = InterventionCostModel()
        act = ActionableRemediationStep("ACT-01", "Flush DNS Cache", "DNSResolver", "cmd", "LOW", False)
        eval_act = cost_model.evaluate_remediation_cost(act)
        self.assertEqual(eval_act.downtime_level, "LOW")
        self.assertEqual(eval_act.risk_level, "LOW")
        self.assertGreater(eval_act.net_benefit_score, 80.0)

    def test_causal_drift_detector(self):
        graph = CausalGraph()
        detector = CausalDriftDetector(graph)
        # Record 10 instances of cause NOT producing effect (0% occurrence)
        for _ in range(10):
            detector.record_observation("RSSI", "PacketLoss", effect_occurred=False)

        report = detector.detect_drift("RSSI", "PacketLoss")
        self.assertTrue(report.drift_detected)
        self.assertEqual(report.recommended_action, "DECAY_WEIGHT")

    def test_graph_versioner(self):
        graph = CausalGraph()
        versioner = GraphVersioner(graph)
        self.assertEqual(versioner.current_version, "v1.0")

        snapshot = versioner.create_snapshot("v1.1", "Added Wireless Drift Edge")
        self.assertEqual(versioner.current_version, "v1.1")

        rolled_back = versioner.rollback_to_version("v1.0")
        self.assertTrue(rolled_back)
        self.assertEqual(versioner.current_version, "v1.0")

    def test_shadow_mode(self):
        shadow = ShadowModeEngine()
        shadow.log_recommendation("INC-01", "PacketLoss", 96.0)
        evaluated = shadow.compare_with_operator("INC-01", "PacketLoss")

        self.assertIsNotNone(evaluated)
        assert evaluated is not None
        self.assertTrue(evaluated.matches_human_decision)
        self.assertEqual(shadow.get_shadow_precision_rate(), 100.0)

    def test_production_kpis(self):
        kpi_engine = ProductionKPIEngine()
        metrics = kpi_engine.calculate_kpis()
        self.assertTrue(metrics.slo_met)
        self.assertGreaterEqual(metrics.root_cause_precision, 95.0)
        self.assertLessEqual(metrics.false_root_cause_rate, 3.0)

    def test_rich_edge_metadata(self):
        """
        Validates that CausalEdge now carries full rich audit metadata:
        causal_probability, evidence_count, last_verified,
        supporting_incidents, contradicting_incidents, confidence.
        """
        graph = CausalGraph()
        audit = graph.get_edge_audit("RSSI", "PacketLoss")
        self.assertIsNotNone(audit)
        assert audit is not None
        self.assertIn("edge", audit)
        self.assertIn("causal_probability", audit)
        self.assertIn("evidence_count", audit)
        self.assertIn("last_verified", audit)
        self.assertIn("supporting_incidents", audit)
        self.assertIn("contradicting_incidents", audit)
        self.assertIn("confidence", audit)
        self.assertEqual(audit["edge"], "RSSI -> PacketLoss")
        self.assertEqual(audit["causal_probability"], 0.95)

    def test_edge_incident_outcome_tracking(self):
        """
        Validates that record_incident_outcome updates edge supporting/contradicting
        incident counts and refreshes derived confidence.
        """
        graph = CausalGraph()
        # Record 8 confirmed + 2 contradicted outcomes for an existing default edge
        for _ in range(8):
            graph.record_incident_outcome("TCP_Retransmission", "DNS_Timeout", confirmed=True)
        for _ in range(2):
            graph.record_incident_outcome("TCP_Retransmission", "DNS_Timeout", confirmed=False)

        audit = graph.get_edge_audit("TCP_Retransmission", "DNS_Timeout")
        self.assertIsNotNone(audit)
        assert audit is not None
        self.assertEqual(audit["supporting_incidents"], 8)
        self.assertEqual(audit["contradicting_incidents"], 2)
        # Confidence = 8 / (8 + 2) = 0.8
        self.assertAlmostEqual(audit["confidence"], 0.8, places=2)



if __name__ == "__main__":
    unittest.main()
