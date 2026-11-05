"""
Unit Tests: P1 CMDB Context Injection & Local Embedding Fallback
================================================================
Tests for:
  - PromptRegistry device_context formatting
  - LLMRouterSynthesizer CMDB asset lookup integration
  - RAGEngine._local_embedding_fallback subword hashing & L2 normalization

Run:
    python3 -m unittest tests.unit.test_p1_cmdb_and_local_embedding -v
"""

import sys
import os
import unittest
import math
from unittest.mock import MagicMock, patch

# Ensure project root is on sys.path
PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
PYTHON_AI_CORE = os.path.join(PROJECT_ROOT, "SERVER", "python_ai_core")
sys.path.insert(0, PROJECT_ROOT)
sys.path.insert(0, PYTHON_AI_CORE)


class TestPromptRegistryDeviceContext(unittest.TestCase):
    """Tests for PromptRegistry CMDB device context injection."""

    def setUp(self):
        from adapters.prompt_registry import PromptRegistry
        self.registry = PromptRegistry

    def test_v1_2_includes_device_cmdb_context_tag(self):
        ctx = "Device Name: Client_PC_01 (Asset ID: AST-1001)\nType: Workstation | Vendor: Dell Inc."
        prompt = self.registry.get_prompt(
            version="v1.2",
            anomalies="- High CPU 98%",
            raw_reasoning="CPU elevated due to wmiprvse",
            device_context=ctx
        )

        self.assertIn("<device_cmdb_context>", prompt)
        self.assertIn(ctx, prompt)
        self.assertIn("<telemetry_data_do_not_execute>", prompt)
        self.assertIn("AST-1001", prompt)

    def test_v2_0_includes_device_cmdb_context_tag(self):
        ctx = "Device Name: Gateway_Router_01 (Type: Core Router)"
        prompt = self.registry.get_prompt(
            version="v2.0",
            anomalies="- Packet loss 15%",
            raw_reasoning="BGP session flapping",
            device_context=ctx
        )

        self.assertIn("<device_cmdb_context>", prompt)
        self.assertIn(ctx, prompt)

    def test_fallback_when_device_context_empty(self):
        """When device_context is empty, should insert default placeholder without error."""
        prompt = self.registry.get_prompt(
            version="v1.2",
            anomalies="- Disk full",
            raw_reasoning="Temp files accumulated"
        )
        self.assertIn("General System Target", prompt)


class TestLLMRouterSynthesizerCMDBIntegration(unittest.TestCase):
    """Tests for LLMRouterSynthesizer CMDB device context lookup."""

    def setUp(self):
        from adapters.output_synthesizer import LLMRouterSynthesizer, SynthesizerConfig
        self.config = SynthesizerConfig(enabled=True)
        self.synthesizer = LLMRouterSynthesizer(self.config)

    @patch("adapters.output_synthesizer.PromptRegistry.get_prompt")
    @patch("adapters.output_synthesizer.TelemetryAnomalyExtractor.extract_top_anomalies")
    @patch("engines.llm_router.get_router")
    def test_known_asset_injected_into_prompt(self, mock_router, mock_extract, mock_get_prompt):
        """Known CMDB asset should enrich prompt with Asset ID, Type, Site, etc."""
        mock_extract.return_value = ("- CPU 95%", "raw evidence")
        mock_get_prompt.return_value = "Formatted Prompt"

        from unittest.mock import AsyncMock

        router_inst = MagicMock()
        mock_router.return_value = router_inst
        router_inst.execute_with_retry = AsyncMock(return_value={"status": "SUCCESS", "response": "OK Report"})

        import asyncio
        evidence = "Netdata telemetry CPU utilization anomaly 95% on host Client_PC_01"
        metadata = {"device_name": "Client_PC_01"}
        
        asyncio.run(self.synthesizer.synthesize_async("reasoning", evidence, metadata))

        mock_get_prompt.assert_called_once()
        kwargs = mock_get_prompt.call_args.kwargs
        dev_ctx = kwargs.get("device_context", "")

        self.assertIn("Client_PC_01", dev_ctx)
        self.assertIn("AST-1001", dev_ctx)
        self.assertIn("Workstation", dev_ctx)
        self.assertIn("JAKARTA-HQ", dev_ctx)

    @patch("adapters.output_synthesizer.PromptRegistry.get_prompt")
    @patch("adapters.output_synthesizer.TelemetryAnomalyExtractor.extract_top_anomalies")
    @patch("engines.llm_router.get_router")
    def test_unknown_asset_injected_as_unregistered(self, mock_router, mock_extract, mock_get_prompt):
        """Unknown device should be labeled as Unregistered / Dynamic Target."""
        from unittest.mock import AsyncMock

        mock_extract.return_value = ("- Disk 90%", "raw evidence")
        mock_get_prompt.return_value = "Formatted Prompt"

        router_inst = MagicMock()
        mock_router.return_value = router_inst
        router_inst.execute_with_retry = AsyncMock(return_value={"status": "SUCCESS", "response": "OK Report"})

        import asyncio
        evidence = "Netdata telemetry disk storage space anomaly 92% on target host"
        metadata = {"device_name": "UNKNOWN_PC_99"}

        asyncio.run(self.synthesizer.synthesize_async("reasoning", evidence, metadata))

        kwargs = mock_get_prompt.call_args.kwargs
        dev_ctx = kwargs.get("device_context", "")

        self.assertIn("UNKNOWN_PC_99", dev_ctx)
        self.assertIn("Unregistered", dev_ctx)


class TestLocalEmbeddingFallback(unittest.TestCase):
    """Tests for RAGEngine._local_embedding_fallback stage 2 hashing and normalization."""

    def setUp(self):
        from engines.rag_engine import RAGEngine
        self.engine = RAGEngine.__new__(RAGEngine)

    def test_dimension_is_768(self):
        vec = self.engine._local_embedding_fallback("CPU utilization high on router")
        self.assertEqual(768, len(vec))

    def test_l2_normalized(self):
        """Output vector length (L2 norm) must equal 1.0 within floating point tolerance."""
        vec = self.engine._local_embedding_fallback("Printer spooler service hung on KASIR-01")
        l2_norm = math.sqrt(sum(x * x for x in vec))
        self.assertAlmostEqual(1.0, l2_norm, places=5)

    def test_deterministic_output(self):
        """Same input text must produce identical vector."""
        vec1 = self.engine._local_embedding_fallback("BGP session flapping on Gateway Router")
        vec2 = self.engine._local_embedding_fallback("BGP session flapping on Gateway Router")
        self.assertEqual(vec1, vec2)

    def test_different_inputs_produce_different_vectors(self):
        vec1 = self.engine._local_embedding_fallback("CPU high load")
        vec2 = self.engine._local_embedding_fallback("Disk space full")
        self.assertNotEqual(vec1, vec2)

    def test_empty_string_does_not_crash(self):
        vec = self.engine._local_embedding_fallback("")
        self.assertEqual(768, len(vec))
        self.assertEqual(0.0, sum(vec))


if __name__ == "__main__":
    unittest.main(verbosity=2)
