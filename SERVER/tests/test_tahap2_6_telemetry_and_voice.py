"""
Tahap 2.6 — Telemetry & AI Agent Integration + Voice Services Test Suite
==========================================================================
DoD Criteria:
 1. NetdataReceiver memproses payload alarm Netdata (normalize, validate, correlate).
 2. AgentReceiver memproses payload L1-L7 probe Go Client Agent.
 3. TelemetryValidator menolak data cacat (empty device_id, NaN/Inf values).
 4. TelemetryCorrelationEngine mengkorelasikan multi-source (Netdata + Agent) & menghitung confidence score (0.95).
 5. EventBus menerima event telemetry ter-korelasi (telemetry.netdata.correlated, telemetry.agent.correlated).
 6. STTProvider (WhisperSTTProvider / MockSTTProvider) dapat mentranskripsikan audio payload.
 7. TTSProvider (EdgeTTSProvider / MockTTSProvider) dapat mensintesis text ke audio payload.
 8. JarvisPresentationRuntime menjalankan alur voice end-to-end dengan STTService & TTSService.
 9. Clean Architecture: Tidak ada import adapter legacy (Zabbix/MikroTik).
"""
import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestTahap26TelemetryAndVoice(unittest.TestCase):

    # ── Test 1: Telemetry Normalizer ──────────────────────────────────────────
    def test_netdata_normalizer(self):
        from SERVER.integration.telemetry import TelemetryNormalizer
        normalizer = TelemetryNormalizer()
        dto = normalizer.normalize_netdata({
            "hostname": "srv-db-01",
            "alarm": "system.cpu",
            "value": 96.5,
            "units": "%",
            "status": "CRITICAL",
        })
        self.assertEqual(dto.source_type, "netdata")
        self.assertEqual(dto.device_id, "srv-db-01")
        self.assertEqual(dto.severity, "critical")
        self.assertEqual(dto.value, 96.5)

    def test_agent_normalizer(self):
        from SERVER.integration.telemetry import TelemetryNormalizer
        normalizer = TelemetryNormalizer()
        dto = normalizer.normalize_agent({
            "device_id": "pc-client-101",
            "layer_3_network": {"dns_latency_ms": 120.0},
            "layer_4_transport": {"tcp_retrans_rate": 0.04},
            "layer_5_7_application": {"browser_crashes": 2},
        })
        self.assertEqual(dto.source_type, "agent")
        self.assertEqual(dto.device_id, "pc-client-101")
        self.assertEqual(dto.severity, "high")

    # ── Test 2: Telemetry Validator ───────────────────────────────────────────
    def test_telemetry_validator_rejects_nan_value(self):
        from SERVER.integration.telemetry import TelemetryValidator, NormalizedTelemetryDTO
        validator = TelemetryValidator()
        dto = NormalizedTelemetryDTO(
            telemetry_id="TEL-001",
            source_type="netdata",
            device_id="srv-01",
            host_name="srv-01",
            metric_category="cpu",
            metric_name="system.cpu",
            value=float("nan"),
            unit="%",
            severity="high",
            timestamp="2026-08-05T12:00:00Z",
        )
        is_valid, reason = validator.validate(dto)
        self.assertFalse(is_valid)
        self.assertIn("NaN", reason)

    def test_telemetry_validator_rejects_missing_device_id(self):
        from SERVER.integration.telemetry import TelemetryValidator, NormalizedTelemetryDTO
        validator = TelemetryValidator()
        dto = NormalizedTelemetryDTO(
            telemetry_id="TEL-002",
            source_type="netdata",
            device_id="",
            host_name="",
            metric_category="cpu",
            metric_name="system.cpu",
            value=80.0,
            unit="%",
            severity="high",
            timestamp="2026-08-05T12:00:00Z",
        )
        is_valid, reason = validator.validate(dto)
        self.assertFalse(is_valid)
        self.assertIn("device_id", reason)

    # ── Test 3: Telemetry Correlation Engine ──────────────────────────────────
    def test_correlation_engine_multi_source_high_confidence(self):
        from SERVER.integration.telemetry import (
            TelemetryCorrelationEngine, TelemetryNormalizer
        )
        engine = TelemetryCorrelationEngine()
        normalizer = TelemetryNormalizer()

        dto_netdata = normalizer.normalize_netdata({
            "hostname": "srv-prod-01",
            "alarm": "system.cpu",
            "value": 98.0,
            "status": "CRITICAL",
        })
        dto_agent = normalizer.normalize_agent({
            "device_id": "srv-prod-01",
            "layer_3_network": {"dns_latency_ms": 160.0},
        })

        res1 = engine.ingest_and_correlate(dto_netdata)
        res2 = engine.ingest_and_correlate(dto_agent)

        self.assertEqual(res2.host_name, "srv-prod-01")
        self.assertEqual(res2.primary_severity, "critical")
        self.assertEqual(res2.confidence_score, 0.95)  # Multi-source confirmed!
        self.assertIn("netdata", res2.correlated_sources)
        self.assertIn("agent", res2.correlated_sources)

    # ── Test 4: NetdataReceiver & AgentReceiver ───────────────────────────────
    def test_netdata_and_agent_receivers_pipeline(self):
        from SERVER.integration.telemetry import NetdataReceiver, AgentReceiver

        events_published = []

        class MockEventBus:
            def publish(self, topic, payload):
                events_published.append((topic, payload))

        event_bus = MockEventBus()
        netdata_rcvr = NetdataReceiver(event_bus=event_bus)
        agent_rcvr = AgentReceiver(event_bus=event_bus)

        c1 = netdata_rcvr.process_payload({
            "hostname": "edge-router-01",
            "alarm": "system.ram",
            "value": 95.0,
            "status": "CRITICAL",
        })
        c2 = agent_rcvr.process_payload({
            "device_id": "edge-router-01",
            "layer_3_network": {"dns_latency_ms": 80.0},
        })

        self.assertIsNotNone(c1)
        self.assertIsNotNone(c2)
        self.assertEqual(len(events_published), 2)
        self.assertEqual(events_published[0][0], "telemetry.netdata.correlated")
        self.assertEqual(events_published[1][0], "telemetry.agent.correlated")

    # ── Test 5: STT and TTS Providers ─────────────────────────────────────────
    def test_stt_and_tts_providers(self):
        from SERVER.jarvis.voice import (
            STTService, TTSService, WhisperSTTProvider, EdgeTTSProvider
        )
        from SERVER.jarvis.interfaces.presentation_dtos import VoiceAudioPayloadDTO

        stt = STTService(provider=WhisperSTTProvider(model_size="base"))
        tts = TTSService(provider=EdgeTTSProvider())

        payload = VoiceAudioPayloadDTO(
            session_id="sess-100",
            audio_format="wav",
            text_caption="Jarvis, status server accounting"
        )

        caption = stt.transcribe(payload)
        self.assertIn("Jarvis", caption)

        synth_result = tts.synthesize("Status server accounting normal", persona_id="noc_engineer")
        self.assertIsInstance(synth_result, VoiceAudioPayloadDTO)
        self.assertGreater(len(synth_result.audio_bytes), 0)

    # ── Test 5b: Wake Word Detector ──────────────────────────────────────────
    def test_wake_word_detector(self):
        from SERVER.jarvis.voice import WakeWordDetector
        detector = WakeWordDetector()

        # 1. Detection
        is_detected, word = detector.detect_in_text("Hello Jarvis, kenapa CPU server 98%?")
        self.assertTrue(is_detected)
        self.assertEqual(word, "hello jarvis")

        # 2. Stripping wake word
        clean_query = detector.strip_wake_word("Hello Jarvis, kenapa CPU server 98%?")
        self.assertEqual(clean_query, "kenapa CPU server 98%?")

        # 3. No wake word
        is_detected, _ = detector.detect_in_text("Berapa disk usage di server accounting?")
        self.assertFalse(is_detected)

    # ── Test 6: Jarvis Presentation Runtime End-to-End Voice ─────────────────
    def test_jarvis_presentation_runtime_voice_e2e(self):
        from SERVER.jarvis.runtime.jarvis_presentation_runtime import JarvisPresentationRuntime
        from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway
        from SERVER.orchestrator.coordinator.noc_execution_coordinator import NOCExecutionCoordinator
        from SERVER.jarvis.voice import STTService, TTSService
        from SERVER.jarvis.interfaces.presentation_dtos import VoiceAudioPayloadDTO

        coordinator = NOCExecutionCoordinator()
        gateway = NOCIntegrationGateway(coordinator=coordinator)
        stt = STTService()
        tts = TTSService()

        runtime = JarvisPresentationRuntime(
            gateway=gateway,
            stt_service=stt,
            tts_service=tts,
        )

        audio_in = VoiceAudioPayloadDTO(
            session_id="voice-sess-001",
            audio_format="pcm",
            text_caption="Kenapa CPU server 98%?",
        )

        res = runtime.process_voice_query("voice-sess-001", audio_in)
        self.assertEqual(res["session_id"], "voice-sess-001")
        self.assertIn("query_text", res)
        self.assertIn("answer_text", res)
        self.assertIsNotNone(res.get("audio_output"))

    # ── Test 7: Clean Architecture Rule — No Legacy Adapters ─────────────────
    def test_no_legacy_adapters_imported(self):
        """Aturan Arsitektur: Tidak ada import Zabbix atau MikroTik adapter."""
        import ast
        server_root = os.path.join(PROJECT_ROOT, "SERVER", "integration")
        forbidden = ["zabbix", "mikrotik"]
        violations = []
        for root, _, files in os.walk(server_root):
            for f in files:
                if not f.endswith(".py"):
                    continue
                fp = os.path.join(root, f)
                with open(fp, encoding="utf-8") as fh:
                    try:
                        tree = ast.parse(fh.read(), filename=fp)
                    except SyntaxError:
                        continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        module = (getattr(node, "module", "") or "").lower()
                        if any(f_name in module for f_name in forbidden):
                            violations.append(f"{fp}: imports {module}")
        self.assertEqual(violations, [], "Architecture violation:\n" + "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
