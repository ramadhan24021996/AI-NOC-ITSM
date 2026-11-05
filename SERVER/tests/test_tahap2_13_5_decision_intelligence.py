"""
SERVER.tests.test_tahap2_13_5_decision_intelligence
====================================================
Tahap 2.13.5 — AI Decision Intelligence Test Suite

Menguji 9 komponen inteligensi keputusan:
  1. EvidenceWeightEngine (Pembobotan 40/30/15/10/5%)
  2. HypothesisEngine (Hipotesis probabilistik dinamis A/B/C)
  3. SolutionComparator (Generasi solusi utama + alternatif)
  4. SolutionValidator (Validasi solusi terhadap sandbox)
  5. RecommendationRanker (Pemeringkatan rekomendasi 1-4)
  6. DecisionMemoryManager (Penyimpanan & pemanggilan keputusan masa lalu)
  7. FailureKnowledgeTracker (Pencatan & peringatan kegagalan tindakan)
  8. OutcomeTracker (Pemantauan hasil eksekusi SUCCESS/FAILED)
  9. ContinuousInvestigationEngine (Investigasi latar belakang berkelanjutan)
  10. Gateway Decision Intelligence Integration
"""
import unittest
from SERVER.orchestrator.decision_intelligence.evidence_weighter import EvidenceWeightEngine
from SERVER.orchestrator.decision_intelligence.hypothesis_engine import HypothesisEngine
from SERVER.orchestrator.decision_intelligence.solution_comparator import SolutionComparator
from SERVER.orchestrator.decision_intelligence.solution_validator import SolutionValidator
from SERVER.orchestrator.decision_intelligence.recommendation_ranker import RecommendationRanker
from SERVER.orchestrator.decision_intelligence.decision_memory import DecisionMemoryManager
from SERVER.orchestrator.decision_intelligence.failure_knowledge import FailureKnowledgeTracker
from SERVER.orchestrator.decision_intelligence.outcome_tracker import OutcomeTracker
from SERVER.orchestrator.decision_intelligence.continuous_investigation import ContinuousInvestigationEngine
from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway


class TestAIDecisionIntelligenceSuite(unittest.TestCase):
    def test_evidence_weight_engine(self):
        ewe = EvidenceWeightEngine()
        payload = ewe.compute_weighted_confidence(
            sandbox_pass=True, netdata_active=True, agent_active=True, historical_match=True, llm_confidence=1.0
        )
        self.assertEqual(payload.calculated_confidence_pct, 100)
        self.assertEqual(payload.llm_weight_pct, 5)

    def test_hypothesis_engine(self):
        he = HypothesisEngine()
        payload = he.generate_hypotheses("High CPU spike because of postgres backup", {"cpu": 98})
        self.assertEqual(payload.top_hypothesis, "Backup Job Table Lock")
        self.assertGreaterEqual(len(payload.hypotheses), 3)
        self.assertEqual(payload.hypotheses[0]["probability_pct"], 85)

    def test_solution_comparator_and_validator(self):
        sc = SolutionComparator()
        sv = SolutionValidator()

        candidates = sc.generate_candidate_solutions("CPU Spike", "srv-accounting-01")
        self.assertEqual(len(candidates), 4)
        self.assertEqual(candidates[0].rank, 1)

        # Primary candidate passes validation
        self.assertTrue(sv.validate_solution(candidates[0], {}))
        # High risk candidate requires extra approval
        self.assertFalse(sv.validate_solution(candidates[3], {}))

    def test_recommendation_ranker(self):
        sc = SolutionComparator()
        rr = RecommendationRanker()
        candidates = sc.generate_candidate_solutions("CPU Spike", "srv-accounting-01")

        ranked = rr.rank_candidates(candidates)
        self.assertGreaterEqual(len(ranked.candidates), 4)
        self.assertIn("Stop Backup", ranked.primary_recommendation)

    def test_decision_memory_and_failure_knowledge(self):
        dm = DecisionMemoryManager()
        fk = FailureKnowledgeTracker()

        # Decision Memory
        dm.record_decision("INC-TEST-1", "Stop Backup Job", "Contention resolved", "PASS", 97, "SUCCESS")
        history = dm.query_similar_decisions("Stop Backup")
        self.assertGreaterEqual(len(history), 1)

        # Failure Knowledge
        fk.record_failure("Restart PostgreSQL Container", "Lock remained active")
        warns = fk.check_failure_warnings(["Restart PostgreSQL Container"])
        self.assertEqual(len(warns), 1)
        self.assertIn("tidak disarankan", warns[0]["warning_message"])

    def test_outcome_tracker(self):
        ot = OutcomeTracker()
        res_succ = ot.record_outcome("INC-OUT-1", "Stop Backup", "SUCCESS")
        self.assertEqual(res_succ.outcome, "SUCCESS")

        res_fail = ot.record_outcome("INC-OUT-2", "Restart Service", "FAILED", "Service crash")
        self.assertEqual(res_fail.outcome, "FAILED")

    def test_continuous_investigation_engine(self):
        cie = ContinuousInvestigationEngine()
        state = cie.start_investigation("sess_cont_1")
        self.assertTrue(state.is_active)
        self.assertIn("Investigasi latar belakang", state.latest_notification)


class TestGatewayDecisionIntelligenceIntegration(unittest.TestCase):
    def setUp(self):
        self.gateway = NOCIntegrationGateway()

    def test_gateway_returns_decision_intelligence_payload(self):
        req = {
            "query_id": "Q-DECISION-1",
            "user_id": "Rama",
            "user_role": "Senior System Engineer",
            "query_text": "CPU spike 98% akibat postgresql backup pada srv-accounting-01",
            "telemetry_context": {"netdata_cpu_usage": 98.0},
        }
        res = self.gateway.handle_request(req)

        self.assertEqual(res["query_id"], "Q-DECISION-1")
        self.assertIn("hypothesis_payload", res)
        self.assertEqual(res["hypothesis_payload"]["top_hypothesis"], "Backup Job Table Lock")

        self.assertIn("weighted_evidence", res)
        self.assertEqual(res["weighted_evidence"]["llm_weight_pct"], 5)

        self.assertIn("ranked_recommendations", res)
        self.assertIn("Stop Backup", res["ranked_recommendations"]["primary_recommendation"])

        self.assertIn("decision_memory", res)
        self.assertIn("failure_warnings", res)

    def test_gateway_record_action_outcome_api(self):
        res = self.gateway.record_action_outcome("INC-API-1", "Stop Backup Job", "SUCCESS")
        self.assertEqual(res["outcome"], "SUCCESS")


if __name__ == "__main__":
    unittest.main()
