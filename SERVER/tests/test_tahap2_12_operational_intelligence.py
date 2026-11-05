"""
SERVER.tests.test_tahap2_12_operational_intelligence
=====================================================
Tahap 2.12 — Senior Systems Engineer Operational Intelligence Test Suite

Menguji 10 modul Inteligensi Operasional:
  1. OperationalHealthEngine & SystemSelfHealthScore
  2. EvidenceCollector (7 sumber bukti empiris)
  3. RootCauseGraphBuilder (Grafik korelasi node & edge RCA)
  4. SelfReflectionEngine (Evaluasi mandiri pasca-generasi)
  5. ExplanationEngine (Jejak audit "Mengapa AI mengambil keputusan ini")
  6. CapabilityRegistry (Daftar batas CAN vs CANNOT)
  7. AIOperationalJournalManager (Jurnal operasional harian)
  8. Gateway Integration
"""
import unittest
import asyncio
from SERVER.health.self_health import SystemSelfHealthScore
from SERVER.health.health_engine import OperationalHealthEngine
from SERVER.orchestrator.cognitive.evidence_collector import EvidenceCollector
from SERVER.orchestrator.cognitive.root_cause_graph import RootCauseGraphBuilder
from SERVER.orchestrator.cognitive.self_reflection import SelfReflectionEngine
from SERVER.orchestrator.cognitive.explanation_engine import ExplanationEngine
from SERVER.orchestrator.cognitive.capability_registry import CapabilityRegistry
from SERVER.orchestrator.cognitive.operational_journal import AIOperationalJournalManager
from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway


class TestOperationalIntelligenceSuite(unittest.TestCase):
    def test_self_health_score_and_health_engine(self):
        sh = SystemSelfHealthScore()
        bd = sh.compute(ai_health=98, knowledge=95, telemetry=99, llm=92, memory=96, sandbox=100)
        self.assertEqual(bd.overall_system_health, 97)

        he = OperationalHealthEngine()
        report = he.run_health_audit({"netdata_cpu_usage": 45.0})
        self.assertEqual(report.overall_status, "HEALTHY")
        self.assertEqual(report.self_health.overall_system_health, 97)
        self.assertGreater(len(report.findings), 2)

    def test_evidence_collector(self):
        ec = EvidenceCollector()
        coll = ec.collect({"netdata_cpu_usage": 98.0, "host": "srv-accounting-01"}, [{}, {}])
        self.assertEqual(coll.verified_sources_count, 7)
        self.assertEqual(len(coll.items), 7)
        self.assertTrue(any(i["source_name"] == "Netdata" and i["is_available"] for i in coll.items))

    def test_root_cause_graph_builder(self):
        rca = RootCauseGraphBuilder()
        payload = rca.build_graph("CPU Spike", "srv-accounting-01", "Kenapa CPU tinggi karena backup postgresql?")
        self.assertEqual(payload.root_cause_node_id, "node_lock")
        self.assertGreaterEqual(len(payload.nodes), 3)
        self.assertGreaterEqual(len(payload.edges), 2)

    def test_self_reflection_engine(self):
        sre = SelfReflectionEngine()
        report = sre.reflect("Diagnosa router BGP", "Langkah 1: Cek BGP session.\nLangkah 2: Restart daemon.", 0.95)
        self.assertTrue(report.is_sufficient)
        self.assertTrue(report.confidence_adequate)
        self.assertFalse(report.needs_clarification)

    def test_explanation_engine(self):
        ee = ExplanationEngine()
        trail = ee.generate_trail("diagnose_incident", "Netdata", 0.95, "Find RCA")
        self.assertGreaterEqual(len(trail.reasoning_steps), 5)
        self.assertIn("Netdata", trail.audit_summary)

    def test_capability_registry(self):
        cr = CapabilityRegistry()
        matrix = cr.get_capabilities()
        self.assertIn("Root Cause Analysis (RCA)", matrix.supported_capabilities)
        self.assertIn("Direct unapproved SSH server login", matrix.forbidden_actions)

    def test_ai_operational_journal(self):
        jm = AIOperationalJournalManager()
        journal = jm.generate_daily_journal(total_incidents=4, critical_incidents=1, new_sops=3)
        self.assertEqual(journal.total_incidents, 4)
        self.assertEqual(journal.critical_incidents, 1)
        self.assertEqual(journal.ai_accuracy_pct, 97)
        self.assertGreater(len(journal.key_findings), 0)


class TestGatewayOperationalIntelligenceIntegration(unittest.TestCase):
    def setUp(self):
        self.gateway = NOCIntegrationGateway()

    def test_gateway_returns_senior_engineer_intelligence_payload(self):
        req = {
            "query_id": "Q-INTEL-1",
            "user_id": "Rama",
            "user_role": "Senior System Engineer",
            "query_text": "Diagnosa CPU spike pada srv-accounting-01 akibat backup PostgreSQL",
            "telemetry_context": {"netdata_cpu_usage": 98.0, "agent_cpu_usage": 98.0, "host": "srv-accounting-01"},
        }
        res = self.gateway.handle_request(req)

        self.assertEqual(res["query_id"], "Q-INTEL-1")
        self.assertIn("root_cause_graph", res)
        self.assertEqual(res["root_cause_graph"]["root_cause_node_id"], "node_lock")

        self.assertIn("evidence_collection", res)
        self.assertGreaterEqual(res["evidence_collection"]["verified_sources_count"], 6)

        self.assertIn("self_health_breakdown", res)
        self.assertEqual(res["self_health_breakdown"]["overall_system_health"], 97)

        self.assertIn("self_reflection", res)
        self.assertTrue(res["self_reflection"]["is_sufficient"])

        self.assertIn("explanation_trail", res)
        self.assertIn("capabilities", res)
        self.assertIn("daily_journal", res)

    def test_gateway_async_intelligence_payload(self):
        async def run_async():
            req = {
                "query_id": "Q-INTEL-ASYNC",
                "user_id": "Rama",
                "user_role": "Executive",
                "query_text": "Jelaskan ringkasan kesehatan operasional",
            }
            return await self.gateway.handle_request_async(req)

        res = asyncio.run(run_async())
        self.assertEqual(res["query_id"], "Q-INTEL-ASYNC")
        self.assertIn("daily_journal", res)
        self.assertIn("self_health_breakdown", res)


if __name__ == "__main__":
    unittest.main()
