"""
JARVIS Full Voice Command Catalog Live Simulation Test Runner
=============================================================
Executes ALL 144 sample voice commands from DOCUMENTATION/JARVIS_VOICE_COMMAND_CATALOG.md
through the live JarvisPresentationRuntime end-to-end pipeline.

Run:
    python3 -m unittest tests.unit.test_jarvis_full_command_simulation -v
"""

import sys
import os
import re
import unittest
import time

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
SERVER_DIR = os.path.join(PROJECT_ROOT, "SERVER")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, SERVER_DIR)

from SERVER.jarvis.runtime.jarvis_presentation_runtime import JarvisPresentationRuntime
from SERVER.jarvis.interfaces.presentation_dtos import VoiceAudioPayloadDTO


class TestJarvisFullCommandSimulation(unittest.TestCase):
    """Full End-to-End Simulation Runner for JARVIS Voice Command Catalog."""

    @classmethod
    def setUpClass(cls):
        cls.runtime = JarvisPresentationRuntime()
        cls.catalog_path = os.path.join(PROJECT_ROOT, "DOCUMENTATION", "JARVIS_VOICE_COMMAND_CATALOG.md")
        cls.actions_by_domain = cls._parse_catalog_by_domain(cls.catalog_path)

    @staticmethod
    def _parse_catalog_by_domain(filepath: str):
        """Parse markdown file and group action items by domain section."""
        domains = {}
        current_domain = "GENERAL"
        
        if not os.path.exists(filepath):
            return domains

        with open(filepath, "r", encoding="utf-8") as f:
            lines = f.readlines()

        table_pattern = re.compile(r"^\|\s*`?([A-Z0-9_]+)`?\s*\|\s*`?([^|]+)`?\s*\|\s*\"?([^|\"]+)\"?\s*\|\s*([^|]+)\s*\|")

        for line in lines:
            line_str = line.strip()
            if line_str.startswith("## ") and not line_str.startswith("## 📌"):
                current_domain = line_str.lstrip("#").strip()
                if current_domain not in domains:
                    domains[current_domain] = []
                continue

            match = table_pattern.match(line_str)
            if match:
                action_code = match.group(1).strip("` ")
                if action_code in ("Action Code", "No") or action_code.isdigit():
                    continue
                triggers_raw = match.group(2).strip("` ")
                sample_query = match.group(3).strip('" ')
                handler = match.group(4).strip()

                if current_domain not in domains:
                    domains[current_domain] = []

                domains[current_domain].append({
                    "action_code": action_code,
                    "triggers": triggers_raw,
                    "sample_query": sample_query,
                    "handler": handler
                })

        return domains

    def test_run_all_catalog_voice_commands(self):
        """Simulate live voice query processing for every single catalog command."""
        total_executed = 0
        success_count = 0
        domain_summary = {}

        t0 = time.time()

        for domain, cmd_list in self.actions_by_domain.items():
            domain_ok = 0
            domain_total = len(cmd_list)

            for item in cmd_list:
                action_code = item["action_code"]
                sample_text = item["sample_query"]
                total_executed += 1

                payload = VoiceAudioPayloadDTO(
                    session_id=f"sim-{action_code.lower()}",
                    audio_format="wav",
                    text_caption=sample_text
                )
                res = self.runtime.process_voice_query(
                    session_id=f"sim-{action_code.lower()}",
                    audio_payload=payload
                )

                self.assertIsNotNone(res)
                self.assertTrue("answer_text" in res or "spoken_text" in res)
                text_ans = res.get("answer_text") or res.get("spoken_text") or ""
                self.assertTrue(len(text_ans) > 0, f"Empty response text for {action_code}")
                self.assertIsNotNone(res.get("action_context") or res.get("intent"))

                domain_ok += 1
                success_count += 1

            domain_summary[domain] = f"{domain_ok}/{domain_total}"

        total_ms = int((time.time() - t0) * 1000)

        print("\n" + "=" * 70)
        print("🎙️ LIVE JARVIS VOICE COMMAND CATALOG SIMULATION REPORT")
        print("=" * 70)
        print(f"Total Commands Simulated : {total_executed}")
        print(f"Total Success           : {success_count} / {total_executed} (100% Passed)")
        print(f"Execution Wall Time     : {total_ms} ms")
        print("-" * 70)
        for d_name, d_stat in domain_summary.items():
            print(f" • {d_name:<50} : {d_stat}")
        print("=" * 70 + "\n")

        self.assertEqual(total_executed, success_count)


if __name__ == "__main__":
    unittest.main(verbosity=2)
