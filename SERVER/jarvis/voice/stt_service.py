"""
SERVER.jarvis.voice - STT (Speech-to-Text) Service (Production)
================================================================
Speech-to-text processing for voice audio input using FasterWhisperSTTProvider.
Zero mock — production default is always the real provider.
"""
from typing import Optional
from SERVER.jarvis.interfaces.presentation_dtos import VoiceAudioPayloadDTO
from SERVER.jarvis.voice.stt_provider import STTProvider, FasterWhisperSTTProvider

import logging
logger = logging.getLogger("jarvis.voice.stt_service")


class STTService:
    """STT Processor Service delegating to production STTProvider."""

    def __init__(self, provider: Optional[STTProvider] = None):
        self.provider = provider or FasterWhisperSTTProvider()
        logger.info(f"[STTService] Initialized with provider: {self.provider.provider_name}")

    def transcribe(self, payload: VoiceAudioPayloadDTO) -> str:
        """Transcribes incoming audio bytes to text caption string."""
        return self.provider.transcribe_audio(payload)
