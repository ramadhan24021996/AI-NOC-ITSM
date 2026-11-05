"""
SERVER.tests.test_tahap2_8_context_conversation_pipeline
=========================================================
Tahap 2.8 — Pre-LLM Cognitive Pipeline Validation Suite

Menguji 4 komponen Pre-LLM:
  1. ConversationManager
  2. ContextBuilder
  3. ContextAnalyzer
  4. ConversationPlanner
dan integrasi end-to-end dengan NOCExecutionCoordinator.
"""
import unittest
import asyncio
from SERVER.contracts.schemas import IncidentQueryContract
from SERVER.orchestrator.conversation.conversation_manager import ConversationManager
from SERVER.orchestrator.context.context_builder import ContextBuilder
from SERVER.orchestrator.context.context_analyzer import ContextAnalyzer
from SERVER.orchestrator.conversation.conversation_planner import ConversationPlanner, DialogueStrategy
from SERVER.orchestrator.coordinator.noc_execution_coordinator import NOCExecutionCoordinator


class TestConversationManager(unittest.TestCase):
    def setUp(self):
        self.mgr = ConversationManager(default_max_turns=4)

    def test_add_turn_and_retrieve_history(self):
        conv_id = "test_conv_001"
        self.mgr.add_turn(conv_id, "user", "Diagnosa CPU spike di router-01", trace_id="TRC-1")
        self.mgr.add_turn(conv_id, "assistant", "Ditemukan CPU spike 98% akibat BGP flap.", trace_id="TRC-1")

        history = self.mgr.get_history(conv_id)
        self.assertEqual(len(history), 2)
        self.assertEqual(history[0]["role"], "user")
        self.assertEqual(history[1]["role"], "assistant")
        self.assertIn("BGP flap", history[1]["content"])

    def test_prune_history(self):
        conv_id = "test_conv_prune"
        for i in range(6):
            self.mgr.add_turn(conv_id, "user", f"Turn query {i}")

        history = self.mgr.get_history(conv_id)
        self.assertEqual(len(history), 4)  # max_turns=4
        self.assertEqual(history[0]["content"], "Turn query 2")
        self.assertEqual(history[-1]["content"], "Turn query 5")

    def test_thread_summary(self):
        conv_id = "test_summary"
        self.mgr.add_turn(conv_id, "user", "Apa status router A?")
        self.mgr.add_turn(conv_id, "assistant", "Router A online.")

        summary = self.mgr.get_thread_summary(conv_id)
        self.assertIn("User: Apa status router A?", summary)
        self.assertIn("Assistant: Router A online.", summary)


class TestContextBuilder(unittest.TestCase):
    def setUp(self):
        self.builder = ContextBuilder()

    def test_build_payload(self):
        query = "Diagnosa high latency di Core Switch 01"
        history = [{"role": "user", "content": "Halo"}, {"role": "assistant", "content": "Halo, ada yang bisa dibantu?"}]
        rag_chunks = [{"title": "SOP Switch Latency", "content": "Cek port buffer overflow.", "score": 0.9}]
        telemetry = {"cpu_usage": 92, "severity": "high"}

        payload = self.builder.build(
            query_text=query,
            conversation_history=history,
            rag_chunks=rag_chunks,
            telemetry_context=telemetry,
            user_role="L2 Engineer",
        )

        self.assertEqual(payload.query_text, query)
        self.assertEqual(payload.user_role, "L2 Engineer")
        self.assertIn("Cek port buffer overflow", payload.formatted_rag)
        self.assertIn("cpu_usage: 92", payload.formatted_telemetry)
        self.assertGreater(payload.estimated_token_count, 10)


class TestContextAnalyzer(unittest.TestCase):
    def setUp(self):
        self.builder = ContextBuilder()
        self.analyzer = ContextAnalyzer()

    def test_token_budget_evaluation(self):
        payload = self.builder.build(
            query_text="A" * 5000,  # ~1250 tokens
            telemetry_context={"severity": "low"},  # budget low = 1000
        )
        res = self.analyzer.analyze(payload, severity_label="low")
        self.assertTrue(res.is_token_overflow)
        self.assertGreater(res.token_budget_usage_pct, 100.0)

    def test_rag_deduplication(self):
        duplicate_chunks = [
            {"title": "Doc1", "content": "SOP penanganan link down router 10.0.0.1"},
            {"title": "Doc2", "content": "SOP penanganan link down router 10.0.0.1"},  # duplicate
        ]
        payload = self.builder.build(
            query_text="Link down link 10.0.0.1",
            rag_chunks=duplicate_chunks,
        )
        res = self.analyzer.analyze(payload, severity_label="medium")
        self.assertEqual(len(res.deduplicated_rag_chunks), 1)

    def test_missing_entity_detection(self):
        payload = self.builder.build(
            query_text="Tolong diagnosa kenapa terjadi error dan down?",
            telemetry_context={"severity": "medium"},
        )
        res = self.analyzer.analyze(payload, severity_label="medium")
        self.assertTrue(res.has_ambiguity)
        self.assertIn("Target Node/IP/Service Name", res.missing_entities)


