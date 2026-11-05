"""
Unit Tests: P0-2 Adaptive CRAG Threshold & Query Reformulation
==============================================================
Tests for:
  - CorrectiveRAGEvaluator.get_threshold() per severity
  - CorrectiveRAGEvaluator.evaluate() with adaptive threshold
  - CorrectiveRAGEvaluator.reformulate_query() with expanded NOC domain synonyms
  - AgenticRAGEngine.run_agentic_rag() passing severity parameter

Run:
    python3 -m unittest tests.unit.test_crag_adaptive_threshold -v
"""

import sys
import os
import unittest
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYTHON_AI_CORE = os.path.join(PROJECT_ROOT, "SERVER", "python_ai_core")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, PYTHON_AI_CORE)


class TestCorrectiveRAGAdaptiveThreshold(unittest.TestCase):
    """Tests for CorrectiveRAGEvaluator adaptive severity thresholds."""

    def setUp(self):
        from engines.agentic_rag_engine import CorrectiveRAGEvaluator
        self.evaluator = CorrectiveRAGEvaluator

    def test_get_threshold_per_severity(self):
        """Should return correct threshold for each severity level."""
        self.assertEqual(0.85, self.evaluator.get_threshold("CRITICAL"))
        self.assertEqual(0.85, self.evaluator.get_threshold("critical"))
        self.assertEqual(0.75, self.evaluator.get_threshold("HIGH"))
        self.assertEqual(0.65, self.evaluator.get_threshold("MEDIUM"))
        self.assertEqual(0.55, self.evaluator.get_threshold("LOW"))
        self.assertEqual(0.50, self.evaluator.get_threshold("INFO"))

    def test_get_threshold_default_fallback(self):
        """Unknown or empty severity should fall back to DEFAULT_THRESHOLD (0.70)."""
        self.assertEqual(0.70, self.evaluator.get_threshold("UNKNOWN"))
        self.assertEqual(0.70, self.evaluator.get_threshold(""))
        self.assertEqual(0.70, self.evaluator.get_threshold(None))

    def test_evaluate_critical_severity_triggers_crag(self):
        """Score 0.80 is high, but for CRITICAL (threshold 0.85) it should trigger CRAG (is_low=True)."""
        results = [{"similarity_score": 0.80, "title": "SOP Entry"}]
        max_score, is_low = self.evaluator.evaluate(results, severity="CRITICAL")
        self.assertEqual(0.80, max_score)
        self.assertTrue(is_low, "Score 0.80 should be below CRITICAL threshold 0.85")

    def test_evaluate_info_severity_bypasses_crag(self):
        """Same score 0.80 for INFO (threshold 0.50) should NOT trigger CRAG (is_low=False)."""
        results = [{"similarity_score": 0.80, "title": "SOP Entry"}]
        max_score, is_low = self.evaluator.evaluate(results, severity="INFO")
        self.assertEqual(0.80, max_score)
        self.assertFalse(is_low, "Score 0.80 should be above INFO threshold 0.50")

    def test_evaluate_handles_various_score_keys(self):
        """Should extract score from similarity_score, score, similarity, rrf_score, or rerank_score."""
        keys = ["similarity_score", "score", "similarity", "rrf_score", "rerank_score"]
        for key in keys:
            results = [{key: 0.78}]
            max_score, is_low = self.evaluator.evaluate(results, severity="HIGH")
            self.assertEqual(0.78, max_score, f"Failed for key '{key}'")

    def test_evaluate_empty_results(self):
        """Empty results should return (0.0, True)."""
        max_score, is_low = self.evaluator.evaluate([], severity="LOW")
        self.assertEqual(0.0, max_score)
        self.assertTrue(is_low)


class TestCorrectiveRAGQueryReformulation(unittest.TestCase):
    """Tests for CorrectiveRAGEvaluator.reformulate_query() with NOC domain synonyms."""

    def setUp(self):
        from engines.agentic_rag_engine import CorrectiveRAGEvaluator
        self.evaluator = CorrectiveRAGEvaluator

    def test_noc_synonyms_cpu(self):
        sub_q = self.evaluator.reformulate_query("CPU utilization high", device="SERVER-01")
        self.assertGreater(len(sub_q), 1)
        self.assertTrue(any("processor overload" in q or "high utilization" in q for q in sub_q))

    def test_noc_synonyms_bgp(self):
        sub_q = self.evaluator.reformulate_query("BGP session status", device="ROUTER-CORE")
        self.assertTrue(any("flapping" in q or "neighbor down" in q for q in sub_q))

    def test_noc_synonyms_nats(self):
        sub_q = self.evaluator.reformulate_query("NATS connection timeout", device="AI-CORE")
        self.assertTrue(any("deserialization error" in q or "connection refused" in q for q in sub_q))

    def test_noc_synonyms_database(self):
        sub_q = self.evaluator.reformulate_query("SQL query hanging in database")
        self.assertTrue(any("query timeout" in q or "db lock" in q for q in sub_q))

    def test_appends_device_if_not_in_query(self):
        sub_q = self.evaluator.reformulate_query("Printer error", device="KASIR-STORE-01")
        self.assertTrue(any("KASIR-STORE-01" in q for q in sub_q))


class TestAgenticRAGEngineSeverityIntegration(unittest.TestCase):
    """Tests for AgenticRAGEngine passing severity to CRAG evaluation."""

    def setUp(self):
        from engines.agentic_rag_engine import AgenticRAGEngine
        self.engine = AgenticRAGEngine.__new__(AgenticRAGEngine)
        self.engine.rag_vector_engine = MagicMock()
        self.engine.kg_service = None

    @patch("engines.agentic_rag_engine.CorrectiveRAGEvaluator.evaluate")
    def test_run_agentic_rag_passes_severity(self, mock_eval):
        """run_agentic_rag should pass severity parameter to CorrectiveRAGEvaluator.evaluate()."""
        mock_eval.return_value = (0.90, False)
        self.engine.rag_vector_engine.embed_and_query.return_value = {
            "results": [{"title": "High CPU Fix", "similarity_score": 0.90, "solution": "kill"}]
        }
        self.engine._synthesize_actionable_plan = MagicMock(return_value=("RCA", [], "LOW", 0.9))
        self.engine._build_voice_narration = MagicMock(return_value="Voice text")

        plan = self.engine.run_agentic_rag(
            query="CPU high on server",
            device="SERVER-01",
            severity="CRITICAL"
        )

        mock_eval.assert_called()
        # Verify severity='CRITICAL' was passed in calls
        call_args_list = mock_eval.call_args_list
        self.assertTrue(any(call.kwargs.get("severity") == "CRITICAL" for call in call_args_list))
        self.assertEqual("CRITICAL", plan.query and "CRITICAL")


if __name__ == "__main__":
    unittest.main(verbosity=2)
