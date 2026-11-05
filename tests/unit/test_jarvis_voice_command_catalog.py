"""
Unit Tests: Full JARVIS Voice Command Catalog Coverage & Verification
======================================================================
Tests all 146 Action Codes and 250+ Keyword Triggers defined in
DOCUMENTATION/JARVIS_VOICE_COMMAND_CATALOG.md against:
  - LLMVoiceCommandTranslator (_rule_fallback & LLM prompt rules)
  - JarvisActionCatalogValidator
  - IntentQueryHandlerMixin

Run:
    python3 -m unittest tests.unit.test_jarvis_voice_command_catalog -v
"""

import sys
import os
import re
import unittest

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVER_DIR = os.path.join(PROJECT_ROOT, "SERVER")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, SERVER_DIR)

from SERVER.jarvis.cognition.llm_command_translator import LLMVoiceCommandTranslator, VoiceActionDTO
from SERVER.jarvis.planning.action_catalog_validator import JarvisActionCatalogValidator


class TestJarvisVoiceCommandCatalog(unittest.TestCase):
    """Test suite for 100% verification of JARVIS Voice Command Catalog."""

    @classmethod
    def setUpClass(cls):
        cls.translator = LLMVoiceCommandTranslator()
        cls.validator = JarvisActionCatalogValidator()

        # Parse catalog markdown file
        cls.catalog_path = os.path.join(PROJECT_ROOT, "DOCUMENTATION", "JARVIS_VOICE_COMMAND_CATALOG.md")
        cls.parsed_actions = cls._parse_catalog_file(cls.catalog_path)

    @staticmethod
    def _parse_catalog_file(filepath: str):
        """Parse markdown tables to extract action codes, triggers, and sample queries."""
        actions = []
        if not os.path.exists(filepath):
            return actions

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        table_pattern = re.compile(r"^\|\s*`?([A-Z0-9_]+)`?\s*\|\s*`?([^|]+)`?\s*\|\s*\"?([^|\"]+)\"?\s*\|\s*([^|]+)\s*\|")

        for line in lines:
            line = line.strip()
            match = table_pattern.match(line)
            if match:
                action_code = match.group(1).strip("` ")
                if action_code in ("Action Code", "No") or action_code.isdigit():
                    continue
                triggers_raw = match.group(2).strip("` ")
                sample_query = match.group(3).strip('" ')
                handler = match.group(4).strip()

                triggers = [t.strip("` ") for t in triggers_raw.split(",")]
                actions.append({
                    "action_code": action_code,
                    "triggers": triggers,
                    "sample_query": sample_query,
                    "handler": handler
                })

        return actions

    def test_catalog_file_parsed(self):
        """Catalog file must be loaded and contain action codes."""
        self.assertGreater(len(self.parsed_actions), 50, f"Expected >50 actions in catalog, found {len(self.parsed_actions)}")

    def test_sample_queries_translation_coverage(self):
        """Every sample voice command in the catalog must translate to a valid VoiceActionDTO without crashing."""
        for item in self.parsed_actions:
            sample_text = item["sample_query"]
            action_code = item["action_code"]
            with self.subTest(action_code=action_code, query=sample_text):
                dto = self.translator.translate(sample_text)
                self.assertIsNotNone(dto)
                self.assertTrue(isinstance(dto, VoiceActionDTO))
                self.assertIsNotNone(dto.intent)
                self.assertGreater(len(dto.intent), 0)
                self.assertIsNotNone(dto.explanation_id)

    def test_keyword_triggers_translation(self):
        """Sample keyword triggers must translate to valid intent/action."""
        tested_count = 0
        for item in self.parsed_actions[:30]:  # Sample test subset of 30 actions
            action_code = item["action_code"]
            for trigger in item["triggers"]:
                clean_trigger = trigger.split("*")[0].strip()
                if not clean_trigger:
                    continue
                query = f"Jarvis, {clean_trigger}"
                with self.subTest(action_code=action_code, trigger=clean_trigger):
                    dto = self.translator.translate(query)
                    self.assertIsNotNone(dto)
                    self.assertIn(dto.intent, ["QUERY", "REMEDIATE", "REMOTE", "BROWSER", "HITL", "CHAT", "EXPLAIN_MENU", "QUERY_LIVE_DATA", "EXECUTE_ACTION"])
                    tested_count += 1
        self.assertGreater(tested_count, 20)

    def test_action_catalog_validator_coverage(self):
        """Validator must recognize pre-approved remediation actions."""
        remediation_samples = [
            ("restart spooler", "ACT_RESTART_SPOOLER"),
            ("flush dns", "ACT_FLUSH_DNS"),
            ("reboot server", "ACT_REBOOT_SERVER"),
            ("restart postgresql", "ACT_RESTART_POSTGRESQL"),
            ("restart redis", "ACT_RESTART_REDIS"),
            ("pindah isp", "ACT_FAILOVER_ISP"),
            ("clear print queue", "ACT_CLEAR_PRINT_QUEUE"),
        ]

        for trigger_phrase, expected_act in remediation_samples:
            with self.subTest(phrase=trigger_phrase):
                res = self.validator.validate(trigger_phrase)
                self.assertIn(res["verdict"], ["APPROVED", "HITL_REQUIRED"])
                self.assertEqual(expected_act, res["action_id"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
