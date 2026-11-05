import unittest
import sys
import os

# Ensure SERVER/python_ai_core is in PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.intent_router import IntentRouter
from core.jarvis_response_engine import JarvisResponseEngine
from core.workflow_orchestrator import WorkflowOrchestrator

class TestJarvisIntentPipeline(unittest.TestCase):
    """
    Automated Unit & Integration Test Suite for Jarvis Intent Router & Response Engine
    as specified in the Enterprise AI OS Multi-Agent System Architecture Plan.
    """

    def setUp(self):
        self.router = IntentRouter()
        self.response_engine = JarvisResponseEngine()
        self.orchestrator = WorkflowOrchestrator()

    def test_noc_intent_classification(self):
        query = "Cek status router TMS"
        result = self.router.classify_and_split(query)
        self.assertEqual(result["intent"], "NOC")

    def test_general_chat_intent_classification(self):
        query = "Jelaskan apa itu DNS"
        result = self.router.classify_and_split(query)
        self.assertEqual(result["intent"], "GENERAL_CHAT")

    def test_mixed_intent_classification_and_splitting(self):
        query = "Internet kantor mati, sekalian jelaskan apa itu BGP"
        result = self.router.classify_and_split(query)
        self.assertEqual(result["intent"], "MIXED")
        self.assertIn("noc_query", result)
        self.assertIn("general_query", result)
        self.assertTrue(len(result["noc_query"]) > 0)
        self.assertTrue(len(result["general_query"]) > 0)

    def test_jarvis_response_engine_formatting(self):
        noc_raw = "Koneksi gateway time out pada interface eth0."
        formatted_noc = self.response_engine.format_as_jarvis(noc_raw, "NOC")
        self.assertTrue(any(prefix in formatted_noc for prefix in self.response_engine.NOC_PREFIXES))

        gen_raw = "BGP adalah Border Gateway Protocol."
        formatted_gen = self.response_engine.format_as_jarvis(gen_raw, "GENERAL_CHAT")
        self.assertTrue(any(formatted_gen.startswith(p) for p in ["Tentu", "Baik", "Berikut", "Sesuai"]))

    def test_orchestrator_process_query_noc(self):
        query = "Jarvis ada Isu apa"
        res = self.orchestrator.process_query("test_session_1", query)
        self.assertIn("answer", res)
        self.assertEqual(res.get("intent"), "NOC")
        self.assertTrue(len(res["answer"]) > 0)

    def test_orchestrator_process_query_general_chat(self):
        query = "Halo cantik"
        res = self.orchestrator.process_query("test_session_2", query)
        self.assertIn("answer", res)
        self.assertEqual(res.get("intent"), "GENERAL_CHAT")
        self.assertTrue(len(res["answer"]) > 0)

if __name__ == "__main__":
    unittest.main()
