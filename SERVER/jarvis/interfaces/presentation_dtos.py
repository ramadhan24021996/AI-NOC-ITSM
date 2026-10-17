"""
SERVER.jarvis.interfaces - Presentation Layer DTOs
DTOs used exclusively by Jarvis presentation layer.

v2.1 (Gap #4 Fix): Tambah VoiceLatencyBreakdownDTO untuk end-to-end latency telemetry.
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

@dataclass
class ConversationContextDTO:
    session_id: str
    user_id: str
    active_persona_id: str = "noc_engineer"
    locale: str = "id-ID"
    voice_enabled: bool = True
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class DecisionTraceSummaryDTO:
    query_id: str
    execution_track: str
    evidence_score: float
    is_sufficient: bool
    summary_text: str

@dataclass
class VoiceAudioPayloadDTO:
    session_id: str
    audio_format: str  # e.g. "wav", "mp3", "pcm"
    sample_rate: int = 16000
    audio_bytes: bytes = b""
    text_caption: Optional[str] = None

@dataclass
class VoiceLatencyBreakdownDTO:
    """
    Gap #4: End-to-End latency breakdown untuk observability voice pipeline JARVIS.

    Breakdown per stage:
      stt_ms        — Waktu Speech-to-Text transcription
      translate_ms  — Waktu LLM voice command translation (termasuk phonetic + privacy redact)
      dispatch_ms   — Waktu dispatch intent ke NOC Bridge / action handler
      tts_ms        — Waktu Text-to-Speech synthesis (EdgeTTS / Kokoro / Parametric)
      total_ms      — Total end-to-end latency

    Digunakan untuk:
      - Identifikasi bottleneck stage (misal: TTS timeout, LLM slow response)
      - Dashboard observability NOC
      - Audit trail performance
    """
    stt_ms: int = 0           # Speech-to-Text transcription time
    translate_ms: int = 0     # LLM voice translation time
    dispatch_ms: int = 0      # Intent dispatch + action execution time
    tts_ms: int = 0           # TTS synthesis time
    total_ms: int = 0         # Total pipeline latency

    def to_dict(self) -> Dict[str, int]:
        return {
            "stt_ms": self.stt_ms,
            "translate_ms": self.translate_ms,
            "dispatch_ms": self.dispatch_ms,
            "tts_ms": self.tts_ms,
            "total_ms": self.total_ms,
        }

    def log_summary(self) -> str:
        """Format breakdown untuk logging — mudah dibaca di log output."""
        return (
            f"STT:{self.stt_ms}ms | "
            f"Translate:{self.translate_ms}ms | "
            f"Dispatch:{self.dispatch_ms}ms | "
            f"TTS:{self.tts_ms}ms | "
            f"TOTAL:{self.total_ms}ms"
        )

