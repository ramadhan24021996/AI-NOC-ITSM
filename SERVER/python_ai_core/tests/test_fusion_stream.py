"""
Unit Tests for Multi-Modal Temporal Cross-Correlation Engine (Fusion Stream)
"""

import unittest
import time
from datetime import datetime, timezone
from fusion_stream import (
    EventNormalizer, ModalityType, SeverityLevel,
    EventDeduplicator, TemporalWindowEngine,
    FusionOrchestrator
)


class TestFusionStream(unittest.TestCase):
    def test_event_normalizer(self):
        raw_dns = {
            "device_id": "POS-KASIR-001",
            "source": "DNS",
            "event": "DNS_TIMEOUT",
            "severity": "HIGH",
            "duration_ms": 3500,
            "timestamp": "2026-08-04T08:03:14Z"
        }
        norm = EventNormalizer.normalize(raw_dns)
        self.assertEqual(norm.device_id, "POS-KASIR-001")
        self.assertEqual(norm.modality, ModalityType.NETWORK)
        self.assertEqual(norm.severity, SeverityLevel.HIGH)
        self.assertEqual(norm.layer, "L3")

    def test_event_deduplicator(self):
        dedup = EventDeduplicator(window_seconds=1.0)
        raw = {
            "device_id": "POS-KASIR-001",
            "source": "DNS",
            "event": "DNS_TIMEOUT",
            "severity": "HIGH"
        }
        e1 = EventNormalizer.normalize(raw)
        e2 = EventNormalizer.normalize(raw)

        is_dup1, count1 = dedup.is_duplicate(e1)
        is_dup2, count2 = dedup.is_duplicate(e2)

        self.assertFalse(is_dup1)
        self.assertEqual(count1, 1)
        self.assertTrue(is_dup2)
        self.assertEqual(count2, 2)

    def test_fusion_orchestrator_scenario(self):
        orchestrator = FusionOrchestrator(window_size_seconds=10.0)

        events = [
            {"device_id": "POS-KASIR-001", "source": "WiFi", "event": "WIFI_RSSI_DROP", "severity": "WARNING", "timestamp": "2026-08-04T08:01:00Z"},
            {"device_id": "POS-KASIR-001", "source": "Ping", "event": "PACKET_LOSS", "severity": "HIGH", "timestamp": "2026-08-04T08:02:00Z"},
            {"device_id": "POS-KASIR-001", "source": "DNS", "event": "DNS_TIMEOUT", "severity": "HIGH", "timestamp": "2026-08-04T08:03:00Z"},
            {"device_id": "POS-KASIR-001", "source": "Chrome", "event": "ERR_NAME_NOT_RESOLVED", "severity": "WARNING", "timestamp": "2026-08-04T08:03:15Z"},
            {"device_id": "POS-KASIR-001", "source": "POS_App", "event": "POS_TRANSACTION_FAILED", "severity": "CRITICAL", "timestamp": "2026-08-04T08:04:00Z"}
        ]

        for ev in events:
            orchestrator.process_raw_event(ev)

        results = orchestrator.force_flush()
        self.assertGreaterEqual(len(results), 1)
        res = results[0]

        self.assertEqual(res.causal_chain.root_cause_event.modality, ModalityType.NETWORK)
        self.assertGreaterEqual(res.hypothesis_ranks[0].confidence_score, 0.85)
        self.assertIn("GraphRAG", res.graphrag_prompt_context)


if __name__ == "__main__":
    unittest.main()

