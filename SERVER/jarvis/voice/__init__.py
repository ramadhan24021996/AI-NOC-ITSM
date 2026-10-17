"""
SERVER.jarvis.voice Package Init (Production) — v3.0 Natural Voice Narration Engine
====================================================================================
Re-exports production-grade STT, TTS, and WakeWord components.
No mock providers exported — mock classes live in tests/ only.

v3.0 additions:
  - SpokenTextNormalizer : LLM output → spoken-style text (markdown/akronim/angka)
  - SSMLBuilder          : Prosody control via SSML tags (rate, pitch, emphasis, break)
  - persona_voice_config : Registry suara per persona (voice name, prosody, severity overrides)
"""
from SERVER.jarvis.voice.stt_service import STTService
from SERVER.jarvis.voice.tts_service import TTSService
from SERVER.jarvis.voice.stt_provider import STTProvider, FasterWhisperSTTProvider, WhisperSTTProvider
from SERVER.jarvis.voice.tts_provider import TTSProvider, KokoroTTSProvider, EdgeTTSProvider
from SERVER.jarvis.voice.wake_word_detector import WakeWordDetector
from SERVER.jarvis.voice.spoken_text_normalizer import SpokenTextNormalizer
from SERVER.jarvis.voice.ssml_builder import SSMLBuilder
from SERVER.jarvis.voice.persona_voice_config import (
    PersonaVoiceProfile,
    get_voice_profile,
    get_voice_name,
    get_prosody_for_severity,
    list_all_personas,
)

__all__ = [
    # STT
    "STTService", "STTProvider", "FasterWhisperSTTProvider", "WhisperSTTProvider",
    # TTS
    "TTSService", "TTSProvider", "KokoroTTSProvider", "EdgeTTSProvider",
    # Wake Word
    "WakeWordDetector",
    # v3.0 Natural Voice
    "SpokenTextNormalizer",
    "SSMLBuilder",
    "PersonaVoiceProfile",
    "get_voice_profile",
    "get_voice_name",
    "get_prosody_for_severity",
    "list_all_personas",
]
