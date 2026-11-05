"""
Unit Tests: P3 Auto Feedback Loop Ingestion & Self-Consistency Voting
======================================================================
Tests for:
  - incident_learning.learning_handler local embedding fallback & RAG cache invalidation
  - LLMRouterSynthesizer._pick_consensus_candidate() Jaccard similarity selection
  - LLMRouterSynthesizer.synthesize_async() self-consistency voting for CRITICAL severity

Run:
    python3 -m unittest tests.unit.test_p3_feedback_loop_and_voting -v
"""

import sys
import os
import unittest
import asyncio
import json
from unittest.mock import MagicMock, patch, AsyncMock

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYTHON_AI_CORE = os.path.join(PROJECT_ROOT, "SERVER", "python_ai_core")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, PYTHON_AI_CORE)


class TestSelfConsistencyVoting(unittest.TestCase):
    """Tests for LLMRouterSynthesizer self-consistency voting for CRITICAL severity."""

    def setUp(self):
        from adapters.output_synthesizer import LLMRouterSynthesizer, SynthesizerConfig
        self.LLMRouterSynthesizer = LLMRouterSynthesizer
        self.config = SynthesizerConfig(enabled=True)
        self.synthesizer = LLMRouterSynthesizer(self.config)

    def test_pick_consensus_candidate(self):
        """Should select the candidate with highest average similarity to others."""
        cand_a = "Sistem mengalami CPU high utilization 98% pada server gateway. Tindakan: restart service wmiprvse."
        cand_b = "Sistem mengalami CPU high utilization 95% pada server gateway. Tindakan: kill process wmiprvse."
        cand_c = "Disk space full pada drive C. Hapus file temp."  # Outlier

        candidates = [cand_a, cand_b, cand_c]
        selected = self.LLMRouterSynthesizer._pick_consensus_candidate(candidates)

        # cand_a or cand_b should win, not the outlier cand_c
        self.assertIn("CPU high utilization", selected)
        self.assertNotIn("Disk space full", selected)

    def test_pick_consensus_single_candidate(self):
        self.assertEqual("Single response", self.LLMRouterSynthesizer._pick_consensus_candidate(["Single response"]))

    def test_pick_consensus_empty(self):
        self.assertEqual("", self.LLMRouterSynthesizer._pick_consensus_candidate([]))

    @patch("adapters.output_synthesizer.PromptRegistry.get_prompt")
    @patch("adapters.output_synthesizer.TelemetryAnomalyExtractor.extract_top_anomalies")
    @patch("engines.llm_router.get_router")
    def test_critical_severity_triggers_3_candidate_voting(self, mock_router, mock_extract, mock_get_prompt):
        """CRITICAL severity should trigger 3 parallel LLM executions."""
        mock_extract.return_value = ("- High CPU 98%", "raw evidence")
        mock_get_prompt.return_value = "Formatted Prompt"

        router_inst = MagicMock()
        mock_router.return_value = router_inst

        resp_a = {"status": "SUCCESS", "response": "RCA: High CPU due to process. Action: Restart service."}
        resp_b = {"status": "SUCCESS", "response": "RCA: High CPU process load. Action: Restart service spooler."}
        resp_c = {"status": "SUCCESS", "response": "RCA: High CPU usage. Action: Restart service."}

        router_inst.execute_with_retry = AsyncMock(side_effect=[resp_a, resp_b, resp_c])

        evidence = "Netdata telemetry CPU utilization anomaly 98% on host Gateway_Router_01"
        metadata = {"device_name": "Gateway_Router_01", "severity": "CRITICAL"}

        result_text, latency = asyncio.run(self.synthesizer.synthesize_async("reasoning", evidence, metadata))

        self.assertIsNotNone(result_text)
        self.assertIn("RCA:", result_text)
        self.assertEqual(3, router_inst.execute_with_retry.call_count)


class TestFeedbackLoopIngestion(unittest.TestCase):
    """Tests for incident_learning.learning_handler non-zero embedding & RAG cache invalidation."""

    @patch("engines.rag_engine.get_rag_engine")
    @patch("engines.llm_router.get_router")
    @patch("core.cache_manager.get_cache_manager")
    def test_learning_handler_ingests_and_clears_cache(self, mock_get_cache_mgr, mock_get_router, mock_get_rag):
        from supervisor.handlers.incident_learning import learning_handler

        rag_inst = MagicMock()
        mock_get_rag.return_value = rag_inst
        rag_inst.conn = MagicMock()
        
        cursor_mock = MagicMock()
        rag_inst.conn.cursor.return_value.__enter__.return_value = cursor_mock
        cursor_mock.fetchone.return_value = (0.75, False, False)  # Policy

        # Local fallback mock vector generator
        rag_inst._local_embedding_fallback.return_value = [0.1] * 768

        router_inst = MagicMock()
        mock_get_router.return_value = router_inst
        router_inst.availability = {"gemini": False}

        cache_mgr_inst = MagicMock()
        mock_get_cache_mgr.return_value = cache_mgr_inst
        cache_mgr_inst.clear_rag_cache.return_value = 5

        # Create mock NATS message
        msg_payload = {
            "incident_id": "9901",
            "verification_status": "SUCCESS",
            "human_confirmed": True,
            "rollback_needed": False,
            "confidence": 0.95,
            "title": "Kasir POS DB Lock",
            "symptoms": "POS terminal cannot checkout",
            "human_root_cause": "Deadlock on sqlite database",
            "resolution": "Kill POS background task and clear lock",
        }
        
        msg = MagicMock()
        msg.data = json.dumps(msg_payload).encode("utf-8")
        msg.ack = AsyncMock()

        asyncio.run(learning_handler(msg))

        # Verify DB execute was called for knowledge_vectors
        self.assertTrue(cursor_mock.execute.called)
        # Verify local fallback embedding was called
        rag_inst._local_embedding_fallback.assert_called_once()
        # Verify clear_rag_cache was called
        cache_mgr_inst.clear_rag_cache.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
