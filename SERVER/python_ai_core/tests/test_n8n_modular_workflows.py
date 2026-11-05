"""
Automated Unit & Integration Tests for Modular n8n Workflows (v4.1 & v4.2).
Validates Obsidian Vault Sync trigger (v4.1) and Auto Post-Mortem Publisher (v4.2).
"""

import os
import sys
import unittest
import tempfile
import shutil
import time

# Add SERVER root directory to sys.path
server_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
python_ai_core_root = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if server_root not in sys.path:
    sys.path.insert(0, server_root)
if python_ai_core_root not in sys.path:
    sys.path.insert(0, python_ai_core_root)

from governance.obsidian_vault_parser import ObsidianVaultParser
from governance.post_mortem_vault_exporter import PostMortemVaultExporter
from services.n8n_webhook_listener import n8n_webhook_listener_service


class TestN8NModularWorkflows(unittest.TestCase):

    def setUp(self):
        self.test_vault_dir = tempfile.mkdtemp(prefix="test_n8n_vault_")

    def tearDown(self):
        shutil.rmtree(self.test_vault_dir, ignore_errors=True)

    def test_postmortem_export_and_vault_parsing(self):
        """Tests v4.2 Post-Mortem markdown generation and round-trip vault parsing."""
        exporter = PostMortemVaultExporter(vault_dir=self.test_vault_dir)

        res = exporter.export_postmortem_to_vault(
            incident_id="INC-2026-N8N-TEST",
            title="Postgres DB Connection Pool Exhaustion",
            root_cause="Unindexed query locked pg_stat_activity table for > 10 minutes.",
            bound_sop_id="SOP_002",
            severity="CRITICAL",
            affected_service="postgres-primary",
            tags=["db", "postgres", "lock"],
            backlinks=["Topology-Postgres-Primary", "SOP_002"]
        )

        self.assertEqual(res["status"], "SUCCESS")
        self.assertTrue(os.path.exists(res["file_path"]))

        # Round-trip Vault Parser Test
        scan_res = ObsidianVaultParser.scan_vault(self.test_vault_dir)
        self.assertEqual(len(scan_res["incidents"]), 1)

        inc_doc = scan_res["incidents"][0]
        self.assertEqual(inc_doc["frontmatter"]["incident_id"], "INC-2026-N8N-TEST")
        self.assertEqual(inc_doc["frontmatter"]["severity"], "CRITICAL")
        self.assertIn("SOP_002", inc_doc["backlinks"])
        self.assertIn("Topology-Postgres-Primary", inc_doc["backlinks"])

    def test_n8n_v4_1_and_v4_2_triggers(self):
        """Tests dispatching v4.1 and v4.2 triggers from N8NWebhookListenerService."""
        # Test v4.1 Vault Sync Trigger
        res_v41 = n8n_webhook_listener_service.trigger_vault_sync_workflow_v4_1(vault_dir=self.test_vault_dir)
        self.assertEqual(res_v41["workflow"], "v4.1")
        self.assertIn(res_v41["status"], ["SUCCESS", "FALLBACK_EXECUTED"])

        # Test v4.2 Post-Mortem Publisher Trigger
        inc_data = {
            "incident_id": "INC-2026-DISPATCH",
            "title": "NATS Broker Consumer Lag Cleanup",
            "root_cause": "Buffer overflow cleared by auto-flushing JetStream.",
            "bound_sop_id": "SOP_003",
            "severity": "HIGH",
            "affected_service": "nats-broker"
        }
        res_v42 = n8n_webhook_listener_service.trigger_postmortem_publisher_v4_2(inc_data)
        self.assertEqual(res_v42["workflow"], "v4.2")
        self.assertIn(res_v42["status"], ["SUCCESS", "FALLBACK_EXECUTED"])


if __name__ == "__main__":
    unittest.main()