class TestConversationPlanner(unittest.TestCase):
    def setUp(self):
        self.builder = ContextBuilder()
        self.analyzer = ContextAnalyzer()
        self.planner = ConversationPlanner()

    def test_chain_of_thought_for_critical_severity(self):
        payload = self.builder.build(
            query_text="Diagnosa router core 10.10.10.1 down",
            telemetry_context={"severity": "critical"},
        )
        analysis = self.analyzer.analyze(payload, severity_label="critical")
        plan = self.planner.plan(analysis)

        self.assertEqual(plan.strategy, DialogueStrategy.CHAIN_OF_THOUGHT)
        self.assertIn("Chain-of-Thought", plan.system_instructions)
        self.assertFalse(plan.should_bypass_llm)

    def test_clarification_required_for_ambiguous_query(self):
        payload = self.builder.build(
            query_text="Tolong diagnosa masalah jaringan",
            telemetry_context={"severity": "low"},
        )
        analysis = self.analyzer.analyze(payload, severity_label="low")
        plan = self.planner.plan(analysis)

        self.assertEqual(plan.strategy, DialogueStrategy.CLARIFICATION_REQUIRED)
        self.assertTrue(plan.should_bypass_llm)
        self.assertIsNotNone(plan.preset_response)
        self.assertIn("Mohon berikan informasi tambahan", plan.preset_response)

    def test_action_execution_intent(self):
        payload = self.builder.build(
            query_text="Restart service nginx di host 192.168.1.50",
            telemetry_context={"severity": "medium"},
        )
        analysis = self.analyzer.analyze(payload, severity_label="medium")
        plan = self.planner.plan(analysis)

        self.assertEqual(plan.strategy, DialogueStrategy.ACTION_EXECUTION)
        self.assertIn("EKSEKUSI OPERASIONAL", plan.system_instructions)


class TestPreLLMPipelineIntegration(unittest.TestCase):
    def setUp(self):
        self.coordinator = NOCExecutionCoordinator()

    def test_coordinator_end_to_end_sync(self):
        conv_id = "integration_conv_123"

        # Turn 1: User asks query
        q1 = IncidentQueryContract(
            query_id="Q-001",
            user_id="U-1",
            user_role="NOC L1",
            query_text="Investigasi BGP flap pada host 10.0.0.5",
            conversation_id=conv_id,
            telemetry_context={"severity": "high"},
        )
        resp1 = self.coordinator.execute(q1)
        self.assertIsNotNone(resp1.answer_text)
        self.assertEqual(resp1.query_id, "Q-001")

        # Turn 2: Follow-up query in same conversation
        q2 = IncidentQueryContract(
            query_id="Q-002",
            user_id="U-1",
            user_role="NOC L1",
            query_text="Bagaimana cara mitigasi tercepat?",
            conversation_id=conv_id,
            telemetry_context={"severity": "high"},
        )
        resp2 = self.coordinator.execute(q2)
        self.assertIsNotNone(resp2.answer_text)

        # Verifikasi conversation manager menyimpan 4 turn (2 turn user, 2 turn assistant)
        history = self.coordinator._conv_manager.get_history(conv_id)
        self.assertEqual(len(history), 4)
        self.assertEqual(history[0]["content"], q1.query_text)
        self.assertEqual(history[2]["content"], q2.query_text)

    def test_coordinator_end_to_end_async(self):
        async def run_async():
            q = IncidentQueryContract(
                query_id="Q-ASYNC-01",
                user_id="U-2",
                user_role="Admin",
                query_text="Restart service redis pada node 10.0.1.20",
                telemetry_context={"severity": "medium"},
            )
            return await self.coordinator.execute_async(q)

        resp = asyncio.run(run_async())
        self.assertEqual(resp.query_id, "Q-ASYNC-01")
        self.assertIsNotNone(resp.answer_text)


if __name__ == "__main__":
    unittest.main()
