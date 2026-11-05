"""
Unit Tests for Visual Postmortem & Executive Report Generator Engine
Path: tests/unit/test_visual_postmortem_engine.py
"""

import os
import unittest
from SERVER.python_ai_core.governance.visual_postmortem_engine import VisualPostmortemEngine
from SERVER.jarvis.command.intent_router import JarvisCommandIntentRouter, JarvisIntent
from SERVER.jarvis.runtime.intent_query_handler import IntentQueryHandlerMixin


class DummyActionContext:
    def __init__(self):
        self.action_taken = None
        self.execution_status = None
        self.session_id = "test-session"


class DummyVoiceBridge(IntentQueryHandlerMixin):
    def __init__(self):
        self.noc_bridge = None


class TestVisualPostmortemEngine(unittest.TestCase):
    def setUp(self):
        self.output_dir = "/tmp/test_reports"
        self.engine = VisualPostmortemEngine(output_dir=self.output_dir)
        self.router = JarvisCommandIntentRouter()

    def test_fetch_incident_data_structure(self):
        data = self.engine.fetch_incident_data("4102")
        self.assertIn("incident_id", data)
        self.assertIn("device_name", data)
        self.assertIn("duration_minutes", data)
        self.assertIn("metrics_before", data)
        self.assertIn("metrics_after", data)
        self.assertIn("events", data)

    def test_generate_html_report_elements(self):
        data = self.engine.fetch_incident_data("4102")
        html = self.engine.generate_html_report(data)
        
        # Verify essential visual & structural sections
        self.assertIn("Executive Incident Post-Mortem", html)
        self.assertIn("Komparasi Metrik Telemetri", html)
        self.assertIn("Diagram Alur Kausalitas", html)
        self.assertIn("Matriks Evaluasi Alternatif Keputusan", html)
        self.assertIn("DPO Continuous Learning", html)
        self.assertIn("@media print", html)

    def test_generate_visual_report_file_creation(self):
        res = self.engine.generate_visual_report("4102")
        self.assertTrue(res["success"])
        self.assertTrue(os.path.exists(res["filepath"]))
        self.assertTrue(res["filepath"].endswith(".html"))
        self.assertIn("Laporan visual postmortem", res["voice_summary"])

    def test_voice_intent_routing_for_postmortem(self):
        queries = [
            "JARVIS, buatkan visual postmortem dan timeline insiden kasir hari ini dalam format PDF/HTML",
            "tolong buatkan visual postmortem insiden",
            "generate postmortem laporan eksekutif",
            "export postmortem kasir"
        ]
        for q in queries:
            res = self.router.classify(q)
            self.assertEqual(res.intent, JarvisIntent.QUERY, f"Failed for query: {q}")

    def test_voice_query_handler_postmortem_execution(self):
        bridge = DummyVoiceBridge()
        ctx = DummyActionContext()
        intent_res = self.router.classify("JARVIS buatkan visual postmortem insiden kasir hari ini")
        
        resp_text, ctx = bridge._handle_query(
            "buatkan visual postmortem insiden kasir hari ini",
            intent_res,
            "PROFESSIONAL",
            ctx
        )
        self.assertEqual(ctx.action_taken, "GENERATE_VISUAL_POSTMORTEM")
        self.assertEqual(ctx.execution_status, "SUCCESS")
        self.assertIn("visual postmortem", resp_text.lower())


if __name__ == "__main__":
    unittest.main()
