"""
Unit Tests: P2 RAG Observability Metrics, Parallel Async Pipeline, & Task-Aware Temperature Routing
====================================================================================================
Tests for:
  - AgenticRAGEngine observability metrics calculation (Precision@K, top1_score, etc.)
  - AgenticRAGEngine.run_agentic_rag_async() non-blocking execution
  - OutputAdapterFacade & LLMRouterSynthesizer task-aware temperature routing (TASK_TEMPERATURE_MAP)

Run:
    python3 -m unittest tests.unit.test_p2_observability_async_and_temperature -v
"""

import sys
import os
import unittest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYTHON_AI_CORE = os.path.join(PROJECT_ROOT, "SERVER", "python_ai_core")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, PYTHON_AI_CORE)


class TestRAGObservabilityMetrics(unittest.TestCase):
    """Tests for RAG Observability metrics attached to AgenticRAGPlanDTO."""

    def setUp(self):
        from engines.agentic_rag_engine import AgenticRAGEngine
        self.engine = AgenticRAGEngine.__new__(AgenticRAGEngine)
        self.engine.rag_vector_engine = MagicMock()
        self.engine.kg_service = None
        self.engine._synthesize_actionable_plan = MagicMock(return_value=("RCA Hypothesis", [], "LOW", 0.9))
        self.engine._build_voice_narration = MagicMock(return_value="Voice text")

    def test_sync_observability_metrics_structure(self):
        """run_agentic_rag() must return filled observability_metrics dict."""
        self.engine._search_vector_kedb = MagicMock(return_value=[
            {"title": "KB 1", "similarity_score": 0.88},
            {"title": "KB 2", "similarity_score": 0.72},
            {"title": "KB 3", "similarity_score": 0.40},
        ])

        plan = self.engine.run_agentic_rag(
            query="CPU bottleneck high load",
            device="SERVER-HQ-01",
            severity="HIGH"  # Threshold 0.75
        )

        obs = plan.observability_metrics
        self.assertIsNotNone(obs)
        self.assertEqual("SYNC", obs.get("execution_mode"))
        self.assertEqual("HIGH", obs.get("severity"))
        self.assertEqual(0.75, obs.get("severity_threshold_applied"))
        self.assertEqual(0.88, obs.get("top1_score"))
        self.assertEqual(3, obs.get("total_candidates_retrieved"))
        self.assertEqual(1, obs.get("relevant_candidates_count"))  # 0.88 >= 0.75, 0.72 < 0.75
        self.assertAlmostEqual(0.333, obs.get("precision_at_k"), places=2)

    def test_async_observability_metrics_structure(self):
        """run_agentic_rag_async() must return filled observability_metrics with execution_mode=ASYNC_PARALLEL."""
        self.engine._search_vector_kedb = MagicMock(return_value=[
            {"title": "KB 1", "similarity_score": 0.92},
            {"title": "KB 2", "similarity_score": 0.86},
        ])

        plan = asyncio.run(self.engine.run_agentic_rag_async(
            query="BGP session flapping",
            device="ROUTER-CORE-01",
            severity="CRITICAL"  # Threshold 0.85
        ))

        obs = plan.observability_metrics
        self.assertEqual("ASYNC_PARALLEL", obs.get("execution_mode"))
        self.assertEqual("CRITICAL", obs.get("severity"))
        self.assertEqual(0.85, obs.get("severity_threshold_applied"))
        self.assertEqual(0.92, obs.get("top1_score"))
        self.assertEqual(2, obs.get("relevant_candidates_count"))
        self.assertEqual(1.0, obs.get("precision_at_k"))


class TestAsyncAgenticRAGEngine(unittest.TestCase):
    """Tests for non-blocking parallel execution in run_agentic_rag_async()."""

    def setUp(self):
        from engines.agentic_rag_engine import AgenticRAGEngine
        self.engine = AgenticRAGEngine.__new__(AgenticRAGEngine)
        self.engine.rag_vector_engine = MagicMock()
        self.engine.kg_service = MagicMock()
        self.engine._synthesize_actionable_plan = MagicMock(return_value=("RCA Hypothesis", [], "LOW", 0.9))
        self.engine._build_voice_narration = MagicMock(return_value="Voice text")

    def test_async_parallel_retrieval(self):
        """Vector search and KnowledgeGraph traversal must execute concurrently."""
        self.engine._search_vector_kedb = MagicMock(return_value=[
            {"title": "Disk Cleanup SOP", "similarity_score": 0.95}
        ])
        self.engine.kg_service.traverse.return_value = [
            {"node_id": "NODE-STORAGE-01", "relationship": "DEPENDS_ON", "impact_score": 0.9}
        ]

        plan = asyncio.run(self.engine.run_agentic_rag_async(
            query="Disk space running out on drive C:",
            device="Client_PC_01",
            severity="MEDIUM"
        ))

        self.assertIsNotNone(plan)
        self.assertEqual("Client_PC_01", plan.target_device)
        self.assertFalse(plan.is_crag_triggered)
        self.engine.kg_service.traverse.assert_called_once_with("Client_PC_01", 5)


class TestTaskAwareTemperatureRouting(unittest.TestCase):
    """Tests for TASK_TEMPERATURE_MAP and task-aware temperature routing."""

    def setUp(self):
        from adapters.output_synthesizer import OutputAdapterFacade, TASK_TEMPERATURE_MAP
        self.facade = OutputAdapterFacade()
        self.temp_map = TASK_TEMPERATURE_MAP

    def test_task_temperature_mapping(self):
        """Task types must map to expected operational temperatures."""
        self.assertEqual(0.10, self.temp_map["rca_analysis"])
        self.assertEqual(0.15, self.temp_map["sop_recommendation"])
        self.assertEqual(0.20, self.temp_map["incident_summary"])
        self.assertEqual(0.30, self.temp_map["anomaly_explain"])
        self.assertEqual(0.50, self.temp_map["voice_narrative"])

    @patch("adapters.output_synthesizer.LLMRouterSynthesizer.synthesize")
    def test_facade_passes_task_type_and_records_temperature(self, mock_synth):
        """OutputAdapterFacade.process() should pass task_type and record computed temperature."""
        mock_synth.return_value = ("Synthesized Report", 15.0)

        evidence = "Netdata CPU utilization anomaly 95% on host Client_PC_01"
        response = self.facade.process(
            raw_final_decision="Raw decision",
            evidence=evidence,
            confidence=0.85,
            device_name="Client_PC_01",
            task_type="rca_analysis"
        )

        mock_synth.assert_called_once()
        kwargs = mock_synth.call_args[0][2]
        self.assertEqual("rca_analysis", kwargs.get("task_type"))
        self.assertEqual("rca_analysis", response.telemetry_metadata.get("task_type"))


if __name__ == "__main__":
    unittest.main(verbosity=2)
