"""
Phase 3 Verification & Continuous Evaluation Test Suite.
Tests GoldenDatasetEvaluator, PromptABTester, and OperatorFeedbackTuner.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from evaluation.golden_dataset_evaluator import GoldenDatasetEvaluator, GoldenIncidentCase
from adapters.prompt_ab_tester import PromptABTester
from evaluation.operator_feedback_tuner import OperatorFeedbackTuner
from adapters.output_synthesizer import OutputAdapterFacade, SynthesizerConfig, MockOutputSynthesizer


class TestPhase3ContinuousEvaluation(unittest.TestCase):

    def setUp(self):
        self.evaluator = GoldenDatasetEvaluator()
        self.ab_tester = PromptABTester(self.evaluator)
        self.feedback_tuner = OperatorFeedbackTuner()

    def test_golden_dataset_evaluation(self):
        """Verify Golden Dataset Benchmark execution and quality metrics calculation."""
        config = SynthesizerConfig(quality_threshold=75.0)
        facade = OutputAdapterFacade(config=config, synthesizer=MockOutputSynthesizer(config))

        benchmark_res = self.evaluator.run_full_benchmark(facade)
        self.assertEqual(benchmark_res["total_golden_cases"], 3)
        self.assertGreaterEqual(benchmark_res["pass_rate_percent"], 66.0)
        self.assertGreaterEqual(benchmark_res["average_quality_score"], 70.0)

    def test_prompt_ab_testing(self):
        """Verify A/B testing comparison between prompt versions (v1.2 vs v2.0)."""
        ab_res = self.ab_tester.compare_prompts(version_a="v1.2", version_b="v2.0")
        self.assertIn(ab_res.winning_version, ["v1.2", "v2.0"])
        self.assertGreaterEqual(ab_res.score_a, 0.0)
        self.assertGreaterEqual(ab_res.score_b, 0.0)

    def test_operator_feedback_tuning(self):
        """Verify dynamic tuning of quality threshold based on operator feedback."""
        mock_fb = [
            {"flag": "HUMAN_APPROVAL"},
            {"flag": "HUMAN_APPROVAL"},
            {"flag": "HUMAN_APPROVAL"},
            {"flag": "HUMAN_REJECTION", "failed_action": "RESTART_SERVICE"}
        ]
        summary = self.feedback_tuner.fetch_and_tune(mock_feedback=mock_fb)
        self.assertEqual(summary.total_feedback_count, 4)
        self.assertEqual(summary.acceptance_rate_percent, 75.0)
        self.assertEqual(summary.recommended_quality_threshold, 75.0)
        self.assertEqual(len(summary.curriculum_updates), 1)


if __name__ == '__main__':
    unittest.main()
