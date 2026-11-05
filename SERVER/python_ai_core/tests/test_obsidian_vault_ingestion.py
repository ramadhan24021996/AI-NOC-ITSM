"""
Automated Unit & Integration Tests for Obsidian Vault Ingestion & SOP Governance Integration.
Ensures zero crashes, safe handling of malformed files, and reliable dynamic SOP binding.
"""

import os
import sys
import unittest
import tempfile
import shutil
import time

server_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
python_ai_core_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if server_root not in sys.path:
    sys.path.insert(0, server_root)
if python_ai_core_root not in sys.path:
    sys.path.insert(0, python_ai_core_root)

from governance.obsidian_vault_parser import ObsidianVaultParser
from governance.sop_registry_engine import SOPRegistryEngine
from services.obsidian_sync_daemon import ObsidianSyncDaemon


class TestObsidianVaultIngestion(unittest.TestCase):

    def setUp(self):
        self.test_dir = tempfile.mkdtemp(prefix="test_obsidian_vault_")
        self.sops_dir = os.path.join(self.test_dir, "sops")
        os.makedirs(self.sops_dir, exist_ok=True)

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_valid_sop_parsing_and_binding(self):
        """Tests parsing a valid Obsidian SOP file and binding intent in SOPRegistryEngine."""
        valid_sop_content = """---
sop_id: SOP_TEST_001
title: Test Flush Redis Ingress Cache
intent_keywords:
  - redis_cache
  - flush_redis
target_os: LINUX
command: redis-cli flushall
risk_score: 0.10
safety_level: PRE_APPROVED_AUTOMATIC
signed_by: NOC-Admin-RSA
signature: sha256_mock_signature_1234567890abcdef
status: ACTIVE
---

# Test SOP Document
Links: [[Topology-Redis-Primary]] and [[INC-2026-001]]
"""
        filepath = os.path.join(self.sops_dir, "SOP_TEST_001.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(valid_sop_content)

        parsed = ObsidianVaultParser.parse_file(filepath)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["doc_type"], "SOP")
        self.assertEqual(parsed["frontmatter"]["sop_id"], "SOP_TEST_001")
        self.assertIn("Topology-Redis-Primary", parsed["backlinks"])
        self.assertIn("INC-2026-001", parsed["backlinks"])

        # Test SOP Registry Engine Integration
        engine = SOPRegistryEngine(vault_dir=self.test_dir)
        bind_res = engine.match_and_bind_intent("High memory on redis_cache cluster")
        self.assertEqual(bind_res["binding_status"], "BOUND_TO_SIGNED_SOP")
        self.assertEqual(bind_res["sop_id"], "SOP_TEST_001")
        self.assertEqual(bind_res["command"], "redis-cli flushall")

    def test_malformed_yaml_does_not_crash_server(self):
        """Ensures corrupted YAML frontmatter is handled gracefully without crashing."""
        corrupted_content = """---
sop_id: SOP_BAD
title: [Malformed YAML Test
intent_keywords: :::: invalid yaml syntax
---

Corrupted file content
"""
        filepath = os.path.join(self.sops_dir, "SOP_BAD.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(corrupted_content)

        # Parser should not raise exception
        parsed = ObsidianVaultParser.parse_file(filepath)
        self.assertIsNotNone(parsed)

        # Engine should skip bad file safely
        engine = SOPRegistryEngine(vault_dir=self.test_dir)
        sops = engine.list_sops()
        bad_sop_ids = [s["sop_id"] for s in sops if s["sop_id"] == "SOP_BAD"]
        self.assertEqual(len(bad_sop_ids), 0)

    def test_unsigned_sop_rejection(self):
        """Ensures SOPs missing signature are rejected by SOPRegistryEngine for security."""
        unsigned_content = """---
sop_id: SOP_UNSIGNED_01
title: Unsigned Malicious Reboot Command
intent_keywords:
  - force_reboot
target_os: LINUX
command: reboot -f
risk_score: 0.99
---
"""
        filepath = os.path.join(self.sops_dir, "SOP_UNSIGNED_01.md")
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(unsigned_content)

        engine = SOPRegistryEngine(vault_dir=self.test_dir)
        bind_res = engine.match_and_bind_intent("force_reboot target host")
        self.assertNotEqual(bind_res["sop_id"], "SOP_UNSIGNED_01")
        self.assertEqual(bind_res["binding_status"], "REJECTED_UNAPPROVED_INTENT")

    def test_hot_reload_daemon(self):
        """Tests that ObsidianSyncDaemon detects new files and reloads catalog automatically."""
        engine = SOPRegistryEngine(vault_dir=self.test_dir)
        daemon = ObsidianSyncDaemon(vault_dir=self.test_dir, sop_engine=engine, poll_interval_sec=0.5)
        daemon.start()

        time.sleep(0.6)

        # Add new SOP file dynamically
        new_sop = """---
sop_id: SOP_DYNAMIC_99
title: Dynamic Hot Reload Test SOP
intent_keywords:
  - dynamic_test_kw
command: echo 'hot reload success'
signature: sha256_mock_sig_999999999999999999
---
"""
        with open(os.path.join(self.sops_dir, "SOP_DYNAMIC_99.md"), "w", encoding="utf-8") as f:
            f.write(new_sop)

        # Wait for daemon poll cycle
        time.sleep(1.2)
        daemon.stop()

        bind_res = engine.match_and_bind_intent("Trigger dynamic_test_kw intent")
        self.assertEqual(bind_res["binding_status"], "BOUND_TO_SIGNED_SOP")
        self.assertEqual(bind_res["sop_id"], "SOP_DYNAMIC_99")


if __name__ == "__main__":
    unittest.main()
