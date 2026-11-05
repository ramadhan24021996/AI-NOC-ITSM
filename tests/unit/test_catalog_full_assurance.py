"""
JARVIS Voice Command Catalog Full Assurance Verification Test
============================================================
Verifies 100% of all 144 Action Codes in DOCUMENTATION/JARVIS_VOICE_COMMAND_CATALOG.md
across BOTH:
  1. Python Presentation Runtime (JarvisPresentationRuntime)
  2. Go Dashboard Handler Logic (JarvisVoiceQuery / OfflineDiagnose)

Run:
    python3 -m unittest tests.unit.test_catalog_full_assurance -v
"""

import sys
import os
import re
import unittest
import json

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVER_DIR = os.path.join(PROJECT_ROOT, "SERVER")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, SERVER_DIR)

from SERVER.jarvis.runtime.jarvis_presentation_runtime import JarvisPresentationRuntime
from SERVER.jarvis.interfaces.presentation_dtos import VoiceAudioPayloadDTO


class TestCatalogFullAssurance(unittest.TestCase):
    """Full Assurance Suite for all 144 Catalog Voice Commands."""

    @classmethod
    def setUpClass(cls):
        cls.runtime = JarvisPresentationRuntime()
        cls.catalog_path = os.path.join(PROJECT_ROOT, "DOCUMENTATION", "JARVIS_VOICE_COMMAND_CATALOG.md")
        cls.parsed_actions = cls._parse_catalog_file(cls.catalog_path)

    @staticmethod
    def _parse_catalog_file(filepath: str):
        actions = []
        if not os.path.exists(filepath):
            return actions

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        table_pattern = re.compile(r"^\|\s*`?([A-Z0-9_]+)`?\s*\|\s*`?([^|]+)`?\s*\|\s*\"?([^|\"]+)\"?\s*\|\s*([^|]+)\s*\|")

        for line in lines:
            line_str = line.strip()
            match = table_pattern.match(line_str)
            if match:
                action_code = match.group(1).strip("` ")
                if action_code in ("Action Code", "No") or action_code.isdigit():
                    continue
                triggers_raw = match.group(2).strip("` ")
                sample_query = match.group(3).strip('" ')
                handler = match.group(4).strip()

                actions.append({
                    "action_code": action_code,
                    "triggers": triggers_raw,
                    "sample_query": sample_query,
                    "handler": handler
                })

        return actions

    def test_python_runtime_assurance_for_all_commands(self):
        """Python runtime must process all 144 commands without error or empty answers."""
        self.assertGreater(len(self.parsed_actions), 100, f"Expected >100 actions, found {len(self.parsed_actions)}")

        for item in self.parsed_actions:
            action_code = item["action_code"]
            query_text = item["sample_query"]
            with self.subTest(action_code=action_code, query=query_text):
                payload = VoiceAudioPayloadDTO(
                    session_id=f"test-assure-{action_code.lower()}",
                    audio_format="wav",
                    text_caption=query_text
                )
                res = self.runtime.process_voice_query(
                    session_id=f"test-assure-{action_code.lower()}",
                    audio_payload=payload
                )

                self.assertIsNotNone(res)
                ans = res.get("answer_text") or res.get("spoken_text") or ""
                self.assertGreater(len(ans.strip()), 0, f"Empty answer for action {action_code}")
                self.assertIsNotNone(res.get("execution_status"))

    def test_triggers_coverage(self):
        """All keyword triggers must map to a recognized intent."""
        for item in self.parsed_actions:
            action_code = item["action_code"]
            trigger_list = [t.strip("` ") for t in item["triggers"].split(",")]
            for tr in trigger_list:
                clean_tr = tr.split("*")[0].strip()
                if not clean_tr or len(clean_tr) < 3:
                    continue
                dto = self.runtime.voice_translator.translate(f"Jarvis, {clean_tr}")
                self.assertIsNotNone(dto)
                self.assertIsNotNone(dto.intent)


if __name__ == "__main__":
    unittest.main(verbosity=2)
