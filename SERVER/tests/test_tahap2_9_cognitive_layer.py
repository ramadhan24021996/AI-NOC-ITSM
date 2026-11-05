"""
SERVER.tests.test_tahap2_9_cognitive_layer
===========================================
Tahap 2.9 — Production-Grade Cognitive Layer & Thinking Dashboard Test Suite

Menguji 13 modul Cognitive Layer & integrasi NOCIntegrationGateway:
  1. ConversationContextTracker
  2. LLMContextAnalyzer
  3. GoalManager
  4. KnowledgeGapDetector
  5. MemoryCandidateDetector & LearningValidator
  6. EvidenceManager
  7. ConfidenceResolver
  8. ConflictResolver
  9. ToolRequirementDetector
  10. ResponseValidator
  11. ResponseStrategyManager
  12. CognitiveDecisionEngine
  13. NOCIntegrationGateway Integration
"""
import unittest
import asyncio
from SERVER.orchestrator.cognitive.context_tracker import ConversationContextTracker
from SERVER.orchestrator.cognitive.llm_analyzer import LLMContextAnalyzer
from SERVER.orchestrator.cognitive.goal_manager import GoalManager
from SERVER.orchestrator.cognitive.knowledge_gap_detector import KnowledgeGapDetector
from SERVER.orchestrator.cognitive.memory_candidate_detector import MemoryCandidateDetector, MemoryCandidateResult
from SERVER.orchestrator.cognitive.learning_validator import LearningValidator
from SERVER.orchestrator.cognitive.evidence_manager import EvidenceManager
from SERVER.orchestrator.cognitive.confidence_resolver import ConfidenceResolver
from SERVER.orchestrator.cognitive.conflict_resolver import ConflictResolver
from SERVER.orchestrator.cognitive.tool_requirement_detector import ToolRequirementDetector
from SERVER.orchestrator.cognitive.decision_engine import CognitiveDecisionEngine
from SERVER.orchestrator.cognitive.response_validator import ResponseValidator
from SERVER.orchestrator.cognitive.response_strategy import ResponseStrategyManager
from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway


class TestCognitiveLayerComponents(unittest.TestCase):
    def test_context_tracker(self):
        tracker = ConversationContextTracker()
        state = tracker.update_context("sess_1", "Diagnosa CPU spike di srv-accounting-01", {"severity": "high"})
        self.assertEqual(state.topic, "CPU High Utilization")
        self.assertEqual(state.device, "srv-accounting-01")
        self.assertEqual(state.stage, "Diagnosis")

    def test_llm_analyzer(self):
        analyzer = LLMContextAnalyzer()
        res = analyzer.analyze("Restart service redis di host 10.0.0.1", {"severity": "medium"})
        self.assertEqual(res.intent, "execute_action")
        self.assertIn("10.0.0.1", res.entities)
        self.assertTrue(res.requires_tool)

    def test_goal_manager(self):
        gm = GoalManager()
        g1 = gm.update_goal("sess_2", "Kenapa CPU tinggi?", "diagnose_incident", "Diagnosis")
        self.assertEqual(g1.active_goal, "Find RCA")

        g2 = gm.update_goal("sess_2", "Restart nginx", "execute_action", "Recovery")
        self.assertEqual(g2.active_goal, "Recovery Execution")
        self.assertEqual(g2.previous_goal, "Find RCA")

    def test_knowledge_gap_detector(self):
        detector = KnowledgeGapDetector()
        res = detector.detect("Bagaimana penanganan SOP Oracle RAC?", [])
        self.assertTrue(res.has_gap)
        self.assertIn("Oracle Rac", res.missing_topic)
        self.assertIsNotNone(res.suggested_prompt)
        self.assertIn("Apakah Anda ingin mengajarkan SOP baru", res.suggested_prompt or "")

    def test_memory_candidate_and_validator(self):
        mem_det = MemoryCandidateDetector()
        val = LearningValidator()

        # Valid candidate
        cand1 = mem_det.detect("Mulai hari ini backup dilakukan pukul 23.00")
        self.assertTrue(cand1.is_candidate)
        val1 = val.validate(cand1)
        self.assertTrue(val1.is_valid)

        # Invalid candidate (invalid percentage > 100%)
        cand2 = MemoryCandidateResult(is_candidate=True, fact_text="Mulai besok CPU 150%")
        val2 = val.validate(cand2)
        self.assertFalse(val2.is_valid)
        self.assertIn("150%", val2.rejection_reason)

    def test_evidence_manager(self):
        em = EvidenceManager()
        summary = em.evaluate(has_telemetry=True, has_memory=True, has_rag=True, has_conversation=True)
        self.assertEqual(summary.primary_evidence, "Telemetry")
        self.assertEqual(summary.secondary_evidence, "Memory")
        self.assertEqual(summary.weight_map["Telemetry"], 0.98)

    def test_confidence_resolver(self):
        cr = ConfidenceResolver()
        card = cr.resolve(intent_confidence=0.98, tool_confidence=0.95, knowledge_confidence=0.85, evidence_primary_weight=0.98)
        self.assertGreaterEqual(card.overall_confidence, 0.85)
        self.assertEqual(card.level_label, "GREEN")

        gauge = cr.get_gauge(card)
        self.assertGreaterEqual(gauge.score_pct, 85)
        self.assertEqual(gauge.color_indicator, "GREEN")

    def test_conflict_resolver(self):
        c_res = ConflictResolver()
        telemetry = {"netdata_cpu_usage": 20.0, "agent_cpu_usage": 98.0}
        res = c_res.resolve_telemetry_conflict(telemetry)
        self.assertTrue(res.has_conflict)
        self.assertEqual(res.resolved_value, 98.0)
        self.assertEqual(res.authority_source, "Host Agent")

    def test_tool_requirement_detector(self):
        tr = ToolRequirementDetector()

        # Conceptual query -> No tool
        res1 = tr.detect("Jelaskan konsep VLAN")
        self.assertFalse(res1.requires_tool)

        # Inspection query -> Tool required
        res2 = tr.detect("Cek penggunaan RAM server")
        self.assertTrue(res2.requires_tool)

    def test_response_validator(self):
        rv = ResponseValidator()

        # False execution claim intercepted
        res1 = rv.validate("Restart database telah dieksekusi dengan sukses.", tools_executed=False)
        self.assertFalse(res1.is_valid)
        self.assertTrue(res1.action_intercepted)
        self.assertIn("menunggu approval", res1.validated_response)

        # Valid text allowed
        res2 = rv.validate("Saya merekomendasikan restart database.", tools_executed=False)
        self.assertTrue(res2.is_valid)

    def test_response_strategy_manager(self):
        rsm = ResponseStrategyManager()
        txt1 = rsm.apply_persona("Ditemukan BGP flap.", user_role="NOC L2 Engineer")
        self.assertIn("[SENIOR ENGINEER ANALYSIS]", txt1)

        txt2 = rsm.apply_persona("System recovery completed.", user_role="Executive VP")
        self.assertIn("[EXECUTIVE SUMMARY]", txt2)


