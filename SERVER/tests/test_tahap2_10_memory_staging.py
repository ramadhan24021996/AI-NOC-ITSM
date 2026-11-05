"""
SERVER.tests.test_tahap2_10_memory_staging
============================================
Tahap 2.10 — Memory Staging Area & Human-in-the-Loop Review Test Suite

Menguji alur Staging, Review Engine, Exporter, Archiver, dan API Gateway:
  1. MemoryStagingManager (Create, Read YAML Frontmatter, Update Status, List Filter)
  2. MemoryReviewEngine (List, Detail, Edit, Reject, Approve, Merge SOPs)
  3. KnowledgeExporter & MemoryArchiver (Chunking, Vector Gate, Archiving)
  4. NOCIntegrationGateway Integration (Staging Auto-Creation & Knowledge Review API)
"""
import os
import shutil
import tempfile
import unittest
from SERVER.memory.staging_manager import MemoryStagingManager
from SERVER.memory.reviewer.memory_review_engine import MemoryReviewEngine
from SERVER.memory.exporter.knowledge_exporter import KnowledgeExporter
from SERVER.memory.archiver.memory_archiver import MemoryArchiver
from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway


class TestMemoryStagingPipeline(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.staging_dir = os.path.join(self.test_dir, "staging")
        self.archive_dir = os.path.join(self.test_dir, "archive")

        self.staging_mgr = MemoryStagingManager(staging_dir=self.staging_dir)
        self.archiver = MemoryArchiver(archive_dir=self.archive_dir)
        self.exporter = KnowledgeExporter(staging_manager=self.staging_mgr, archiver=self.archiver)
        self.review_engine = MemoryReviewEngine(staging_manager=self.staging_mgr, exporter=self.exporter)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_create_and_read_staging_file(self):
        filename = self.staging_mgr.create_staging_file(
            session_id="sess_test_100",
            user_query="Diagnosa CPU spike di srv-accounting-01",
            assistant_response="[SENIOR ENGINEER ANALYSIS] CPU spike akibat backup.",
            cognitive_payload={
                "analysis_result": {"intent": "diagnose_incident", "entities": ["srv-accounting-01"]},
                "goal_payload": {"active_goal": "Find RCA"},
                "context_state": {"stage": "Diagnosis"},
                "confidence_scorecard": {"overall_confidence": 0.96},
            },
            operator="Rama",
        )

        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, filename)))
        st = self.staging_mgr.read_staging_file(filename)

        self.assertEqual(st.session_id, "sess_test_100")
        self.assertEqual(st.operator, "Rama")
        self.assertEqual(st.review_status, "DRAFT")
        self.assertEqual(st.cognitive_metadata.get("intent"), "diagnose_incident")
        self.assertIn("srv-accounting-01", st.cognitive_metadata.get("entities", []))

    def test_update_status_and_list_files(self):
        fn1 = self.staging_mgr.create_staging_file("sess_1", "Q1", "A1")
        fn2 = self.staging_mgr.create_staging_file("sess_2", "Q2", "A2")

        self.staging_mgr.update_status(fn1, "APPROVED")

        draft_files = self.staging_mgr.list_files(status_filter="DRAFT")
        approved_files = self.staging_mgr.list_files(status_filter="APPROVED")

        self.assertIn(fn2, draft_files)
        self.assertIn(fn1, approved_files)

    def test_review_engine_operations(self):
        fn = self.staging_mgr.create_staging_file("sess_review", "Check RAM", "RAM usage 45%")

        # 1. Detail
        detail = self.review_engine.get_item_detail(fn)
        self.assertEqual(detail["session_id"], "sess_review")
        self.assertEqual(detail["review_status"], "DRAFT")

        # 2. Edit
        self.review_engine.edit_item(fn, detail["transcript_md"] + "\n\nNote: Verified by engineer.")
        st_after_edit = self.staging_mgr.read_staging_file(fn)
        self.assertEqual(st_after_edit.review_status, "UNDER_REVIEW")
        self.assertIn("Verified by engineer", st_after_edit.transcript_md)

        # 3. Reject
        self.review_engine.reject_item(fn, reason="Duplicate turn")
        st_after_reject = self.staging_mgr.read_staging_file(fn)
        self.assertEqual(st_after_reject.review_status, "REJECTED")

    def test_approve_and_export_item(self):
        fn = self.staging_mgr.create_staging_file("sess_export", "Q export", "A export")
        self.staging_mgr.update_status(fn, "APPROVED")

        export_res = self.exporter.export_approved_file(fn)
        self.assertEqual(export_res["status"], "SUCCESS")
        self.assertGreater(export_res["vector_chunks_created"], 0)

        # Verified moved to archiver storage
        self.assertTrue(os.path.exists(export_res["archived_filepath"]))
        self.assertFalse(os.path.exists(os.path.join(self.staging_dir, fn)))

    def test_merge_items_into_sop(self):
        fn1 = self.staging_mgr.create_staging_file("sess_m1", "SOP step 1", "Response 1", cognitive_payload={"analysis_result": {"entities": ["srv-web-01"]}})
        fn2 = self.staging_mgr.create_staging_file("sess_m2", "SOP step 2", "Response 2", cognitive_payload={"analysis_result": {"entities": ["srv-db-01"]}})

        merged_fn = self.review_engine.merge_items([fn1, fn2], target_sop_title="Database & Web Backup Procedure")
        self.assertTrue(os.path.exists(os.path.join(self.staging_dir, merged_fn)))

        st_merged = self.staging_mgr.read_staging_file(merged_fn)
        self.assertIn("Database & Web Backup Procedure", st_merged.transcript_md)
        self.assertIn("srv-web-01", st_merged.cognitive_metadata.get("entities", []))
        self.assertIn("srv-db-01", st_merged.cognitive_metadata.get("entities", []))


class TestGatewayMemoryStagingIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.staging_dir = os.path.join(self.test_dir, "staging")
        self.staging_mgr = MemoryStagingManager(staging_dir=self.staging_dir)
        self.review_engine = MemoryReviewEngine(staging_manager=self.staging_mgr)
        self.gateway = NOCIntegrationGateway(staging_manager=self.staging_mgr, review_engine=self.review_engine)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_gateway_creates_staging_file_and_provides_review_api(self):
        req = {
            "query_id": "Q-STAGE-1",
            "user_id": "Rama",
            "user_role": "Senior System Engineer",
            "query_text": "Investigasi BGP Flap pada router-core-01",
            "telemetry_context": {"severity": "critical"},
        }
        res = self.gateway.handle_request(req)
        self.assertEqual(res["query_id"], "Q-STAGE-1")

        # Verify staging file was generated
        staging_items = self.gateway.get_knowledge_review_list(status_filter="DRAFT")
        self.assertGreater(len(staging_items), 0)

        filename = staging_items[0]["filename"]
        detail = self.gateway.get_knowledge_review_detail(filename)
        self.assertEqual(detail["operator"], "Rama")
        self.assertIn("BGP Flap", detail["transcript_md"])

        # Edit via Gateway API
        self.gateway.edit_knowledge_review(filename, detail["transcript_md"] + "\n\nEdited via Gateway")
        detail_after = self.gateway.get_knowledge_review_detail(filename)
        self.assertEqual(detail_after["review_status"], "UNDER_REVIEW")
        self.assertIn("Edited via Gateway", detail_after["transcript_md"])


if __name__ == "__main__":
    unittest.main()
