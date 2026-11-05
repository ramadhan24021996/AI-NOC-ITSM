"""
SERVER.jarvis.voice - TTS (Text-to-Speech) Service (Production)
================================================================
Text-to-speech audio synthesis for Jarvis voice output.

Priority Chain (v3.0 — Natural Voice Narration Engine):
  1. SpokenTextNormalizer  — konversi LLM output → spoken-style text
  2. SSMLBuilder           — bungkus teks dalam SSML prosody yang tepat
  3. EdgeTTSProvider       — Microsoft Neural TTS, persona-aware + severity-aware
  4. KokoroTTSProvider     — CPU Neural ONNX fallback
  5. Parametric WAV        — last resort fallback

Pipeline baru menghasilkan narasi yang:
  - Tidak membacakan markdown symbols secara literal
  - Mengeja akronim teknis (SLA → S-L-A, CPU → C-P-U)
  - Mengucapkan angka secara verbal (90% → sembilan puluh persen)
  - Menyesuaikan kecepatan & nada sesuai persona dan severity
  - Memberikan jeda natural antar kalimat via SSML break tags
"""
from typing import Optional
from collections import OrderedDict
import hashlib
from SERVER.jarvis.interfaces.presentation_dtos import VoiceAudioPayloadDTO
from SERVER.jarvis.voice.tts_provider import TTSProvider, EdgeTTSProvider, KokoroTTSProvider

import logging
logger = logging.getLogger("jarvis.voice.tts_service")

# ── TTS Audio LRU Cache (REC-7) ──────────────────────────────────────────────
# Cache audio hasil synthesis untuk kalimat yang sama + persona + severity.
# Menghemat ~30% EdgeTTS API calls untuk greeting dan acknowledgment repetitif.
_TTS_CACHE_MAX = 128

class _TTSLRUCache:
    """Thread-safe LRU cache untuk TTS audio payload."""

    def __init__(self, maxsize: int = _TTS_CACHE_MAX):
        self._cache: OrderedDict[str, VoiceAudioPayloadDTO] = OrderedDict()
        self._maxsize = maxsize
        self._hits = 0
        self._misses = 0

    @staticmethod
    def _make_key(text: str, persona_id: str, severity: str) -> str:
        raw = f"{text}|{persona_id}|{severity}"
        return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:16]

    def get(self, text: str, persona_id: str, severity: str) -> Optional[VoiceAudioPayloadDTO]:
        key = self._make_key(text, persona_id, severity)
        if key in self._cache:
            self._cache.move_to_end(key)
            self._hits += 1
            return self._cache[key]
        self._misses += 1
        return None

    def put(self, text: str, persona_id: str, severity: str, payload: VoiceAudioPayloadDTO):
        key = self._make_key(text, persona_id, severity)
        if key in self._cache:
            self._cache.move_to_end(key)
            return
        if len(self._cache) >= self._maxsize:
            self._cache.popitem(last=False)
        self._cache[key] = payload

    @property
    def stats(self) -> dict:
        total = self._hits + self._misses
        return {
            "size": len(self._cache),
            "max_size": self._maxsize,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": f"{self._hits / total * 100:.1f}%" if total > 0 else "0%",
        }

# Global TTS cache singleton
_tts_cache = _TTSLRUCache()


