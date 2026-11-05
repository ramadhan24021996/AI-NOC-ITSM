"""
SERVER.jarvis.voice.voice_health — JARVIS Voice Subsystem Health Check & Rate Limiter
======================================================================================
REC-10: Rate limiting per session (max 15 requests/menit).
REC-11: Health check endpoint data untuk /api/jarvis/voice/health.

Production-Ready — Zero Placeholders, Zero Mock Data.
"""
import time
import logging
import importlib.util
from typing import Any, Dict, Optional

logger = logging.getLogger("jarvis.voice.health")


# ── REC-10: Voice API Rate Limiter ────────────────────────────────────────────
class VoiceRateLimiter:
    """Per-session rate limiter untuk voice API requests.

    Default: max 15 requests per 60 detik per session.
    Mencegah spam voice requests yang membebani EdgeTTS/STT.
    """

    def __init__(self, max_per_minute: int = 15, window_seconds: int = 60):
        self._max = max_per_minute
        self._window = window_seconds
        self._buckets: Dict[str, list] = {}  # session_id → [timestamps]

    def check(self, session_id: str) -> bool:
        """Return True jika request diperbolehkan, False jika rate-limited."""
        now = time.time()
        cutoff = now - self._window

        if session_id not in self._buckets:
            self._buckets[session_id] = []

        # Buang timestamps yang sudah expired
        self._buckets[session_id] = [
            t for t in self._buckets[session_id] if t > cutoff
        ]

        if len(self._buckets[session_id]) >= self._max:
            logger.warning(
                "[RateLimiter] Session '%s' rate-limited: %d/%d requests in window.",
                session_id, len(self._buckets[session_id]), self._max
            )
            return False

        self._buckets[session_id].append(now)
        return True

    def get_remaining(self, session_id: str) -> int:
        """Return jumlah request tersisa dalam window saat ini."""
        now = time.time()
        cutoff = now - self._window
        if session_id not in self._buckets:
            return self._max
        active = [t for t in self._buckets[session_id] if t > cutoff]
        return max(0, self._max - len(active))

    def cleanup(self):
        """Bersihkan bucket yang sudah expired (panggil periodik)."""
        now = time.time()
        cutoff = now - self._window
        expired = [
            sid for sid, ts in self._buckets.items()
            if all(t <= cutoff for t in ts)
        ]
        for sid in expired:
            del self._buckets[sid]

    @property
    def stats(self) -> dict:
        return {
            "active_sessions": len(self._buckets),
            "max_per_minute": self._max,
            "window_seconds": self._window,
        }


# Global rate limiter singleton
_voice_rate_limiter = VoiceRateLimiter()


def get_voice_rate_limiter() -> VoiceRateLimiter:
    """Return the singleton VoiceRateLimiter instance."""
    return _voice_rate_limiter


# ── REC-11: Voice Health Check ────────────────────────────────────────────────
def get_voice_health() -> Dict[str, Any]:
    """Kumpulkan health status lengkap voice subsystem.

    Digunakan oleh endpoint /api/jarvis/voice/health.
    Returns dict berisi status TTS, STT, wake word, cache, dan rate limiter.
    """
    health: Dict[str, Any] = {
        "status": "ok",
        "timestamp": time.time(),
    }

    # TTS Engine Status
    try:
        from SERVER.jarvis.voice.voice_config_store import get_voice_config_store
        store = get_voice_config_store()
        config = store.get()
        health["tts"] = {
            "engine": config.get("tts_engine", "auto"),
            "voice_name": config.get("voice_name", "unknown"),
            "voice_display": config.get("current_voice_display", ""),
            "offline_mode": config.get("offline_mode", False),
            "speech_rate": config.get("speech_rate", ""),
        }
    except Exception as e:
        health["tts"] = {"status": "error", "error": str(e)}

    # TTS Cache Stats (REC-7)
    try:
        from SERVER.jarvis.voice.tts_service import TTSService
        health["tts_cache"] = TTSService.get_cache_stats()
    except Exception as e:
        health["tts_cache"] = {"status": "error", "error": str(e)}

    # STT Engine Status
    try:
        from SERVER.jarvis.voice.stt_provider import FasterWhisperSTTProvider
        provider = FasterWhisperSTTProvider.__new__(FasterWhisperSTTProvider)
        health["stt"] = {
            "engine": "faster-whisper",
            "provider_name": "FasterWhisperSTTProvider",
            "status": "available",
        }
    except Exception as e:
        health["stt"] = {"status": "error", "error": str(e)}

    # Wake Word Engine Status
    try:
        import importlib
        oww_available = importlib.util.find_spec("openwakeword") is not None
        health["wake_word"] = {
            "engine": "openwakeword" if oww_available else "text_regex_fallback",
            "openwakeword_installed": oww_available,
            "status": "available",
        }
    except Exception as e:
        health["wake_word"] = {"status": "error", "error": str(e)}

    # Edge-TTS Package Status
    try:
        import edge_tts
        health["edge_tts"] = {
            "version": getattr(edge_tts, "__version__", "unknown"),
            "status": "installed",
        }
    except ImportError:
        health["edge_tts"] = {"status": "not_installed"}

    # Rate Limiter Stats (REC-10)
    health["rate_limiter"] = _voice_rate_limiter.stats

    return health
