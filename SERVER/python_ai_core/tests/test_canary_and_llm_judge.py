"""
Unit Test Suite for SOP Canary Deployment Engine & Continuous LLM-as-a-Judge Pipeline
Tests 10%->50%->100% Canary Rollouts, Instant Safety Rollback, and 4 Core Evaluation Metrics.
"""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governance.sop_canary_deployment import SOPCanaryDeploymentEngine
from evaluation.llm_judge_evaluator import LLMJudgeEvaluator


class TestCanaryAndLLMJudge(unittest.TestCase):

    def setUp(self):
        self.canary_db = os.path.join(os.path.dirname(__file__), "test_canary_registry.json")
        if os.path.exists(self.canary_db):
            try:
                os.remove(self.canary_db)
            except Exception:
                pass
        self.canary = SOPCanaryDeploymentEngine(storage_file=self.canary_db)
        self.evaluator = LLMJudgeEvaluator()

    def tearDown(self):
        if os.path.exists(self.canary_db):
            try:
                os.remove(self.canary_db)
            except Exception:
                pass

    def test_canary_auto_promotion_lifecycle(self):
        """Test Canary Rollout 10% -> 50% -> 100% Golden Production Auto-Promotion."""
        sop_id = "SOP-CANARY-TEST-001"
        self.canary.register_new_sop(
            sop_id=sop_id,
            sop_title="Test SOP Rollout",
            sop_content="New Canary SOP Content",
            previous_version_content="Old Baseline SOP Content"
        )

        status_init = self.canary.get_status(sop_id)
        self.assertIsNotNone(status_init)
        assert status_init is not None
        self.assertEqual(status_init["canary_stage"], "CANARY_10_PERCENT")
        self.assertEqual(status_init["canary_traffic_pct"], 10)

        # Record 5 successful evaluations -> Auto-Promote to 50%
        for i in range(5):
            self.canary.record_result(sop_id, is_success=True, side_effect_detected=False)

        status_50 = self.canary.get_status(sop_id)
        self.assertIsNotNone(status_50)
        assert status_50 is not None
        self.assertEqual(status_50["canary_stage"], "CANARY_50_PERCENT")
        self.assertEqual(status_50["canary_traffic_pct"], 50)
        print("\n  [CANARY PASS] Auto-Promoted to 50% Traffic Rollout after 5 successful evaluations.")

        # Record 5 more successful evaluations -> Auto-Promote to 100% Golden Production
        for i in range(5):
            self.canary.record_result(sop_id, is_success=True, side_effect_detected=False)

        status_100 = self.canary.get_status(sop_id)
        self.assertIsNotNone(status_100)
        assert status_100 is not None
        self.assertEqual(status_100["canary_stage"], "PRODUCTION_100_PERCENT")
        self.assertEqual(status_100["canary_traffic_pct"], 100)
        print("  [CANARY PASS] Auto-Promoted to 100% Golden Production Baseline after 10 successful evaluations.")

    def test_canary_instant_safety_rollback(self):
        """Test instant rollback to baseline SOP when side effect is detected."""
        sop_id = "SOP-CANARY-TEST-002"
        self.canary.register_new_sop(
            sop_id=sop_id,
            sop_title="Faulty SOP Test",
            sop_content="Faulty SOP Content",
            previous_version_content="Safe Baseline SOP Content"
        )

        # Trigger side effect on evaluation 2
        self.canary.record_result(sop_id, is_success=True, side_effect_detected=False)
        res = self.canary.record_result(sop_id, is_success=False, side_effect_detected=True)

        self.assertEqual(res["canary_stage"], "ROLLED_BACK_SAFETY_TRIGGERED")
        self.assertEqual(res["canary_traffic_pct"], 0)

        # Verify should_use_canary now returns baseline SOP
        use_canary, content = self.canary.should_use_canary(sop_id, "INC-999")
        self.assertFalse(use_canary, "Should not use canary after rollback")
        self.assertEqual(content, "Safe Baseline SOP Content", "Should return baseline SOP content")
        print("  [CANARY PASS] Instant Safety Rollback triggered successfully on side-effect detection!")

    def test_llm_judge_evaluation_pipeline(self):
        """Test LLM-as-a-Judge Evaluation across 4 core metrics & CI/CD Quality Gate."""
        def mock_reasoning_pipeline(symptom: str) -> dict:
            sym = symptom.lower()
            if "cpu" in sym:
                return {"response": "PostgreSQL Unindexed Query Lock detected in pg_stat_activity. Action: kill_locking_query and create index.", "root_cause": "PostgreSQL Unindexed Query Lock"}
            elif "spooler" in sym:
                return {"response": "Print Spooler Buffer Memory Lock detected. Action: restart_spooler.", "root_cause": "Print Spooler Buffer Memory Lock"}
            elif "nats" in sym:
                return {"response": "NATS Active Node Heartbeat Timeout. Executing failover_nats_cluster to node2.", "root_cause": "NATS Active Node Heartbeat Timeout"}
            elif "disk" in sym:
                return {"response": "IIS Temp Log Accumulation on C: drive. Action: clean_temp_files.", "root_cause": "IIS Temp Log Accumulation"}
            else:
                return {"response": "Go Routine Memory Leak in container. Action: soft_restart_app.", "root_cause": "Go Routine Memory Leak"}

        summary = self.evaluator.run_full_evaluation(mock_reasoning_pipeline)
        self.assertEqual(summary["verdict"], "PASSED_QUALITY_GATE")
        self.assertGreaterEqual(summary["metrics_summary"]["faithfulness_score_pct"], 90.0)
        self.assertEqual(summary["metrics_summary"]["hallucination_index_pct"], 0.0)
        self.assertGreaterEqual(summary["metrics_summary"]["rca_precision_pct"], 90.0)

        print(f"\n  [LLM JUDGE PASS] Quality Gate Verdict: {summary['verdict']}")
        print(f"  [LLM JUDGE PASS] Faithfulness: {summary['metrics_summary']['faithfulness_score_pct']}% | Hallucination: {summary['metrics_summary']['hallucination_index_pct']}% | RCA Precision: {summary['metrics_summary']['rca_precision_pct']}%")


if __name__ == "__main__":
    unittest.main()
