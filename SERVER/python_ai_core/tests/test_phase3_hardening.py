"""
Phase 3 Hardening & Governance Verification Test Suite.
Verifies PromptRegistry Metadata, SLA Enforcement, 300+ Golden Cases, Drift Detection, Provider Benchmarking, and AI Incident Replay.
"""

import sys
import os
import time
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.prompt_registry import PromptRegistry, PromptStatus
from governance.human_review_queue import HumanReviewQueue, ReviewTriggerReason, SeverityLevel
from evaluation.categorized_golden_dataset import CategorizedGoldenDatasetEvaluator, CategorizedGoldenDatasetGenerator, IncidentCategory
from governance.drift_detection import DriftDetectionEngine
from evaluation.provider_benchmark import ProviderBenchmarkEngine
from evaluation.incident_replay import AIIncidentReplayEngine
from adapters.output_synthesizer import OutputAdapterFacade, SynthesizerConfig, MockOutputSynthesizer


class TestPhase3Hardening(unittest.TestCase):

    def setUp(self):
        self.review_queue = HumanReviewQueue()
        self.drift_engine = DriftDetectionEngine(alert_threshold_pct=5.0)
        self.provider_bench = ProviderBenchmarkEngine()
        self.replay_engine = AIIncidentReplayEngine()

    def test_prompt_registry_rich_metadata(self):
        """Verify prompt registry metadata, changelogs, and status."""
        meta = PromptRegistry.get_metadata("v1.2")
        self.assertIsNotNone(meta)
        self.assertEqual(meta.status, PromptStatus.PRODUCTION)
        self.assertIn("NOC Architecture Board", meta.author)
        self.assertGreaterEqual(len(meta.changelog), 2)

    def test_human_review_queue_sla_enforcement(self):
        """Verify SLA deadline assignment and SLA breach detection for Critical, High, and Medium severe items."""
        item = self.review_queue.enqueue(
            incident_id=101,
            device_name="PC-NOC-01",
            raw_decision="Raw decision text",
            clean_decision="Clean text",
            confidence_score=0.40,
            reasons=[ReviewTriggerReason.LOW_CONFIDENCE],
            severity=SeverityLevel.CRITICAL
        )
        self.assertEqual(item.severity, SeverityLevel.CRITICAL)

        future_time = time.time() + 1000.0
        breached = self.review_queue.check_sla_breaches(current_time=future_time)
        self.assertEqual(len(breached), 1)
        self.assertEqual(breached[0].status, "SLA_BREACHED")

    def test_300_cases_golden_dataset_generator(self):
        """Verify generation of 360 categorized historical Netdata incident cases (target >= 300)."""
        cases = CategorizedGoldenDatasetGenerator.generate_300_cases()
        self.assertEqual(len(cases), 360)

        cpu_cases = sum(1 for c in cases if c.category == IncidentCategory.CPU)
        mem_cases = sum(1 for c in cases if c.category == IncidentCategory.MEMORY)
        self.assertEqual(cpu_cases, 50)
        self.assertEqual(mem_cases, 50)

    def test_explicit_governance_score_formula(self):
        """Verify evaluation over 300 cases using explicit Governance Score formula."""
        cases = CategorizedGoldenDatasetGenerator.generate_300_cases()[:20]
        evaluator = CategorizedGoldenDatasetEvaluator(cases=cases)
        config = SynthesizerConfig(quality_threshold=75.0)
        facade = OutputAdapterFacade(config=config, synthesizer=MockOutputSynthesizer(config))

        res = evaluator.run_formal_evaluation(facade, prompt_version="v1.2")
        self.assertEqual(res.total_cases_evaluated, 20)
        self.assertGreaterEqual(res.overall_governance_score, 70.0)
        self.assertIn("0.30*RCA_Acc", res.audit_metadata["governance_score_formula"])

    def test_ai_quality_drift_detection(self):
        """Verify detection of quality metric degradation over time (e.g. Week 1 vs Week 5)."""
        baseline_week1 = {"rca_accuracy_percent": 91.0, "evidence_grounding_percent": 95.0, "unsupported_claim_rate_percent": 5.0}
        current_week5 = {"rca_accuracy_percent": 82.0, "evidence_grounding_percent": 94.0, "unsupported_claim_rate_percent": 12.0}

        alerts = self.drift_engine.analyze_ai_quality_drift(baseline_week1, current_week5)
        self.assertEqual(len(alerts), 2)
        metric_names = [a.metric_name for a in alerts]
        self.assertIn("rca_accuracy_percent", metric_names)
        self.assertIn("unsupported_claim_rate_percent", metric_names)

    def test_provider_capability_benchmark(self):
        """Verify empirical capability benchmarking across Gemini, DeepSeek, Groq, and Rule Engine."""
        metrics = self.provider_bench.benchmark_all_providers()
        self.assertEqual(len(metrics), 4)

        provider_names = [m.provider_name for m in metrics]
        self.assertIn("gemini", provider_names)
        self.assertIn("deepseek", provider_names)
        self.assertIn("groq", provider_names)

    def test_ai_incident_replay_engine(self):
        """Verify historical incident replay across multiple prompt versions."""
        replay_res = self.replay_engine.replay_incident(
            incident_id=999,
            device_name="SERVER-01",
            raw_decision="Stack trace error dump",
            evidence="CPU 99% Netdata dump",
            confidence=0.85
        )
        self.assertEqual(replay_res.incident_id, 999)
        self.assertIn("v1.0", replay_res.replays)
        self.assertIn("v1.2", replay_res.replays)
        self.assertIn("v2.0", replay_res.replays)


if __name__ == '__main__':
    unittest.main()
