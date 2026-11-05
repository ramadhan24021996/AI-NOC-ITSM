"""
tests.unit.test_predictive_ttf_engine
=====================================
Unit tests for Predictive Time-To-Failure (TTF) Early Warning Engine.
"""
import unittest
import time
from SERVER.python_ai_core.probabilistic.predictive_ttf_engine import PredictiveTTFEngine


class TestPredictiveTTFEngine(unittest.TestCase):

    def setUp(self):
        self.engine = PredictiveTTFEngine()

    def test_ols_regression_perfect_linear(self):
        """Test exact slope and R^2 for perfectly linear data."""
        # 10 data points: y = 2*t + 10
        base_time = 1000.0
        data = [(base_time + i * 60.0, 10.0 + i * 2.0) for i in range(10)]
        slope, intercept, r_squared = self.engine.calculate_trend_ols(data)

        # Slope per second: 2.0 units per 60 seconds = 0.03333333333333333
        self.assertAlmostEqual(slope, 2.0 / 60.0, places=5)
        self.assertAlmostEqual(r_squared, 1.0, places=4)

    def test_estimate_time_to_failure_ram_leak(self):
        """Test estimating TTF for a continuous RAM leak."""
        # RAM growing from 60% to 75% over 15 minutes (1% per minute = 60% per hour)
        base_time = time.time() - 900.0
        history = [(base_time + i * 60.0, 60.0 + i * 1.0) for i in range(16)]
        current_ram = 75.0  # Threshold is 95%
        # Remaining: 20% / (1% per minute) = 20 minutes TTF

        advisory = self.engine.estimate_time_to_failure(
            metric_name="ram_usage_pct",
            history=history,
            current_value=current_ram
        )

        self.assertIsNotNone(advisory)
        self.assertEqual(advisory["metric"], "ram_usage_pct")
        self.assertAlmostEqual(advisory["ttf_minutes"], 20.0, delta=1.0)
        self.assertEqual(advisory["urgency"], "HIGH_URGENCY")
        self.assertEqual(advisory["recommended_action"], "GRACEFUL_SERVICE_RECYCLE")

    def test_estimate_time_to_failure_negative_slope_no_alert(self):
        """Test that a declining/healthy metric generates no false alarms."""
        base_time = time.time() - 600.0
        history = [(base_time + i * 60.0, 80.0 - i * 2.0) for i in range(10)]
        current_ram = 62.0

        advisory = self.engine.estimate_time_to_failure(
            metric_name="ram_usage_pct",
            history=history,
            current_value=current_ram
        )

        self.assertIsNone(advisory)

    def test_device_telemetry_batch_analysis(self):
        """Test analyzing multiple telemetry metric streams for a device."""
        base_time = time.time() - 3600.0
        metrics_history = {
            "ram_usage_pct": [(base_time + i * 300.0, 50.0 + i * 3.0) for i in range(12)],
            "disk_usage_pct": [(base_time + i * 300.0, 70.0 + i * 0.1) for i in range(12)],
        }
        current_metrics = {
            "ram_usage_pct": 83.0,
            "disk_usage_pct": 71.1,
        }

        advisories = self.engine.analyze_device_telemetry(
            device_id="PC-KASIR-JKT-001",
            metrics_history=metrics_history,
            current_metrics=current_metrics
        )

        self.assertTrue(len(advisories) >= 1)
        ram_adv = next(a for a in advisories if a["metric"] == "ram_usage_pct")
        self.assertEqual(ram_adv["device_id"], "PC-KASIR-JKT-001")
        self.assertIn("ttf_human", ram_adv)


if __name__ == "__main__":
    unittest.main()
