"""
SERVER.tests.test_tahap2_11_knowledge_governance
=================================================
Tahap 2.11 — Enterprise Knowledge Governance Platform Test Suite

Menguji 5 komponen Governance & integrasi MemoryReviewEngine & Gateway:
  1. KnowledgeVersionManager (Snapshots, Versioning, Rollback)
  2. KnowledgeQualityChecker (Metrics & Gate: overall < 80 Blocked)
  3. KnowledgeDuplicateDetector (Jaccard similarity % detection)
  4. KnowledgeLinker (Relational topic extraction)
  5. KnowledgeFreshnessManager (Annual review & stale SOP warnings)
  6. MemoryReviewEngine Governance Integration
  7. NOCIntegrationGateway Governance API
"""
import os
import shutil
import tempfile
import unittest
from SERVER.memory.staging_manager import MemoryStagingManager
from SERVER.memory.reviewer.memory_review_engine import MemoryReviewEngine
from SERVER.memory.exporter.knowledge_exporter import KnowledgeExporter
from SERVER.memory.archiver.memory_archiver import MemoryArchiver
from SERVER.memory.governance.version_manager import KnowledgeVersionManager
from SERVER.memory.governance.quality_checker import KnowledgeQualityChecker
from SERVER.memory.governance.duplicate_detector import KnowledgeDuplicateDetector
from SERVER.memory.governance.knowledge_linker import KnowledgeLinker
from SERVER.memory.governance.freshness_manager import KnowledgeFreshnessManager
from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway


