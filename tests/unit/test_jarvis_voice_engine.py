"""
Unit Tests for Jarvis Voice Engine and Conversation Opening Engine
===================================================================
Tests:
 - STTProvider & FasterWhisperSTTProvider
 - TTSProvider & KokoroTTSProvider
 - WakeWordDetector (Text, OpenWakeWord, & Porcupine Engines)
 - ConversationOpeningEngine
"""
import unittest
from SERVER.jarvis.interfaces.presentation_dtos import VoiceAudioPayloadDTO
from SERVER.jarvis.voice.stt_provider import FasterWhisperSTTProvider
from SERVER.jarvis.voice.tts_provider import KokoroTTSProvider, EdgeTTSProvider
from SERVER.jarvis.voice.stt_service import STTService
from SERVER.jarvis.voice.tts_service import TTSService
from SERVER.jarvis.voice.wake_word_detector import (
    WakeWordDetector,
    OpenWakeWordEngine,
    PorcupineWakeWordEngine,
)
from SERVER.jarvis.conversation.opening_engine import ConversationOpeningEngine


class TestJarvisVoiceEngine(unittest.TestCase):

    def test_stt_provider(self):
        provider = FasterWhisperSTTProvider(model_size="tiny")
        payload = VoiceAudioPayloadDTO(
            session_id="test-session-123",
            audio_format="wav",
            audio_bytes=b"\x00" * 100,
            text_caption="Jarvis status server accounting"
        )
        caption = provider.transcribe_audio(payload)
        self.assertEqual(caption, "Jarvis status server accounting")

        stt_service = STTService(provider)
        res = stt_service.transcribe(payload)
        self.assertEqual(res, "Jarvis status server accounting")

    def test_tts_provider(self):
        provider = KokoroTTSProvider()
        result = provider.synthesize_text("Sistem berjalan normal", persona_id="noc_engineer")
        self.assertEqual(result.audio_format, "wav")
        self.assertGreater(len(result.audio_bytes), 44)  # Contains WAV header + data
        self.assertEqual(result.text_caption, "Sistem berjalan normal")

        tts_service = TTSService(provider)
        res_payload = tts_service.synthesize("Status server OK")
        self.assertEqual(res_payload.text_caption, "Status server O-K.")

        res_payload_raw = tts_service.synthesize("Status server OK", skip_normalization=True)
        self.assertEqual(res_payload_raw.text_caption, "Status server OK")

    def test_wake_word_detector(self):
        oww_engine = OpenWakeWordEngine()
        porcupine_engine = PorcupineWakeWordEngine()
        detector = WakeWordDetector(audio_engine=oww_engine)
        
        # Test text detection
        detected, word = detector.detect_in_text("Jarvis, tolong periksa CPU server")
        self.assertTrue(detected)
        self.assertEqual(word, "jarvis")

        detected, word = detector.detect_in_text("Halo Jarvis, status database gimana?")
        self.assertTrue(detected)

        detected, word = detector.detect_in_text("Periksa memori server")
        self.assertFalse(detected)

        # Test audio frame detection (safe fallback when package uninstalled)
        mock_pcm_frame = b"\x00\x00" * 512
        audio_detected, audio_word = detector.detect_in_audio(mock_pcm_frame)
        self.assertFalse(audio_detected)  # Package not installed in unit test env

        # Test stripping wake word
        stripped = detector.strip_wake_word("Jarvis, tolong periksa CPU server")
        self.assertEqual(stripped, "tolong periksa CPU server")

    def test_conversation_opening_engine(self):
        engine = ConversationOpeningEngine()

        # Morning greeting for NOC Engineer
        opening = engine.generate_opening(
            session_id="sess-001",
            operator_name="Rama",
            persona_id="noc_engineer",
            system_status={"critical_incidents": 1, "open_alerts": 3, "primary_target": "srv-db-01"},
            hour_override=8
        )
        self.assertIn("Selamat pagi Rama", opening)
        self.assertIn("ALERT: Terdeteksi 1 insiden CRITICAL", opening)

        # Executive greeting for stable status
        opening_exec = engine.generate_opening(
            session_id="sess-002",
            operator_name="Budi",
            persona_id="executive",
            system_status={"critical_incidents": 0, "open_alerts": 0},
            hour_override=14
        )
        self.assertIn("Selamat siang Budi", opening_exec)
        self.assertIn("Seluruh layanan beroperasi secara optimal", opening_exec)

    def test_bilingual_slang_intent_routing(self):
        from SERVER.jarvis.command.intent_router import JarvisCommandIntentRouter, JarvisIntent
        router = JarvisCommandIntentRouter()

        # Mixed Indonesian-English NOC Slang Query
        res1 = router.classify("tolong cek kenapa switch cabang SBY loss packet spike abis jam makan siang")
        self.assertEqual(res1.intent, JarvisIntent.QUERY)
        self.assertEqual(res1.target_site, "Surabaya")
        self.assertEqual(res1.extracted_entities.get("time_window"), "post_lunch_13_00")

        # Remediation Slang
        res2 = router.classify("tolong benerin spooler printer kasir di JKT")
        self.assertEqual(res2.intent, JarvisIntent.REMEDIATE)
        self.assertEqual(res2.target_site, "Jakarta")

    def test_adaptive_ssml_severity_prosody(self):
        from SERVER.jarvis.voice.ssml_builder import SSMLBuilder
        builder = SSMLBuilder()

        # CRITICAL severity should apply elevated tempo & strong emphasis
        critical_ssml = builder.build_ssml("Terjadi error darurat pada server kasir", severity="CRITICAL")
        self.assertIn('rate="+10%"', critical_ssml)
        self.assertIn('volume="loud"', critical_ssml)
        self.assertIn('<emphasis level="strong">', critical_ssml)

        # INFO severity should apply calm conversational prosody
        info_ssml = builder.build_ssml("Status server normal dan optimal", severity="INFO")
        self.assertIn('rate="-8%"', info_ssml)
        self.assertIn('volume="soft"', info_ssml)


if __name__ == "__main__":
    unittest.main()

