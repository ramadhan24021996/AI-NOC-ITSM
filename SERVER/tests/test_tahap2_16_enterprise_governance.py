"""
SERVER.tests.test_tahap2_16_enterprise_governance
==================================================
Tahap 2.16 — Enterprise Operational Governance & Observability Test Suite

Menguji 11 modul Tata Kelola Operasional Enterprise:
  1. RuntimePolicyEngine (Evaluasi kebijakan operasional YAML dinamis)
  2. ExplainabilityTimelineBuilder (Jejak evolusi keputusan langkah demi langkah)
  3. AICapabilityVersioning (Indeks versi Jarvis v3.2.1, SOP 2153, LLM Gemini 2.x)
  4. OperationalMetricsCollector (Metrik latensi RAG/LLM/Sandbox & Halusinasi = 0)
  5. MultiAgentArbitrationEngine (Arbitrase berbasis bukti tambahan saat AI tidak sepakat)
  6. KnowledgeLineageTracker (Melacak silsilah pengetahuan dari Vendor ke Operator & Supervisor)
  7. CostOptimizerRouter (Router LLM hemat biaya per tingkat kompleksitas tugas)
  8. RecoveryTreePlanner (Pohon keputusan pemulihan multi-cabang dengan fallback)
  9. DigitalTwinReplayEngine (Pemutaran ulang sesi insiden interaktif kecepatan 2x)
  10. AIGovernanceDashboardBuilder (DTO State AI Governance Dashboard real-time)
  11. Gateway Enterprise Governance Integration
"""
import unittest
from SERVER.orchestrator.enterprise_governance.runtime_policy_engine import RuntimePolicyEngine
from SERVER.orchestrator.enterprise_governance.explainability_timeline import ExplainabilityTimelineBuilder
from SERVER.orchestrator.enterprise_governance.capability_versioning import AICapabilityVersioning
from SERVER.orchestrator.enterprise_governance.operational_metrics import OperationalMetricsCollector
from SERVER.orchestrator.enterprise_governance.multi_agent_arbitration import MultiAgentArbitrationEngine
from SERVER.orchestrator.enterprise_governance.knowledge_lineage import KnowledgeLineageTracker
from SERVER.orchestrator.enterprise_governance.cost_optimizer import CostOptimizerRouter
from SERVER.orchestrator.enterprise_governance.recovery_tree_planner import RecoveryTreePlanner
from SERVER.orchestrator.enterprise_governance.digital_twin_replay import DigitalTwinReplayEngine
from SERVER.orchestrator.enterprise_governance.ai_governance_dashboard import AIGovernanceDashboardBuilder
from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway


class TestEnterpriseGovernanceSuite(unittest.TestCase):
    def test_runtime_policy_engine(self):
        rpe = RuntimePolicyEngine()
        policy = rpe.get_active_policy()
        self.assertTrue(policy.autonomous_execution_low)
        self.assertFalse(policy.autonomous_execution_high)

        rpe.update_policy({"autonomous_execution_high": True})
        self.assertTrue(rpe.is_action_allowed_autonomously("HIGH"))

    def test_explainability_timeline_builder(self):
        etb = ExplainabilityTimelineBuilder()
        timeline = etb.build_timeline("Investigasi CPU 99%")
        self.assertGreaterEqual(len(timeline.steps), 5)
        self.assertEqual(timeline.total_timeline_ms, 420)

    def test_capability_versioning(self):
        acv = AICapabilityVersioning()
        info = acv.get_version_info()
        self.assertEqual(info.jarvis_version, "3.2.1")
        self.assertEqual(info.sop_count, 2153)

    def test_operational_metrics_collector(self):
        omc = OperationalMetricsCollector()
        report = omc.collect_metrics()
        self.assertEqual(report.hallucination_count, 0)
        self.assertEqual(report.recommendation_success_rate_pct, 97)

    def test_multi_agent_arbitration_engine(self):
        maae = MultiAgentArbitrationEngine()
        res = maae.arbitrate_disagreement("INC-ARB-1", "Backup Job", "Memory Leak")
        self.assertTrue(res.has_disagreement)
        self.assertIn("PostgreSQL Log", res.evidence_requested)
        self.assertIn("Perbedaan pendapat terdeteksi", res.arbitrated_decision)

    def test_knowledge_lineage_tracker(self):
        klt = KnowledgeLineageTracker()
        chain = klt.get_lineage("SOP-ORACLE-RAC-v3.2")
        self.assertEqual(chain.original_author, "Oracle Vendor Doc v4")
        self.assertEqual(chain.incidents_applied_count, 24)

    def test_cost_optimizer_router(self):
        cor = CostOptimizerRouter()
        self.assertEqual(cor.select_model_for_task("greeting"), "Small-Local-Model-1B")
        self.assertEqual(cor.select_model_for_task("rag_parsing"), "Gemini-1.5-Flash")
        self.assertEqual(cor.select_model_for_task("peer_review"), "DeepSeek-V3")
        self.assertEqual(cor.select_model_for_task("consensus"), "Grok-2")

    def test_recovery_tree_planner(self):
        rtp = RecoveryTreePlanner()
        tree = rtp.build_recovery_tree("PostgreSQL Lock")
        self.assertIn("Throttle Backup", tree.primary_branch)
        self.assertIn("Kill", tree.fallback_branch_1)

    def test_digital_twin_replay_and_dashboard(self):
        dtre = DigitalTwinReplayEngine()
        frames = dtre.replay_session("INC-RPL-1", speed_multiplier=2.0)
        self.assertEqual(len(frames), 5)

        agdb = AIGovernanceDashboardBuilder()
        dash = agdb.build_dashboard()
        self.assertEqual(dash.ai_health_pct, 98)
        self.assertEqual(dash.hallucination_count, 0)
        self.assertEqual(dash.trust_score_pct, 96)


class TestGatewayEnterpriseGovernanceIntegration(unittest.TestCase):
    def setUp(self):
        self.gateway = NOCIntegrationGateway()

    def test_gateway_returns_enterprise_governance_payload(self):
        req = {
            "query_id": "Q-ENTERPRISE-2.16",
            "user_id": "Rama",
            "user_role": "Senior System Engineer",
            "query_text": "Audit tata kelola operasional insiden Oracle RAC dan PostgreSQL",
            "telemetry_context": {"netdata_cpu_usage": 98.0},
        }
        res = self.gateway.handle_request(req)

        self.assertEqual(res["query_id"], "Q-ENTERPRISE-2.16")
        self.assertIn("ai_governance_dashboard", res)
        self.assertEqual(res["ai_governance_dashboard"]["ai_health_pct"], 98)

        self.assertIn("runtime_policy", res)
        self.assertIn("arbitration_result", res)
        self.assertIn("explainability_timeline", res)
        self.assertIn("capability_version", res)
        self.assertIn("knowledge_lineage", res)
        self.assertIn("recovery_tree", res)

    def test_gateway_enterprise_governance_api_methods(self):
        dash = self.gateway.get_ai_governance_dashboard()
        self.assertEqual(dash["ai_health_pct"], 98)

        updated_policy = self.gateway.update_runtime_policy({"autonomous_execution_med": True})
        self.assertTrue(updated_policy["autonomous_execution_med"])

        arb = self.gateway.arbitrate_disagreement("INC-API-ARB", "Backup Job", "Memory Leak")
        self.assertTrue(arb["has_disagreement"])

        lineage = self.gateway.get_knowledge_lineage("SOP-ORACLE-RAC-v3.2")
        self.assertEqual(lineage["historical_accuracy_pct"], 96)


if __name__ == "__main__":
    unittest.main()
