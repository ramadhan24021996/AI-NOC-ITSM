"""
tests/unit/test_duplex_voice_health.py
======================================
Unit tests for REC-7 (TTS Cache), REC-10 (Rate Limiter), REC-11 (Voice Health),
and REC-12 (Duplex Session state machine + barge-in).

Covers:
  - JarvisVoiceDuplexSession state transitions
  - Barge-in interrupt handling
  - TTS LRU cache hit/miss/eviction
  - VoiceRateLimiter per-session rate limiting
  - Voice health check data structure
"""
import unittest
import time
import threading
from unittest.mock import MagicMock, patch, ANY

# ── Import Targets ────────────────────────────────────────────────────────────
from SERVER.jarvis.voice.duplex_session import JarvisVoiceDuplexSession
from SERVER.jarvis.voice.voice_health import (
    VoiceRateLimiter, get_voice_rate_limiter, get_voice_health,
)
from SERVER.jarvis.voice.tts_service import TTSService, _TTSLRUCache
from SERVER.jarvis.interfaces.presentation_dtos import VoiceAudioPayloadDTO


class TestDuplexSessionStateMachine(unittest.TestCase):
    """REC-12: Test duplex session state transitions and barge-in."""

    def setUp(self):
        self.session = JarvisVoiceDuplexSession(session_id="test-duplex-001")
        self.emitted = []
        self.emit_func = lambda data: self.emitted.append(data)

    def test_initial_state_is_listening(self):
        self.assertEqual(self.session.state, "LISTENING")

    def test_barge_in_while_speaking(self):
        """Barge-in should transition SPEAKING → INTERRUPTED → LISTENING."""
        self.session.state = "SPEAKING"
        self.session.trigger_barge_in(self.emit_func)

        self.assertEqual(self.session.state, "LISTENING")
        self.assertEqual(len(self.emitted), 1)
        self.assertEqual(self.emitted[0]["avatar_state"], "INTERRUPTED")
        self.assertEqual(self.emitted[0]["event"], "barge_in_ack")
        self.assertFalse(self.session.interrupt_event.is_set())

    def test_barge_in_while_thinking(self):
        """Barge-in should also work when state is THINKING."""
        self.session.state = "THINKING"
        self.session.trigger_barge_in(self.emit_func)

        self.assertEqual(self.session.state, "LISTENING")
        self.assertEqual(len(self.emitted), 1)
        self.assertEqual(self.emitted[0]["event"], "barge_in_ack")

    def test_barge_in_while_listening_ignored(self):
        """Barge-in should be ignored if already LISTENING."""
        self.session.state = "LISTENING"
        self.session.trigger_barge_in(self.emit_func)

        self.assertEqual(self.session.state, "LISTENING")
        self.assertEqual(len(self.emitted), 0)

    def test_barge_in_while_idle_ignored(self):
        """Barge-in should be ignored if state is IDLE."""
        self.session.state = "IDLE"
        self.session.trigger_barge_in(self.emit_func)
        self.assertEqual(len(self.emitted), 0)

    def test_interrupt_event_cleared_after_barge_in(self):
        """interrupt_event should be cleared after barge-in completes."""
        self.session.state = "SPEAKING"
        self.session.interrupt_event.set()
        self.session.trigger_barge_in(self.emit_func)
        self.assertFalse(self.session.interrupt_event.is_set())

    def test_process_aborted_if_interrupted_after_llm(self):
        """Pipeline should skip TTS streaming if barge-in occurs after LLM call."""
        mock_runtime = MagicMock()
        # Simulate: LLM returns answer, then barge-in triggers before TTS
        def side_effect(*args, **kwargs):
            self.session.interrupt_event.set()  # barge-in during LLM
            return {"answer_text": "test answer", "intent": "QUERY", "intent_confidence": 0.9}
        mock_runtime.process_voice_query.side_effect = side_effect

        self.session.process_text_query_stream("test", mock_runtime, self.emit_func)

        # Runtime WAS called, but TTS streaming was aborted
        mock_runtime.process_voice_query.assert_called_once()
        states = [e.get("avatar_state") for e in self.emitted]
        # Should NOT contain SPEAKING (interrupted before TTS)
        self.assertNotIn("SPEAKING", [s for s in states if s not in ["THINKING", "IDLE"]])
        self.assertIn("IDLE", states)  # Always ends with IDLE

    def test_session_id_propagated(self):
        """Session ID should be present in all emitted events."""
        self.session.state = "SPEAKING"
        self.session.trigger_barge_in(self.emit_func)
        for event in self.emitted:
            self.assertEqual(event["session_id"], "test-duplex-001")

    def test_concurrent_barge_in_thread_safe(self):
        """Multiple concurrent barge-in calls should not cause race conditions."""
        self.session.state = "SPEAKING"
        results = []

        def trigger():
            self.session.trigger_barge_in(lambda d: results.append(d))

        threads = [threading.Thread(target=trigger) for _ in range(10)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        # Only first barge-in should succeed (state was SPEAKING only once)
        ack_count = sum(1 for r in results if r.get("event") == "barge_in_ack")
        self.assertEqual(ack_count, 1, f"Expected exactly 1 barge-in ACK, got {ack_count}")
        self.assertEqual(self.session.state, "LISTENING")


class TestTTSLRUCache(unittest.TestCase):
    """REC-7: Test TTS audio LRU cache."""

    def setUp(self):
        self.cache = _TTSLRUCache(maxsize=3)
        self.payload = VoiceAudioPayloadDTO(
            session_id="test", audio_format="mp3",
            sample_rate=24000, audio_bytes=b"\xff" * 100,
            text_caption="test audio"
        )

    def test_cache_miss(self):
        result = self.cache.get("hello", "noc_engineer", "INFO")
        self.assertIsNone(result)
        self.assertEqual(self.cache._misses, 1)

    def test_cache_put_and_hit(self):
        self.cache.put("hello", "noc_engineer", "INFO", self.payload)
        result = self.cache.get("hello", "noc_engineer", "INFO")
        self.assertIsNotNone(result)
        self.assertEqual(result.audio_bytes, b"\xff" * 100)
        self.assertEqual(self.cache._hits, 1)

    def test_different_persona_is_cache_miss(self):
        """Same text but different persona should be a cache miss."""
        self.cache.put("hello", "noc_engineer", "INFO", self.payload)
        result = self.cache.get("hello", "executive", "INFO")
        self.assertIsNone(result)

    def test_different_severity_is_cache_miss(self):
        """Same text+persona but different severity should be a cache miss."""
        self.cache.put("hello", "noc_engineer", "INFO", self.payload)
        result = self.cache.get("hello", "noc_engineer", "CRITICAL")
        self.assertIsNone(result)

    def test_lru_eviction(self):
        """LRU eviction: oldest entry should be evicted when cache is full."""
        self.cache.put("a", "p", "s", self.payload)
        self.cache.put("b", "p", "s", self.payload)
        self.cache.put("c", "p", "s", self.payload)
        # Cache full (3/3), add one more
        self.cache.put("d", "p", "s", self.payload)

        # "a" should be evicted (LRU)
        self.assertIsNone(self.cache.get("a", "p", "s"))
        # "d" should be present
        self.assertIsNotNone(self.cache.get("d", "p", "s"))

    def test_lru_access_refreshes(self):
        """Accessing an entry should refresh its position (not evicted next)."""
        self.cache.put("a", "p", "s", self.payload)
        self.cache.put("b", "p", "s", self.payload)
        self.cache.put("c", "p", "s", self.payload)

        # Access "a" to refresh it
        self.cache.get("a", "p", "s")

        # Add "d" — "b" should be evicted (not "a" because it was refreshed)
        self.cache.put("d", "p", "s", self.payload)
        self.assertIsNotNone(self.cache.get("a", "p", "s"))
        self.assertIsNone(self.cache.get("b", "p", "s"))

    def test_stats(self):
        self.cache.put("x", "p", "s", self.payload)
        self.cache.get("x", "p", "s")  # hit
        self.cache.get("y", "p", "s")  # miss
        stats = self.cache.stats
        self.assertEqual(stats["size"], 1)
        self.assertEqual(stats["hits"], 1)
        self.assertEqual(stats["misses"], 1)
        self.assertEqual(stats["hit_rate"], "50.0%")

    def test_duplicate_put_does_not_grow(self):
        """Putting same key twice should not grow cache size."""
        self.cache.put("x", "p", "s", self.payload)
        self.cache.put("x", "p", "s", self.payload)
        self.assertEqual(self.cache.stats["size"], 1)


class TestVoiceRateLimiter(unittest.TestCase):
    """REC-10: Test per-session rate limiting."""

    def test_allows_within_limit(self):
        limiter = VoiceRateLimiter(max_per_minute=5, window_seconds=60)
        for i in range(5):
            self.assertTrue(limiter.check("sess-1"), f"Request {i+1} should be allowed")

    def test_blocks_over_limit(self):
        limiter = VoiceRateLimiter(max_per_minute=3, window_seconds=60)
        for _ in range(3):
            limiter.check("sess-1")
        self.assertFalse(limiter.check("sess-1"), "4th request should be blocked")

    def test_different_sessions_independent(self):
        limiter = VoiceRateLimiter(max_per_minute=2, window_seconds=60)
        limiter.check("sess-A")
        limiter.check("sess-A")
        # sess-A at limit, but sess-B should be unaffected
        self.assertTrue(limiter.check("sess-B"))

    def test_get_remaining(self):
        limiter = VoiceRateLimiter(max_per_minute=5, window_seconds=60)
        self.assertEqual(limiter.get_remaining("sess-X"), 5)
        limiter.check("sess-X")
        limiter.check("sess-X")
        self.assertEqual(limiter.get_remaining("sess-X"), 3)

    def test_window_expiry(self):
        """Requests should expire after the window period."""
        limiter = VoiceRateLimiter(max_per_minute=2, window_seconds=1)
        limiter.check("sess-1")
        limiter.check("sess-1")
        self.assertFalse(limiter.check("sess-1"))  # blocked

        # Wait for window to expire
        time.sleep(1.1)
        self.assertTrue(limiter.check("sess-1"))  # should be allowed again

    def test_cleanup_removes_expired(self):
        limiter = VoiceRateLimiter(max_per_minute=5, window_seconds=1)
        limiter.check("sess-expired")
        time.sleep(1.1)
        limiter.cleanup()
        self.assertEqual(limiter.stats["active_sessions"], 0)

    def test_stats(self):
        limiter = VoiceRateLimiter(max_per_minute=10)
        limiter.check("a")
        limiter.check("b")
        stats = limiter.stats
        self.assertEqual(stats["active_sessions"], 2)
        self.assertEqual(stats["max_per_minute"], 10)

    def test_singleton_accessor(self):
        """get_voice_rate_limiter should return the same instance."""
        limiter1 = get_voice_rate_limiter()
        limiter2 = get_voice_rate_limiter()
        self.assertIs(limiter1, limiter2)


class TestVoiceHealth(unittest.TestCase):
    """REC-11: Test voice health check."""

    def test_health_returns_dict(self):
        health = get_voice_health()
        self.assertIsInstance(health, dict)
        self.assertEqual(health["status"], "ok")
        self.assertIn("timestamp", health)

    def test_health_contains_tts_section(self):
        health = get_voice_health()
        self.assertIn("tts", health)

    def test_health_contains_tts_cache_section(self):
        health = get_voice_health()
        self.assertIn("tts_cache", health)

    def test_health_contains_stt_section(self):
        health = get_voice_health()
        self.assertIn("stt", health)

    def test_health_contains_wake_word_section(self):
        health = get_voice_health()
        self.assertIn("wake_word", health)

    def test_health_contains_edge_tts_section(self):
        health = get_voice_health()
        self.assertIn("edge_tts", health)

    def test_health_contains_rate_limiter_section(self):
        health = get_voice_health()
        self.assertIn("rate_limiter", health)
        self.assertIn("max_per_minute", health["rate_limiter"])

    def test_health_edge_tts_installed(self):
        health = get_voice_health()
        # edge-tts sudah di-install di session sebelumnya
        self.assertEqual(health["edge_tts"]["status"], "installed")

    def test_health_wake_word_available(self):
        health = get_voice_health()
        self.assertTrue(health["wake_word"]["openwakeword_installed"])


class TestTTSServiceCacheIntegration(unittest.TestCase):
    """REC-7: Integration test — TTSService.synthesize() uses cache."""

    def test_cache_stats_accessible(self):
        stats = TTSService.get_cache_stats()
        self.assertIn("size", stats)
        self.assertIn("hits", stats)
        self.assertIn("misses", stats)
        self.assertIn("hit_rate", stats)


if __name__ == "__main__":
    unittest.main()
