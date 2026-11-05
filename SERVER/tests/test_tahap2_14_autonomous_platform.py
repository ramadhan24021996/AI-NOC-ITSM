"""
SERVER.tests.test_tahap2_14_autonomous_platform
================================================
Tahap 2.14 — Autonomous AI Operations Platform Test Suite

Menguji 11 modul Platform AI Otonom:
  1. MissionManager (Antrean prioritas insiden P1-P4)
  2. ResourceManager (Monitoring & Failover Provider LLM Gemini/DeepSeek)
  3. WorkflowPlanner (Generasi rencana alur kerja operasional multi-tahap)
  4. MultiAgentCollaborationEngine (Dialog peer-to-peer AI NOC <-> Jarvis)
  5. OperationalKnowledgeGraphBuilder (Grafik relasi topologi perangkat)
  6. MemoryGraphIndex (Indeks grafik relasi memori & SOP)
  7. AIExperienceEngine (Pengalaman insiden berbulan-bulan)
  8. ContinuousImprovementEngine (Evaluasi akurasi mingguan & Learning Plan)
  9. DigitalTwinBuilder (DTO State Dashboard Digital Twin real-time)
  10. TaskSchedulerManager (Penjadwalan tugas operasional berkala)
  11. Gateway Autonomous Platform Integration
"""
import unittest
from SERVER.orchestrator.autonomous.mission_manager import MissionManager
from SERVER.orchestrator.autonomous.resource_manager import ResourceManager
from SERVER.orchestrator.autonomous.workflow_planner import WorkflowPlanner
from SERVER.orchestrator.autonomous.multi_agent_collaboration import MultiAgentCollaborationEngine
from SERVER.orchestrator.autonomous.operational_knowledge_graph import OperationalKnowledgeGraphBuilder
from SERVER.orchestrator.autonomous.memory_graph import MemoryGraphIndex
from SERVER.orchestrator.autonomous.experience_engine import AIExperienceEngine
from SERVER.orchestrator.autonomous.continuous_improvement import ContinuousImprovementEngine
from SERVER.orchestrator.autonomous.digital_twin_builder import DigitalTwinBuilder
from SERVER.orchestrator.autonomous.task_scheduler import TaskSchedulerManager
from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway


class TestAutonomousPlatformSuite(unittest.TestCase):
    def test_mission_manager(self):
        mm = MissionManager()
        queue = mm.get_mission_queue()
        self.assertGreater(len(queue.p1_active_incidents), 0)
        self.assertIn("Firewall Outage", queue.active_mission)

    def test_resource_manager_failover(self):
        rm = ResourceManager()
        status1 = rm.get_resource_status(provider_timeout=False)
        self.assertEqual(status1.active_provider, "Gemini 1.5 Pro")

        status2 = rm.get_resource_status(provider_timeout=True)
        self.assertEqual(status2.active_provider, "DeepSeek V3")
        self.assertEqual(status2.provider_health["Gemini 1.5 Pro"], "BUSY")

    def test_workflow_planner(self):
        wp = WorkflowPlanner()
        plan = wp.generate_plan("PostgreSQL DB", "Upgrade")
        self.assertEqual(len(plan.steps), 5)
        self.assertIn("Rollback", plan.rollback_plan)

    def test_multi_agent_collaboration_engine(self):
        mace = MultiAgentCollaborationEngine()
        payload = mace.run_collaboration_dialogue("INC-MA-1", "Diagnosa CPU high")
        self.assertGreaterEqual(len(payload.dialogue_turns), 6)
        self.assertEqual(payload.peer_agreement_pct, 96)
        self.assertEqual(payload.peer_verdict, "VERIFIED")

    def test_operational_knowledge_graph_builder(self):
        op_kg = OperationalKnowledgeGraphBuilder()
        payload = op_kg.build_topology_graph("srv-accounting-01")
        self.assertEqual(len(payload.nodes), 5)
        self.assertEqual(len(payload.relations), 4)

    def test_memory_graph_index(self):
        mgi = MemoryGraphIndex()
        payload = mgi.query_memory_graph("Oracle RAC")
        self.assertEqual(payload.indexed_links_count, 14)

    def test_experience_and_improvement_engines(self):
        ee = AIExperienceEngine()
        rec = ee.evaluate_experience("Backup Lock")
        self.assertEqual(rec.matched_incidents_count, 5)

        cie = ContinuousImprovementEngine()
        plan = cie.generate_improvement_plan()
        self.assertEqual(plan.weekly_accuracy_pct, 82)
        self.assertGreaterEqual(len(plan.generated_learning_plan), 3)

    def test_digital_twin_and_scheduler(self):
        dtb = DigitalTwinBuilder()
        state = dtb.build_state()
        self.assertEqual(state.confidence_pct, 92)
        self.assertTrue(state.active_loop)

        tsm = TaskSchedulerManager()
        tasks = tsm.get_scheduled_tasks()
        self.assertEqual(len(tasks), 3)


class TestGatewayAutonomousPlatformIntegration(unittest.TestCase):
    def setUp(self):
        self.gateway = NOCIntegrationGateway()

    def test_gateway_returns_autonomous_platform_payload(self):
        req = {
            "query_id": "Q-AUTONOMOUS-1",
            "user_id": "Rama",
            "user_role": "Senior System Engineer",
            "query_text": "Investigasi P1 Core Firewall Outage dan Accounting Server",
            "telemetry_context": {"netdata_cpu_usage": 99.0},
        }
        res = self.gateway.handle_request(req)

        self.assertEqual(res["query_id"], "Q-AUTONOMOUS-1")
        self.assertIn("digital_twin_state", res)
        self.assertEqual(res["digital_twin_state"]["sandbox_status"], "COMPLETED")

        self.assertIn("mission_queue", res)
        self.assertIn("multi_agent_dialogue", res)
        self.assertEqual(res["multi_agent_dialogue"]["peer_verdict"], "VERIFIED")

        self.assertIn("workflow_plan", res)
        self.assertIn("knowledge_graph", res)
        self.assertIn("experience_record", res)
        self.assertIn("improvement_plan", res)

    def test_gateway_autonomous_api_methods(self):
        twin = self.gateway.get_digital_twin_state()
        self.assertEqual(twin["sandbox_status"], "COMPLETED")

        queue = self.gateway.get_mission_queue()
        self.assertIn("Firewall Outage", queue["active_mission"])

        dialogue = self.gateway.run_multi_agent_dialogue("INC-API-MA", "High CPU")
        self.assertEqual(dialogue["peer_agreement_pct"], 96)

        plan = self.gateway.generate_operational_plan("PostgreSQL DB", "Upgrade")
        self.assertEqual(len(plan["steps"]), 5)


if __name__ == "__main__":
    unittest.main()