class TestCognitiveGatewayIntegration(unittest.TestCase):
    def setUp(self):
        self.gateway = NOCIntegrationGateway()

    def test_gateway_handle_request_with_cognitive_payloads(self):
        req = {
            "query_id": "Q-COG-1",
            "user_id": "U-100",
            "user_role": "NOC L2",
            "query_text": "Kenapa CPU tinggi di srv-accounting-01?",
            "telemetry_context": {"netdata_cpu_usage": 20.0, "agent_cpu_usage": 98.0, "severity": "high"},
        }
        res = self.gateway.handle_request(req)

        self.assertEqual(res["query_id"], "Q-COG-1")
        self.assertIn("[SENIOR ENGINEER ANALYSIS]", res["answer_text"])

        # Dashboard thinking panels presence
        self.assertIn("cognitive_state", res)
        self.assertEqual(res["cognitive_state"]["device"], "srv-accounting-01")

        self.assertIn("ai_confidence_gauge", res)
        self.assertEqual(res["ai_confidence_gauge"]["color_indicator"], "GREEN")

        self.assertIn("jarvis_thinking", res)
        self.assertEqual(res["jarvis_thinking"]["intent_stage"], "COMPLETED")

        self.assertIn("decision_timeline", res)
        self.assertGreater(len(res["decision_timeline"]), 3)

        self.assertIn("conflict_resolution", res)
        self.assertTrue(res["conflict_resolution"]["has_conflict"])

    def test_gateway_handle_request_async_with_cognitive_payloads(self):
        async def run_async():
            req = {
                "query_id": "Q-COG-ASYNC",
                "user_id": "U-200",
                "user_role": "Executive Manager",
                "query_text": "Jelaskan status ketersediaan sistem",
                "telemetry_context": {"severity": "low"},
            }
            return await self.gateway.handle_request_async(req)

        res = asyncio.run(run_async())
        self.assertEqual(res["query_id"], "Q-COG-ASYNC")
        self.assertIn("[EXECUTIVE SUMMARY]", res["answer_text"])
        self.assertIn("ai_confidence_gauge", res)
        self.assertIn("decision_timeline", res)


if __name__ == "__main__":
    unittest.main()
