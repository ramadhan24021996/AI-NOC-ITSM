"""
Phase 2B Expanded Test Suite with Latency Breakdown, Prompt Registry, Composite Confidence, and Dual Evidence.
"""

import sys
import os
import time
import tracemalloc
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from adapters.prompt_registry import PromptRegistry
from adapters.output_synthesizer import (
    SynthesizerConfig,
    IdempotencyDetector,
    QualityScoreEngine,
    OutputValidator,
    MockOutputSynthesizer,
    OutputAdapterFacade,
    CompositeConfidenceEngine,
    TelemetryAnomalyExtractor,
    PROMPT_VERSION,
    ADAPTER_VERSION
)


class TestEnhancedOutputSynthesizerAdapter(unittest.TestCase):

    def setUp(self):
        self.config = SynthesizerConfig(quality_threshold=75.0, min_length_chars=100)
        self.facade = OutputAdapterFacade(config=self.config, synthesizer=MockOutputSynthesizer(self.config))

    def test_prompt_registry_lookup(self):
        """Test retrieval of versioned prompts from PromptRegistry."""
        p_v12 = PromptRegistry.get_prompt("v1.2", "CPU 99%", "Raw text")
        self.assertIn("Prompt Version: v1.2", p_v12)
        self.assertIn("ANOMALY SUMMARY:\nCPU 99%", p_v12)

        p_v20 = PromptRegistry.get_prompt("v2.0", "RAM 98%", "Raw text")
        self.assertIn("Prompt Version: v2.0", p_v20)

    def test_composite_confidence_formula(self):
        """Test explainable composite confidence score formula."""
        # 0.4 * 80 + 0.3 * 90 + 0.3 * 85 = 32 + 27 + 25.5 = 84.5
        score = CompositeConfidenceEngine.calculate_confidence(
            evidence_score=80.0,
            consensus_confidence=90.0,
            validation_quality_score=85.0
        )
        self.assertEqual(score, 84.5)

    def test_dual_evidence_extraction(self):
        """Test extraction of concise summary evidence alongside original evidence."""
        raw_netdata = '{"chart": "system.cpu", "value": 99.5, "host": "PC-01"}'
        summary_ev, original_ev = TelemetryAnomalyExtractor.extract_top_anomalies(raw_netdata)
        self.assertIn("CPU Utilization Anomaly", summary_ev)
        self.assertEqual(original_ev, raw_netdata)

    def test_explicit_latency_breakdown(self):
        """Test separate reporting of validator latency, adapter overhead, and LLM network latency."""
        resp = self.facade.process(
            raw_final_decision='{"error": "Stack overflow"}',
            evidence="CPU 99%",
            incident_id=999
        )
        meta = resp.telemetry_metadata
        self.assertIn("validator_latency_ms", meta)
        self.assertIn("adapter_overhead_ms", meta)
        self.assertIn("llm_network_ms", meta)
        self.assertIn("temperature", meta)
        self.assertEqual(meta["temperature"], 0.3)


if __name__ == '__main__':
    unittest.main()
