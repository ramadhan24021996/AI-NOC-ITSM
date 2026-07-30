"""
Unit Test Suite for Canary A/B Playbook Rollout Engine (RAG 3.0)
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from governance.prompt_canary_deployer import PromptCanaryDeployer


class TestCanaryPlaybookRolloutEngine(unittest.TestCase):

    def setUp(self):
        self.deployer = PromptCanaryDeployer()
        self.candidates_close_score = [
            {
                "sop_id": "SOP-001",
                "title": "Restart Nginx Container",
                "rerank_score": 0.8500,
                "similarity": 0.82
            },
            {
                "sop_id": "SOP-002",
                "title": "Flush DNS & Rebind Port",
                "rerank_score": 0.8200,
                "similarity": 0.80
            }
        ]
        self.candidates_clear_winner = [
            {
                "sop_id": "SOP-001",
                "title": "Restart Nginx Container",
                "rerank_score": 0.9500,
                "similarity": 0.92
            },
            {
                "sop_id": "SOP-002",
                "title": "Flush DNS & Rebind Port",
                "rerank_score": 0.6000,
                "similarity": 0.55
            }
        ]

    def test_evaluate_canary_trigger_on_close_scores(self):
        eval_res = self.deployer.evaluate_playbook_canary_rollout(self.candidates_close_score, fleet_size=100)
        self.assertEqual(eval_res["rollout_mode"], "CANARY_5_PERCENT")
        self.assertEqual(eval_res["canary_hosts_count"], 5)
        self.assertEqual(eval_res["candidate_a"]["sop_id"], "SOP-001")
        self.assertEqual(eval_res["candidate_b"]["sop_id"], "SOP-002")

    def test_evaluate_full_rollout_on_clear_winner(self):
        eval_res = self.deployer.evaluate_playbook_canary_rollout(self.candidates_clear_winner, fleet_size=100)
        self.assertEqual(eval_res["rollout_mode"], "FULL_DEPLOYMENT_100")
        self.assertEqual(eval_res["selected_sop"]["sop_id"], "SOP-001")

    def test_monitor_canary_telemetry_healthy_promotion(self):
        res = self.deployer.monitor_canary_telemetry_window(
            canary_run_id="canary_1001",
            candidate_a=self.candidates_close_score[0],
            candidate_b=self.candidates_close_score[1],
            telemetry_recovered=True
        )
        self.assertEqual(res["status"], "PROMOTED_100_PERCENT")
        self.assertEqual(res["promoted_sop"]["sop_id"], "SOP-001")
        self.assertEqual(res["telemetry_status"], "HEALTHY")

    def test_monitor_canary_telemetry_degraded_fallback(self):
        res = self.deployer.monitor_canary_telemetry_window(
            canary_run_id="canary_1002",
            candidate_a=self.candidates_close_score[0],
            candidate_b=self.candidates_close_score[1],
            telemetry_recovered=False
        )
        self.assertEqual(res["status"], "FALLBACK_TO_CANDIDATE_B")
        self.assertEqual(res["promoted_sop"]["sop_id"], "SOP-002")
        self.assertEqual(res["telemetry_status"], "DEGRADED")

    def test_rag_engine_canary_integration(self):
        from rag_engine import get_rag_engine
        rag = get_rag_engine()
        res = rag.evaluate_rag3_canary_decision(self.candidates_close_score, fleet_count=50)
        self.assertEqual(res["rollout_mode"], "CANARY_5_PERCENT")
        self.assertEqual(res["canary_hosts_count"], 2)  # 50 * 0.05 = 2.5 -> rounds to 2


if __name__ == "__main__":
    unittest.main()
