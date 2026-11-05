"""
SERVER.tests.test_tahap2_13_6_decision_governance
==================================================
Tahap 2.13.6 — AI Decision Governance & Peer Review Test Suite

Menguji 9 komponen tata kelola keputusan:
  1. DecisionCriticEngine (Evaluasi kualitas bukti, reasoning & safety)
  2. CrossValidationEngine (Verifikasi 6 sinyal & persentase konsensus)
  3. SOPComplianceEngine (Audit kepatuhan SOP perusahaan & deviasi)
  4. MultiLLMConsensusEngine (Voting lintas provider Gemini, DeepSeek, Grok)
  5. RecommendationReviewer (Review pra-eksekusi minim downtime)
  6. DecisionDriftDetector (Deteksi penurunan sukses insiden dari waktu ke waktu)
  7. HumanOverrideLearningEngine (Pembelajaran dari override operator human)
  8. ConfidenceCalibrationEngine (Kalibrasi skor keyakinan empiris)
  9. Gateway Decision Governance Integration
"""
import os
import shutil
import tempfile
import unittest
from SERVER.orchestrator.governance.decision_critic import DecisionCriticEngine
from SERVER.orchestrator.governance.cross_validator import CrossValidationEngine
from SERVER.orchestrator.governance.sop_compliance import SOPComplianceEngine
from SERVER.orchestrator.governance.multi_llm_consensus import MultiLLMConsensusEngine
from SERVER.orchestrator.governance.recommendation_reviewer import RecommendationReviewer
from SERVER.orchestrator.governance.decision_drift import DecisionDriftDetector
from SERVER.orchestrator.governance.human_override_learning import HumanOverrideLearningEngine
from SERVER.orchestrator.governance.confidence_calibrator import ConfidenceCalibrationEngine
from SERVER.memory.staging_manager import MemoryStagingManager
from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway


class TestAIDecisionGovernanceSuite(unittest.TestCase):
    def test_decision_critic_engine(self):
        dce = DecisionCriticEngine()
        report = dce.evaluate_decision("Stop Backup Job", 95, has_failure_warning=False)
        self.assertEqual(report.critic_verdict, "APPROVED")
        self.assertEqual(report.safety_score_pct, 100)

        report_warn = dce.evaluate_decision("Restart Container", 50, has_failure_warning=True)
        self.assertEqual(report_warn.critic_verdict, "REVIEW_REQUIRED")
        self.assertTrue(report_warn.need_more_evidence)

    def test_cross_validation_engine(self):
        cve = CrossValidationEngine()
        matrix = cve.validate_signals(netdata_yes=True, agent_yes=True, docker_yes=True, sandbox_yes=True, knowledge_yes=True, llm_yes=True)
        self.assertEqual(matrix.consensus_pct, 100)
        self.assertEqual(matrix.validation_status, "VERIFIED")

        matrix_conflict = cve.validate_signals(netdata_yes=True, agent_yes=False, docker_yes=False, sandbox_yes=True, knowledge_yes=False, llm_yes=True)
        self.assertEqual(matrix_conflict.consensus_pct, 50)
        self.assertTrue(matrix_conflict.has_conflict)
        self.assertEqual(matrix_conflict.validation_status, "NEED_INVESTIGATION")

    def test_sop_compliance_engine(self):
        sce = SOPComplianceEngine()
        rep1 = sce.audit_compliance("Stop Backup Job")
        self.assertTrue(rep1.has_deviation)
        self.assertIn("SOP Backup", rep1.deviation_reason)

    def test_multi_llm_consensus_engine(self):
        mlc = MultiLLMConsensusEngine()
        res = mlc.evaluate_consensus(
            gemini_vote="Stop Backup Job", deepseek_vote="Stop Backup Job", grok_vote="Memory Leak Recovery"
        )
        self.assertEqual(res.winning_consensus, "Stop Backup Job")
        self.assertEqual(res.consensus_confidence_pct, 66)

    def test_decision_drift_detector(self):
        ddd = DecisionDriftDetector()
        rep = ddd.evaluate_drift("Restart PostgreSQL Container", historical_success_pct=93, current_success_pct=48)
        self.assertTrue(rep.drift_detected)
        self.assertIn("Recommendation Drift detected", rep.action_recommendation)

    def test_confidence_calibration_engine(self):
        cce = ConfidenceCalibrationEngine()
        card = cce.calibrate(netdata_score=100, sandbox_score=100, history_score=95, knowledge_score=90, llm_score=70)
        self.assertEqual(card.calibrated_final_score, 96)

    def test_human_override_learning(self):
        temp_dir = tempfile.mkdtemp()
        try:
            sm = MemoryStagingManager(staging_dir=temp_dir)
            hole = HumanOverrideLearningEngine(staging_manager=sm)
            entry = hole.record_override("INC-OVR-101", "Throttle Backup", "Stop Backup", "Less disruptive during business hours")
            self.assertEqual(entry.chosen_option, "Throttle Backup")
            self.assertTrue(os.path.exists(os.path.join(temp_dir, entry.staging_file_created)))
        finally:
            shutil.rmtree(temp_dir)


class TestGatewayDecisionGovernanceIntegration(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.mkdtemp()
        self.sm = MemoryStagingManager(staging_dir=os.path.join(self.test_dir, "staging"))
        self.gateway = NOCIntegrationGateway(staging_manager=self.sm)

    def tearDown(self):
        shutil.rmtree(self.test_dir)

    def test_gateway_returns_decision_governance_payload(self):
        req = {
            "query_id": "Q-GOV-2.13.6",
            "user_id": "Rama",
            "user_role": "Senior System Engineer",
            "query_text": "Investigasi CPU spike 98% akibat postgresql backup pada srv-accounting-01",
            "telemetry_context": {"netdata_cpu_usage": 98.0},
        }
        res = self.gateway.handle_request(req)

        self.assertEqual(res["query_id"], "Q-GOV-2.13.6")
        self.assertIn("decision_critic", res)
        self.assertIn(res["decision_critic"]["critic_verdict"], ["APPROVED", "REVIEW_REQUIRED"])

        self.assertIn("cross_validation", res)
        self.assertEqual(res["cross_validation"]["validation_status"], "VERIFIED")

        self.assertIn("sop_compliance", res)
        self.assertIn("multi_llm_consensus", res)
        self.assertEqual(res["multi_llm_consensus"]["winning_consensus"], "Stop Backup Job (cron_backup.sh)")

        self.assertIn("decision_drift", res)
        self.assertIn("calibrated_confidence", res)
        self.assertEqual(res["calibrated_confidence"]["calibrated_final_score"], 96)

    def test_gateway_record_human_override_api(self):
        res = self.gateway.record_human_override(
            incident_id="INC-GOV-99",
            chosen_option="Throttle Backup",
            default_ai_option="Stop Backup",
            reason="Less disruptive during peak hours"
        )
        self.assertEqual(res["chosen_option"], "Throttle Backup")
        self.assertTrue(res["staging_file_created"].endswith(".md"))


if __name__ == "__main__":
    unittest.main()
