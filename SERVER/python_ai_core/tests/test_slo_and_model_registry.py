"""
Verification Test Suite for AISloEngine and ModelRegistry.
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governance.ai_slo_engine import AISloEngine, SloTarget
from adapters.model_registry import ModelRegistry, ModelMetadata, ModelDeploymentStatus


class TestSloAndModelRegistry(unittest.TestCase):

    def setUp(self):
        self.slo_engine = AISloEngine()

    def test_slo_engine_healthy_evaluation(self):
        """Verify SLO evaluation when system meets all operational targets."""
        latencies = [300.0, 450.0, 500.0, 650.0, 1100.0, 1400.0]
        report = self.slo_engine.evaluate_slo(
            latencies_ms=latencies,
            total_requests=1000,
            failed_requests=0,
            fallback_count=10,        # 1.0% (target < 5.0%)
            hallucination_count=5,     # 0.5% (target < 3.0%)
            human_review_count=30      # 3.0% (target < 10.0%)
        )
        self.assertTrue(report.slo_met)
        self.assertEqual(report.availability_pct, 100.0)
        self.assertLess(report.median_latency_ms, 700.0)
        self.assertLess(report.p95_latency_ms, 1500.0)
        self.assertEqual(report.error_budget_remaining_pct, 100.0)

    def test_slo_engine_breach_detection(self):
        """Verify SLO evaluation and breach detection when latency or fallback exceeds targets."""
        latencies = [1800.0, 2200.0, 2500.0] # All > 1500ms
        report = self.slo_engine.evaluate_slo(
            latencies_ms=latencies,
            total_requests=100,
            failed_requests=2,         # 98.0% availability (target >= 99.9%)
            fallback_count=10,         # 10% (target < 5%)
            hallucination_count=5,
            human_review_count=15
        )
        self.assertFalse(report.slo_met)
        self.assertGreater(len(report.breached_slos), 0)

    def test_model_registry_lookup_and_lifecycle(self):
        """Verify ModelRegistry metadata lookup, registration, and status filtering."""
        gemini = ModelRegistry.get_model("gemini-1.5-flash")
        self.assertEqual(gemini.provider, "google")
        self.assertEqual(gemini.deployment_status, ModelDeploymentStatus.PRODUCTION)

        prod_models = ModelRegistry.get_production_models()
        self.assertGreaterEqual(len(prod_models), 2)
        model_ids = [m.model_id for m in prod_models]
        self.assertIn("gemini-1.5-flash", model_ids)
        self.assertIn("groq-llama-3", model_ids)


if __name__ == '__main__':
    unittest.main()
