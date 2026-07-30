"""
Phase 3 Governance Framework Verification Test Suite.
Tests HumanReviewQueue, CategorizedGoldenDatasetEvaluator, RegressionTestRunner, and PromptCanaryDeployer.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governance.human_review_queue import HumanReviewQueue, ReviewTriggerReason
from evaluation.categorized_golden_dataset import CategorizedGoldenDatasetEvaluator, FormalAIMetricsResult
from governance.prompt_canary_deployer import RegressionTestRunner, PromptCanaryDeployer
from adapters.output_synthesizer import OutputAdapterFacade, SynthesizerConfig, MockOutputSynthesizer


class TestGovernanceFramework(unittest.TestCase):

    def setUp(self):
        self.review_queue = HumanReviewQueue()
        self.categorized_evaluator = CategorizedGoldenDatasetEvaluator()
        self.regression_runner = RegressionTestRunner(self.categorized_evaluator)
        self.canary_deployer = PromptCanaryDeployer(prod_version="v1.2", canary_version="v2.0", canary_weight_percent=10.0)

    def test_human_review_queue_trigger_rules(self):
        """Verify incident routing to Human Review Queue on low confidence or fallback."""
        should_route, reasons = self.review_queue.should_route_to_review(
            confidence_score=0.45,
            rca_text="Unknown root cause",
            fallback_used=True,
            operator_flag="HUMAN_REJECTION"
        )
        self.assertTrue(should_route)
        self.assertIn(ReviewTriggerReason.LOW_CONFIDENCE, reasons)
        self.assertIn(ReviewTriggerReason.UNKNOWN_ROOT_CAUSE, reasons)
        self.assertIn(ReviewTriggerReason.FALLBACK_TRIGGERED, reasons)

        item = self.review_queue.enqueue(
            incident_id=888,
            device_name="PC-NOC-01",
            raw_decision="Raw text",
            clean_decision="Clean text",
            confidence_score=0.45,
            reasons=reasons
        )
        self.assertEqual(item.status, "PENDING_HUMAN_REVIEW")

        approved_item = self.review_queue.approve_for_golden_dataset(item.item_id, "Verified by NOC Lead")
        self.assertEqual(approved_item.status, "APPROVED_FOR_GOLDEN_DATASET")

    def test_categorized_golden_dataset_formal_metrics(self):
        """Verify evaluation across 360 cases (8 incident categories) and formal AI metrics calculation."""
        config = SynthesizerConfig(quality_threshold=75.0)
        facade = OutputAdapterFacade(config=config, synthesizer=MockOutputSynthesizer(config))

        res: FormalAIMetricsResult = self.categorized_evaluator.run_formal_evaluation(
            facade, prompt_version="v1.2", evaluation_run_id="eval-2026-07-21"
        )
        self.assertEqual(res.total_cases_evaluated, 360)
        self.assertGreaterEqual(res.rca_accuracy_percent, 70.0)
        self.assertGreaterEqual(res.recommendation_relevance_percent, 70.0)
        self.assertGreaterEqual(res.evidence_grounding_percent, 70.0)
        self.assertLessEqual(res.unsupported_claim_rate_percent, 30.0)
        self.assertIn("provider", res.audit_metadata)
        self.assertEqual(res.audit_metadata["golden_dataset_version"], "2026.07")

    def test_regression_test_runner(self):
        """Verify Regression Testing enforcement before prompt deployment."""
        res = self.regression_runner.run_regression_test(prod_version="v1.2", canary_version="v2.0")
        self.assertIn(res.deployment_recommendation, ["APPROVED_FOR_CANARY_DEPLOYMENT", "REJECTED_DUE_TO_REGRESSION"])
        self.assertIn("prod_eval", res.audit_metadata)

    def test_canary_prompt_deployer_traffic_split(self):
        """Verify 90% Prod / 10% Canary traffic splitting per incident_id."""
        prod_count = 0
        canary_count = 0

        for inc_id in range(100):
            version, is_canary = self.canary_deployer.select_prompt_version(incident_id=inc_id)
            if is_canary:
                canary_count += 1
                self.assertEqual(version, "v2.0")
            else:
                prod_count += 1
                self.assertEqual(version, "v1.2")

        self.assertEqual(canary_count, 10)
        self.assertEqual(prod_count, 90)


if __name__ == '__main__':
    unittest.main()