class TestKnowledgeGovernanceComponents(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.versions_dir = os.path.join(self.test_dir, "versions")
        self.vm = KnowledgeVersionManager(versions_dir=self.versions_dir)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_create_version_snapshot_and_rollback(self):
        src_file = os.path.join(self.test_dir, "oracle_rac.md")
        with open(src_file, "w", encoding="utf-8") as f:
            f.write("# SOP Oracle RAC v1 Content")

        snap1 = self.vm.create_version_snapshot("oracle_rac", src_file)
        self.assertEqual(snap1["version"], "v1")
        self.assertTrue(os.path.exists(snap1["version_filepath"]))

        with open(src_file, "w", encoding="utf-8") as f:
            f.write("# SOP Oracle RAC v2 Content Updated")

        snap2 = self.vm.create_version_snapshot("oracle_rac", src_file)
        self.assertEqual(snap2["version"], "v2")

        versions = self.vm.list_versions("oracle_rac")
        self.assertEqual(len(versions), 2)
        self.assertEqual(versions[0]["version"], "v2")

        # Rollback v2 file to v1 content
        self.vm.rollback_to_version("oracle_rac", "v1", src_file)
        with open(src_file, "r", encoding="utf-8") as f:
            content = f.read()
        self.assertIn("v1 Content", content)

    def test_quality_checker_gate(self):
        qc = KnowledgeQualityChecker()

        # High quality content
        good_text = (
            "# SOP Procedure\n\n"
            "## Percakapan\n"
            "Operator: Diagnosa Oracle RAC\n"
            "Jarvis: Analysis completed.\n\n"
            "## Context\n"
            "- Intent: diagnose_incident\n"
            "- Goal: Find RCA\n"
            "- Step 1: Check node status\n"
            "- Step 2: Check database listener\n"
        )
        card1 = qc.evaluate(good_text, {"confidence": 0.95})
        self.assertGreaterEqual(card1.overall_score, 80)
        self.assertTrue(card1.is_approvable)

        # Low quality content
        poor_text = "Short text"
        card2 = qc.evaluate(poor_text, {"confidence": 0.40, "conflict_resolution": {"has_conflict": True}})
        self.assertLess(card2.overall_score, 80)
        self.assertFalse(card2.is_approvable)
        self.assertIn("below minimum threshold", card2.rejection_reason)

    def test_duplicate_detector(self):
        dd = KnowledgeDuplicateDetector()
        cand = "Prosedur recovery database oracle rac dan listener check port 1521"
        existing = [
            {"filename": "oracle_sop.md", "content": "Prosedur recovery database oracle rac dan listener check port 1521"},
            {"filename": "nginx_sop.md", "content": "Nginx web server reload configuration"},
        ]
        res = dd.check_duplicate(cand, existing)
        self.assertTrue(res.is_duplicate)
        self.assertGreaterEqual(res.similarity_pct, 85)

    def test_knowledge_linker(self):
        linker = KnowledgeLinker()
        text = "Prosedur backup database postgresql dan oracle rac"
        topics = linker.extract_related_topics(text, {"entities": ["srv-db-01"]})
        self.assertIn("Oracle RAC", topics)
        self.assertIn("PostgreSQL", topics)
        self.assertIn("Backup & Recovery", topics)

    def test_freshness_manager(self):
        fm = KnowledgeFreshnessManager()

        # Fresh SOP
        f1 = fm.evaluate_freshness(created_date="2026-01-01", last_review_date="2026-01-01")
        self.assertFalse(f1.is_stale)

        # Stale SOP (> 12 months)
        f2 = fm.evaluate_freshness(created_date="2024-01-01", last_review_date="2024-01-01")
        self.assertTrue(f2.is_stale)
        self.assertIn("belum direview", f2.stale_warning)


class TestReviewEngineGovernance(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.staging_dir = os.path.join(self.test_dir, "staging")
        self.archive_dir = os.path.join(self.test_dir, "archive")
        self.versions_dir = os.path.join(self.test_dir, "versions")

        self.staging_mgr = MemoryStagingManager(staging_dir=self.staging_dir)
        self.archiver = MemoryArchiver(archive_dir=self.archive_dir)
        self.version_mgr = KnowledgeVersionManager(versions_dir=self.versions_dir)
        self.exporter = KnowledgeExporter(staging_manager=self.staging_mgr, archiver=self.archiver)
        self.review_engine = MemoryReviewEngine(
            staging_manager=self.staging_mgr,
            exporter=self.exporter,
            version_manager=self.version_mgr,
        )

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_quality_gate_blocks_low_quality_approval(self):
        fn = self.staging_mgr.create_staging_file("sess_low", "Low Q", "Low A")
        # Overwrite file with low quality content
        self.staging_mgr.write_file_content(fn, "Tiny")

        with self.assertRaises(ValueError) as ctx:
            self.review_engine.approve_item(fn)
        self.assertIn("Approval BLOCKED", str(ctx.exception))

    def test_approval_creates_version_snapshot_and_audit(self):
        fn = self.staging_mgr.create_staging_file("sess_gov", "Diagnosa Oracle RAC", "Langkah 1: Cek node listener.\nLangkah 2: Restart service.\n" * 5)
        res = self.review_engine.approve_item(fn, reviewer="Rama", approval_reason="SOP Validated")

        self.assertEqual(res["status"], "SUCCESS")
        self.assertEqual(res["version"], "v1")

        # Verified version snapshot created
        versions = self.version_mgr.list_versions("sess_gov")
        self.assertEqual(len(versions), 1)

    def test_list_items_dashboard_table_attributes(self):
        self.staging_mgr.create_staging_file("sess_table", "Diagnosa PostgreSQL", "Content PostgreSQL SOP detail.\n" * 5)
        items = self.review_engine.list_items()
        self.assertEqual(len(items), 1)
        item = items[0]

        self.assertIn("quality_score", item)
        self.assertIn("similarity_pct", item)
        self.assertIn("version", item)
        self.assertIn("freshness_status", item)
        self.assertGreaterEqual(item["quality_score"], 80)


class TestGatewayGovernanceIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.staging_mgr = MemoryStagingManager(staging_dir=os.path.join(self.test_dir, "staging"))
        self.version_mgr = KnowledgeVersionManager(versions_dir=os.path.join(self.test_dir, "versions"))
        self.review_engine = MemoryReviewEngine(staging_manager=self.staging_mgr, version_manager=self.version_mgr)
        self.gateway = NOCIntegrationGateway(staging_manager=self.staging_mgr, review_engine=self.review_engine)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_gateway_governance_api(self):
        req = {
            "query_id": "Q-GOV-1",
            "user_id": "Rama",
            "user_role": "Senior System Engineer",
            "query_text": "Investigasi Oracle RAC RAC-01 node failure",
            "telemetry_context": {"severity": "high"},
        }
        res = self.gateway.handle_request(req)
        self.assertEqual(res["query_id"], "Q-GOV-1")

        items = self.gateway.get_knowledge_review_list()
        self.assertGreater(len(items), 0)
        filename = items[0]["filename"]

        # Approve via Gateway API
        app_res = self.gateway.approve_knowledge_review(filename, reviewer="Rama", approval_reason="Validated")
        self.assertEqual(app_res["status"], "SUCCESS")
        self.assertEqual(app_res["version"], "v1")


if __name__ == "__main__":
    unittest.main()
