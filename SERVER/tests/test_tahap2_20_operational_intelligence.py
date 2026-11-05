"""
SERVER.tests.test_tahap2_20_operational_intelligence
======================================================
Tahap 2.20 — Ultimate Production Operational Intelligence Test Suite

Menguji 8 modul Operational Intelligence Puncak:
  1. RuntimeCapabilityHealthRegistry (Cek Ketersediaan Alat Live: OFFLINE, BUSY, TIMEOUT, ONLINE)
  2. GranularConfidenceExplainer (Penjelasan Terurai Penurunan Skor Keyakinan)
  3. ResourceAwareDecisionEngine (Adaptasi Strategi AI terhadap RAM/CPU Host 8GB)
  4. SLABusinessImpactEngine (Kalkulasi Pengguna Terdampak, POS Mati, Kerugian $, SLA Risk)
  5. ToolSequenceOptimizer (Urutan Eksekusi Alat Efisien & Tercepat)
  6. IncidentSimilarityGraphBuilder (Graf Kemiripan Insiden Historis + Penjelasan Perbedaan Utama)
  7. AutonomousRollbackAdvisor (Saran Rollback Otomatis jika Recovery Gagal)
  8. MultiAgentHealthMonitor (Monitoring Kesehatan Live AI NOC & Jarvis)
  9. Gateway Integration & API Methods
"""
import unittest
from SERVER.orchestrator.operational_intelligence.runtime_capability_health import RuntimeCapabilityHealthRegistry
from SERVER.orchestrator.operational_intelligence.granular_confidence_explainer import GranularConfidenceExplainer
from SERVER.orchestrator.operational_intelligence.resource_aware_decision import ResourceAwareDecisionEngine
from SERVER.orchestrator.operational_intelligence.sla_business_impact import SLABusinessImpactEngine
from SERVER.orchestrator.operational_intelligence.tool_sequence_optimizer import ToolSequenceOptimizer
from SERVER.orchestrator.operational_intelligence.incident_similarity_graph import IncidentSimilarityGraphBuilder
from SERVER.orchestrator.operational_intelligence.autonomous_rollback_advisor import AutonomousRollbackAdvisor
from SERVER.orchestrator.operational_intelligence.multi_agent_health import MultiAgentHealthMonitor
from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway


class TestOperationalIntelligenceSuite(unittest.TestCase):
    def test_runtime_capability_health(self):
        registry = RuntimeCapabilityHealthRegistry()
        status = registry.check_capability_health()
        self.assertIn("Docker Container CLI", status.capabilities_health)
        self.assertTrue(status.all_critical_capabilities_ready)

    def test_granular_confidence_explainer(self):
        explainer = GranularConfidenceExplainer()
        exp = explainer.explain_confidence(92)
        self.assertEqual(exp.overall_confidence_pct, 92)
        self.assertIn("PostgreSQL Log belum tersedia", exp.degradation_reason)

    def test_resource_aware_decision(self):
        engine = ResourceAwareDecisionEngine()
        state = engine.evaluate_resource_state(ram_pct=95, cpu_pct=92, queue_len=37)
        self.assertEqual(state.active_mode, "RESOURCE_CONSTRAINED_LIGHT_MODEL")
        self.assertTrue(state.use_cache)

    def test_sla_business_impact(self):
        impact_engine = SLABusinessImpactEngine()
        report = impact_engine.compute_impact("Restart PostgreSQL Container")
        self.assertEqual(report.impacted_users_count, 120)
        self.assertEqual(report.stopped_pos_terminals_count, 3)
        self.assertEqual(report.estimated_revenue_loss_usd, 450.0)

    def test_tool_sequence_optimizer(self):
        optimizer = ToolSequenceOptimizer()
        seq = optimizer.optimize_sequence()
        self.assertEqual(len(seq.execution_order), 5)
        self.assertEqual(seq.estimated_total_time_seconds, 36)

    def test_incident_similarity_graph(self):
        builder = IncidentSimilarityGraphBuilder()
        graph = builder.build_similarity_graph("Backup Lock Contention")
        self.assertEqual(len(graph.similar_incidents), 3)
        self.assertIn("Perbedaan Utama", graph.key_differences_explanation)

    def test_autonomous_rollback_advisor(self):
        advisor = AutonomousRollbackAdvisor()
        advice = advisor.generate_rollback_advice("FAILED")
        self.assertTrue(advice.rollback_recommended)
        self.assertEqual(advice.estimated_success_pct, 97)

    def test_multi_agent_health_monitor(self):
        monitor = MultiAgentHealthMonitor()
        health = monitor.get_system_health()
        self.assertIn("HEALTHY", health.ai_noc_status)
        self.assertIn("HEALTHY", health.jarvis_status)


class TestGatewayOperationalIntelligenceIntegration(unittest.TestCase):
    def setUp(self):
        self.gateway = NOCIntegrationGateway()

    def test_gateway_returns_operational_intelligence_payload(self):
        req = {
            "query_id": "Q-OP-INTEL-2.20",
            "user_id": "Rama",
            "user_role": "Senior System Engineer",
            "query_text": "Evaluasi dampak bisnis, urutan tool, dan kesehatan kapabilitas insiden PostgreSQL",
            "telemetry_context": {"netdata_cpu_usage": 98.0},
        }
        res = self.gateway.handle_request(req)

        self.assertEqual(res["query_id"], "Q-OP-INTEL-2.20")

        self.assertIn("capability_health", res)
        self.assertTrue(res["capability_health"]["all_critical_capabilities_ready"])

        self.assertIn("granular_confidence", res)
        self.assertGreater(res["granular_confidence"]["overall_confidence_pct"], 80)

        self.assertIn("resource_state", res)
        self.assertEqual(res["resource_state"]["active_mode"], "RESOURCE_CONSTRAINED_LIGHT_MODEL")

        self.assertIn("business_impact", res)
        self.assertEqual(res["business_impact"]["impacted_users_count"], 0)  # Primary recommendation is Throttle Backup

        self.assertIn("tool_sequence", res)
        self.assertEqual(len(res["tool_sequence"]["execution_order"]), 5)

        self.assertIn("similarity_graph", res)
        self.assertEqual(len(res["similarity_graph"]["similar_incidents"]), 3)

        self.assertIn("rollback_advice", res)

        self.assertIn("multi_agent_health", res)
        self.assertIn("HEALTHY", res["multi_agent_health"]["ai_noc_status"])

    def test_gateway_operational_intelligence_api_methods(self):
        health = self.gateway.get_multi_agent_health()
        self.assertIn("HEALTHY", health["ai_noc_status"])

        impact = self.gateway.compute_business_impact("Restart PostgreSQL Container")
        self.assertEqual(impact["estimated_revenue_loss_usd"], 450.0)

        cap_health = self.gateway.check_capability_health()
        self.assertTrue(cap_health["all_critical_capabilities_ready"])


if __name__ == "__main__":
    unittest.main()