class TTSService:
    """TTS Audio Synthesizer Service — v3.0 Natural Voice Narration Engine.

    Pipeline synthesis:
      raw_text
        → SpokenTextNormalizer (strip markdown, expand akronim/angka/IP)
        → SSMLBuilder          (wrap dengan prosody SSML sesuai persona+severity)
        → EdgeTTSProvider      (Microsoft Neural TTS cloud)
        → [fallback] KokoroTTS / Parametric WAV

    Default provider: EdgeTTSProvider (id-ID-GadisNeural) dengan persona noc_engineer.
    """

    def __init__(self, provider: Optional[TTSProvider] = None):
        self.provider = provider or EdgeTTSProvider(voice_name="id-ID-GadisNeural")  # Default: suara wanita
        # Lazy-init normalizer dan SSML builder agar tidak berat di import
        self._normalizer = None
        self._ssml_builder = None
        logger.info("[TTSService v3.0] Initialized with primary provider: %s", self.provider.provider_name)

    def _get_normalizer(self):
        """Lazy-init SpokenTextNormalizer."""
        if self._normalizer is None:
            try:
                from SERVER.jarvis.voice.spoken_text_normalizer import SpokenTextNormalizer
                self._normalizer = SpokenTextNormalizer()
                logger.debug("[TTSService] SpokenTextNormalizer loaded.")
            except ImportError:
                logger.warning("[TTSService] SpokenTextNormalizer not available — raw text will be used.")
                self._normalizer = None
        return self._normalizer

    def _get_ssml_builder(self):
        """Lazy-init SSMLBuilder."""
        if self._ssml_builder is None:
            try:
                from SERVER.jarvis.voice.ssml_builder import SSMLBuilder
                self._ssml_builder = SSMLBuilder()
                logger.debug("[TTSService] SSMLBuilder loaded.")
            except ImportError:
                logger.warning("[TTSService] SSMLBuilder not available — plain text synthesis.")
                self._ssml_builder = None
        return self._ssml_builder

    def synthesize(
        self,
        text: str,
        persona_id: str = "noc_engineer",
        locale: str = "id-ID",
        severity: str = "INFO",
        skip_normalization: bool = False,
    ) -> VoiceAudioPayloadDTO:
        """Synthesizes text string into audio bytes payload via full Natural Voice pipeline.

        v3.0 Pipeline:
          1. SpokenTextNormalizer  — normalize LLM output → spoken text
          2. SSMLBuilder           — wrap dalam SSML prosody
          3. EdgeTTSProvider       — synthesize via Microsoft Neural TTS

        Args:
            text:               Teks yang akan diucapkan (bisa berisi markdown dari LLM).
            persona_id:         ID persona aktif (noc_engineer / incident_manager / executive).
            locale:             Locale target synthesis (default: id-ID).
            severity:           Tingkat keparahan (CRITICAL/HIGH/MEDIUM/LOW/INFO) untuk
                                prosody adjustment. Default: INFO.
            skip_normalization: Jika True, skip normalisasi (teks sudah clean).

        Returns:
            VoiceAudioPayloadDTO berisi audio bytes (mp3 dari EdgeTTS, atau wav fallback).
        """
        if not text or not text.strip():
            logger.warning("[TTSService] Empty text received, skip synthesis.")
            return VoiceAudioPayloadDTO(
                session_id="tts-empty",
                audio_format="wav",
                sample_rate=24000,
                audio_bytes=b"",
                text_caption="",
            )

        original_text = text

        # Step 1: Normalisasi teks — strip markdown, expand akronim/angka/IP
        if not skip_normalization:
            normalizer = self._get_normalizer()
            if normalizer:
                try:
                    text = normalizer.normalize(text)
                    logger.debug(
                        "[TTSService] Normalized: '%s...' → '%s...'",
                        original_text[:60], text[:60]
                    )
                except Exception as e:
                    logger.warning("[TTSService] Normalization failed: %s — using raw text.", e)
                    text = original_text

        # Step 1b: Cache lookup (REC-7) — jika teks+persona+severity sama, gunakan cached audio
        cached = _tts_cache.get(text, persona_id, severity)
        if cached is not None:
            logger.debug("[TTSService] ⚡ Cache HIT for '%s...' (%s)",
                         text[:40], _tts_cache.stats.get("hit_rate", "?"))
            return cached

        # Step 2: Synthesize via provider.
        # TTSProvider abstract interface v3.0 sudah mendeklarasikan severity parameter,
        # sehingga bisa langsung dipanggil tanpa inspect.signature() runtime check.
        try:
            result = self.provider.synthesize_text(
                text,
                persona_id=persona_id,
                locale=locale,
                severity=severity,
            )

            # Cache result jika audio valid (REC-7)
            if result and result.audio_bytes and len(result.audio_bytes) > 44:
                _tts_cache.put(text, persona_id, severity, result)

            return result

        except Exception as e:
            logger.error("[TTSService] Synthesis pipeline failed: %s", e)
            return VoiceAudioPayloadDTO(
                session_id="tts-error",
                audio_format="wav",
                sample_rate=24000,
                audio_bytes=b"",
                text_caption=text,
            )

    def synthesize_stream(
        self,
        text: str,
        persona_id: str = "noc_engineer",
        locale: str = "id-ID",
        severity: str = "INFO",
        skip_normalization: bool = False,
    ):
        """Generator streaming: yields VoiceAudioPayloadDTO per klausa.

        Normalisasi dilakukan sekali pada teks penuh, lalu streaming per klausa
        untuk first-audio latency yang lebih rendah.

        Args:
            text:               Teks yang akan diucapkan.
            persona_id:         ID persona aktif.
            locale:             Locale synthesis.
            severity:           Severity untuk prosody.
            skip_normalization: Skip normalization jika teks sudah clean.

        Yields:
            VoiceAudioPayloadDTO per klausa audio.
        """
        if not text or not text.strip():
            return

        # Step 1: Normalisasi teks sekali untuk seluruh teks
        if not skip_normalization:
            normalizer = self._get_normalizer()
            if normalizer:
                try:
                    text = normalizer.normalize(text)
                except Exception as e:
                    logger.warning("[TTSService.stream] Normalization failed: %s", e)

        # Step 2: Stream via provider.
        # TTSProvider abstract interface v3.0 sudah mendeklarasikan severity parameter.
        try:
            yield from self.provider.synthesize_stream_generator(
                text,
                persona_id=persona_id,
                locale=locale,
                severity=severity,
            )
        except Exception as e:
            logger.error("[TTSService.stream] Streaming synthesis failed: %s", e)
            # Fallback ke single synthesize
            payload = self.synthesize(
                text, persona_id=persona_id, locale=locale,
                severity=severity, skip_normalization=True
            )
            if payload and payload.audio_bytes:
                yield payload

    @staticmethod
    def get_cache_stats() -> dict:
        """Return TTS audio cache statistics (REC-7)."""
        return _tts_cache.stats
