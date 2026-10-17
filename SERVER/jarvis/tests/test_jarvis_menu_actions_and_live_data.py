"""
test_jarvis_menu_actions_and_live_data.py
=========================================
Unit and Integration Test Suite for Jarvis 26-Menu Knowledge Registry,
Intent Translation, Live Data Queries, and Menu Action Execution.
"""

import unittest
from typing import Dict, Any

from SERVER.jarvis.cognition.menu_knowledge_registry import (
    MENU_KNOWLEDGE_REGISTRY,
    get_menu_info,
    search_menu_by_query
)
from SERVER.jarvis.cognition.llm_command_translator import (
    LLMVoiceCommandTranslator,
    VoiceActionDTO
)
from SERVER.jarvis.noc.noc_bridge import JarvisNOCBridge


class TestJarvis26MenuIntegration(unittest.TestCase):
    """Test suite for 26-menu Jarvis Assistant Integration."""

    def setUp(self):
        self.translator = LLMVoiceCommandTranslator(llm_router=None)
        self.bridge = JarvisNOCBridge()

    def test_menu_registry_completeness(self):
        """Verifikasi bahwa 26 menu registered dengan atribut yang valid."""
        expected_menu_count = 26
        self.assertGreaterEqual(
            len(MENU_KNOWLEDGE_REGISTRY),
            expected_menu_count,
            f"Registri menu harus memiliki minimal {expected_menu_count} panel terdaftar."
        )

        for panel_id, info in MENU_KNOWLEDGE_REGISTRY.items():
            self.assertIn("title", info, f"Panel {panel_id} harus memiliki title")
            self.assertIn("category", info, f"Panel {panel_id} harus memiliki category")
            self.assertIn("description", info, f"Panel {panel_id} harus memiliki description")
            self.assertIn("submodules", info, f"Panel {panel_id} harus memiliki submodules")
            self.assertIn("live_query_endpoint", info, f"Panel {panel_id} harus memiliki live_query_endpoint")

    def test_search_menu_by_query(self):
        """Uji pencarian panel ID berdasarkan kata kunci ucapan."""
        self.assertEqual(search_menu_by_query("jelaskan ground truth rca"), "rca")
        self.assertEqual(search_menu_by_query("cek status printer"), "printer")
        self.assertEqual(search_menu_by_query("bagaimana pc health"), "pchealth")
        self.assertEqual(search_menu_by_query("tampilkan storage stats"), "storage")
        self.assertEqual(search_menu_by_query("buka governance center"), "gov")

    def test_explain_menu_intent_translation(self):
        """Uji penerjemahan perintah pertanyaan penjelasan menu."""
        dto: VoiceActionDTO = self.translator.translate("jelaskan fungsi ground truth rca")
        self.assertEqual(dto.intent, "EXPLAIN_MENU")
        self.assertEqual(dto.target_panel, "rca")
        self.assertIn("Ground Truth & Root Cause Analysis", dto.explanation_id)

    def test_printer_spooler_action_translation(self):
        """Uji penerjemahan perintah aksi restart spooler."""
        dto: VoiceActionDTO = self.translator.translate("restart print spooler di PC-02")
        self.assertEqual(dto.intent, "REMEDIATE")
        self.assertIn("restart", dto.explanation_id.lower())

    def test_noc_bridge_menu_queries_and_actions(self):
        """Uji query menu data dan eksekusi aksi via NOC Bridge."""
        # Query Live Data
        query_resp = self.bridge.query_menu_live_data("pchealth")
        self.assertIsNotNone(query_resp)

        # Execute Menu Action
        action_resp = self.bridge.execute_menu_action(
            action_code="RESTART_PRINT_SPOOLER",
            panel_id="printer",
            parameters={"hostname": "PC-TEST-01"}
        )
        self.assertEqual(action_resp.action_taken, "RESTART_PRINT_SPOOLER")


if __name__ == "__main__":
    unittest.main()
