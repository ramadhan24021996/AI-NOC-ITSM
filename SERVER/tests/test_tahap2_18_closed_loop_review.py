"""
SERVER.tests.test_tahap2_18_closed_loop_review
===============================================
Tahap 2.18 — Closed-Loop AI Review & Operational Quality Gate Test Suite

Menguji 6 modul Review Tertutup (Closed-Loop Review):
  1. ClosedLoopReviewEngine (Alur Review Iteratif Multi-Putaran hingga LULUS)
  2. ReviewAuditTrailTracker (Catatan Audit Kronologis per Putaran Review)
  3. JarvisTechnicalQuestionGenerator (Generasi Pertanyaan Teknis Audit saat Menolak Kontrak)
  4. AINOCScorecardEngine (Scorecard Kualitas Eksekusi AI NOC)
  5. RecommendationDiffEngine (Tabel Komparasi Berdampingan Proposal AI NOC vs Jarvis)
  6. HumanLearningFeedbackEngine (Pembelajaran dari Pilihan Operator ke Staging Candidate)
  7. Gateway Closed-Loop Integration & API Methods
"""
import os
import shutil
import tempfile
import unittest
from SERVER.orchestrator.closed_loop.closed_loop_review import ClosedLoopReviewEngine
from SERVER.orchestrator.closed_loop.review_audit_trail import ReviewAuditTrailTracker
from SERVER.orchestrator.closed_loop.jarvis_technical_questions import JarvisTechnicalQuestionGenerator
from SERVER.orchestrator.closed_loop.ai_noc_scorecard import AINOCScorecardEngine
from SERVER.orchestrator.closed_loop.recommendation_diff_engine import RecommendationDiffEngine
from SERVER.orchestrator.closed_loop.human_learning_feedback import HumanLearningFeedbackEngine
from SERVER.memory.staging_manager import MemoryStagingManager
from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway


class TestClosedLoopReviewSuite(unittest.TestCase):
    def test_closed_loop_review_engine(self):
        engine = ClosedLoopReviewEngine()
        initial_contract = {
            "hypothesis": ["Backup Lock"],
            "evidence": ["[Netdata] CPU 98%"],
            "recommended_actions": ["Throttle Backup"],
            "confidence": 0.96,
        }
        trail = engine.execute_closed_loop_review("INC-CLOSED-18", initial_contract, max_rounds=3)
        self.assertEqual(trail.session_id, "INC-CLOSED-18")
        self.assertEqual(trail.final_verdict, "APPROVED")
        self.assertGreater(len(trail.iterations), 0)

    def test_jarvis_technical_questions(self):
        generator = JarvisTechnicalQuestionGenerator()
        payload = generator.generate_questions("Restart PostgreSQL Container")
        self.assertEqual(len(payload.technical_questions), 6)
        self.assertIn("lock table", payload.technical_questions[1])

    def test_ai_noc_scorecard(self):
        scorecard_engine = AINOCScorecardEngine()
        sc = scorecard_engine.compute_scorecard()
        self.assertEqual(sc.final_overall_score, 92)
        self.assertEqual(sc.evidence_score, 98)

    def test_recommendation_diff_engine(self):
        diff_engine = RecommendationDiffEngine()
        table = diff_engine.generate_diff("Restart PostgreSQL Container", "Throttle Backup Job")
        self.assertEqual(len(table.rows), 6)
        self.assertIn("Throttle Backup Job", table.selected_winner)

    def test_human_learning_feedback_engine(self):
        temp_dir = tempfile.mkdtemp()
        try:
            sm = MemoryStagingManager(staging_dir=temp_dir)
            feedback_engine = HumanLearningFeedbackEngine(staging_manager=sm)
            candidate = feedback_engine.record_feedback_choice(
                session_id="INC-FB-18",
                chosen_option="Restart Container",
                operator_reason_category="Faster Recovery",
            )
            self.assertEqual(candidate.chosen_option, "Restart Container")
            self.assertTrue(os.path.exists(os.path.join(temp_dir, candidate.staging_file_created)))
        finally:
            shutil.rmtree(temp_dir)


class TestGatewayClosedLoopIntegration(unittest.TestCase):
    def setUp(self):
        self.gateway = NOCIntegrationGateway()

    def test_gateway_returns_closed_loop_payload(self):
        req = {
            "query_id": "Q-CLOSED-LOOP-2.18",
            "user_id": "Rama",
            "user_role": "Senior System Engineer",
            "query_text": "Audit review tertutup kontrak AI NOC insiden CPU spike",
            "telemetry_context": {"netdata_cpu_usage": 98.0},
        }
        res = self.gateway.handle_request(req)

        self.assertEqual(res["query_id"], "Q-CLOSED-LOOP-2.18")
        self.assertIn("closed_loop_audit_trail", res)
        self.assertEqual(res["closed_loop_audit_trail"]["final_verdict"], "APPROVED")

        self.assertIn("technical_questions", res)
        self.assertEqual(len(res["technical_questions"]["technical_questions"]), 6)

        self.assertIn("ai_noc_scorecard", res)
        self.assertEqual(res["ai_noc_scorecard"]["final_overall_score"], 92)

        self.assertIn("recommendation_diff", res)
        self.assertEqual(len(res["recommendation_diff"]["rows"]), 6)

    def test_gateway_closed_loop_api_methods(self):
        contract_dict = {
            "incident_id": "INC-API-CL",
            "hypothesis": ["Backup Lock"],
            "evidence": ["[Netdata] CPU 98%"],
            "recommended_actions": ["Throttle Backup"],
            "confidence": 0.96,
        }
        review_res = self.gateway.execute_closed_loop_review(contract_dict, max_rounds=3)
        self.assertEqual(review_res["final_verdict"], "APPROVED")

        diff = self.gateway.generate_recommendation_diff("Restart PG", "Throttle Backup")
        self.assertIn("Throttle Backup", diff["selected_winner"])

        fb = self.gateway.record_operator_feedback_choice("INC-API-CL", "Restart PG", "Corporate SOP")
        self.assertEqual(fb["chosen_option"], "Restart PG")


if __name__ == "__main__":
    unittest.main()
