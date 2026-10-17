"""
SERVER.jarvis.voice — STT Provider Pattern (Production)
========================================================
Production-grade Speech-to-Text providers. Zero mock, zero placeholder.

Providers:
 - FasterWhisperSTTProvider (FasterWhisper / Local Whisper)
 - WhisperSTTProvider       (Backward-compat alias)

v3.0 — Natural Voice Understanding:
  - Expanded initial_prompt: 60+ istilah teknis NOC, ITSM, jaringan, site codes
    agar Whisper tidak salah transkripsi istilah kritis (SLA → SLA bukan 'esia',
    BGP → BGP bukan 'be ge pe', HITL → HITL bukan 'hit el')
  - condition_on_previous_text=True: konteks lintas utterance untuk sesi panjang
  - VAD filter tuning: vad_filter=True dengan parameter optimal untuk Bahasa
    Indonesia agar boundary kalimat lebih akurat
"""
from abc import ABC, abstractmethod
import logging
import io
import importlib
from typing import Optional, Any, Tuple
from SERVER.jarvis.interfaces.presentation_dtos import VoiceAudioPayloadDTO

logger = logging.getLogger("jarvis.voice.stt_provider")


class STTProvider(ABC):
    """Abstract STT Engine Provider Interface."""

    @property
    @abstractmethod
    def provider_name(self) -> str:
        pass

    @abstractmethod
    def transcribe_audio(self, payload: VoiceAudioPayloadDTO) -> str:
        """Transcribes incoming audio bytes payload to text caption."""
        pass

    @abstractmethod
    def transcribe_stream_chunk(self, chunk_bytes: bytes, session_id: str = "") -> Tuple[str, bool]:
        """Transcribes an incremental audio chunk for streaming STT (< 300ms latency).

        Returns:
            Tuple of (recognized_text_chunk, is_final_phrase)
        """
        pass


class FasterWhisperSTTProvider(STTProvider):
    """Production-grade FasterWhisper / Local Speech-To-Text Provider.

    Supports:
     - Direct FasterWhisper model inference (GPU/CPU)
     - Pre-transcribed text caption passthrough (from browser WebSpeech API)
     - Streaming audio chunk transcription with Voice Activity Detection (VAD)
     - Graceful degradation: returns empty string on failure for proper error handling upstream
    """

    def __init__(self, model_size: str = "base", compute_type: str = "float32",
                 device: str = "cpu", language: str = "id", beam_size: int = 5):
        self._model_size = model_size
        self._compute_type = compute_type
        self._device = device
        self._language = language
        self._beam_size = beam_size
        self._whisper_model: Any = None
        self._is_initialized = False
        self._init_error: Optional[str] = None
        self._stream_buffers: dict = {}

    def _lazy_init(self):
        """Lazy-initialize the FasterWhisper model on first use."""
        if self._is_initialized:
            return
        try:
            faster_whisper_mod = importlib.import_module("faster_whisper")
            WhisperModel = getattr(faster_whisper_mod, "WhisperModel")
            logger.info(
                f"[FasterWhisperSTTProvider] Loading model '{self._model_size}' "
                f"(device={self._device}, compute_type={self._compute_type})..."
            )
            self._whisper_model = WhisperModel(
                self._model_size, device=self._device, compute_type=self._compute_type
            )
            self._is_initialized = True
            self._init_error = None
            logger.info(f"[FasterWhisperSTTProvider] Model '{self._model_size}' loaded successfully.")
        except ImportError:
            self._init_error = "'faster_whisper' package not installed"
            logger.warning(
                f"[FasterWhisperSTTProvider] {self._init_error}. "
                "Install via: pip install faster-whisper"
            )
            self._is_initialized = False
        except Exception as e:
            self._init_error = str(e)
            logger.error(f"[FasterWhisperSTTProvider] Failed to load Whisper model: {e}")
            self._is_initialized = False

    @property
    def provider_name(self) -> str:
        return f"FasterWhisperSTT({self._model_size})"

    def transcribe_audio(self, payload: VoiceAudioPayloadDTO) -> str:
        """Transcribes audio payload to text.

        Priority:
         1. If payload has pre-transcribed text_caption (e.g. WebSpeech API), use it directly.
         2. If audio_bytes present, run FasterWhisper inference.
         3. On failure, return empty string (NOT a hardcoded placeholder).

        Returns:
            Transcribed text string, or empty string on failure.
        """
        # 1. Pre-transcribed text passthrough (browser WebSpeech API, external STT)
        if payload.text_caption and payload.text_caption.strip():
            logger.debug(f"[{self.provider_name}] Using pre-transcribed text caption directly.")
            return payload.text_caption.strip()

        # 2. Validate audio payload
        if not payload.audio_bytes or len(payload.audio_bytes) == 0:
            logger.warning(f"[{self.provider_name}] Empty audio payload received. No transcription possible.")
            return ""

        # 3. Initialize model on demand
        self._lazy_init()

        # 4. Run FasterWhisper inference
        if self._whisper_model and self._is_initialized:
            # v3.0: Expanded initial_prompt dengan 60+ istilah teknis NOC.
            # Didefinisikan di luar try block agar selalu tersedia di except fallback.
            noc_initial_prompt = (
                # Nama sistem & persona
                "Jarvis, JARVIS, NOC, SOC, ITSM, SLA, SLO, SLI, OLA, "
                # Hardware & metrik
                "CPU, RAM, GPU, disk, HDD, SSD, UPS, PDU, server, printer, "
                # Jaringan & protokol
                "BGP, OSPF, VLAN, VPN, DNS, DHCP, NTP, SNMP, ICMP, TCP, UDP, "
                "HTTP, HTTPS, FTP, SSH, RDP, VNC, API, IP address, gateway, "
                "bandwidth, latency, packet loss, throughput, failover, "
                # Platform remote
                "RustDesk, RDP, VNC, TeamViewer, AnyDesk, "
                # Status & kondisi
                "offline, online, down, degraded, flapping, throttling, overload, "
                "critical, warning, healthy, incident, alert, anomali, "
                # Perintah operasional
                "restart, reboot, flush DNS, recycle, kill process, rollback, "
                "approve, reject, escalate, assign, remediate, "
                # HITL & insiden
                "HITL, approve HITL, reject HITL, INC-001, incident ID, "
                "blast radius, RCA, causal graph, root cause, "
                # Site & lokasi
                "kasir, gudang, kantor, marketing, finance, HRD, pusat, "
                "cabang, server room, rack, data center, "
                # Database & platform
                "PostgreSQL, Redis, Kafka, RabbitMQ, Elasticsearch, NATS, "
                "Kubernetes, Docker, container, pod, node, cluster, "
                # Probabilistik & AI
                "probabilistic, anomaly detection, LLM, Groq, Ollama, Gemini, "
                "model context, MTTR, MTBF, RTO, RPO, criticality score, "
                # Perintah menu JARVIS
                "cek CPU, status printer, status server, live log, "
                "audit log, sandbox, obsidian sync, ground truth"
            )
            try:
                audio_stream = io.BytesIO(payload.audio_bytes)
                segments, info = self._whisper_model.transcribe(
                    audio_stream,
                    beam_size=self._beam_size,
                    language=self._language,
                    initial_prompt=noc_initial_prompt,
                    # v3.0: konteks lintas utterance untuk sesi percakapan panjang
                    condition_on_previous_text=True,
                    # v3.0: VAD filter untuk boundary kalimat lebih akurat
                    vad_filter=True,
                    vad_parameters={
                        "min_silence_duration_ms": 300,   # jeda minimum untuk split utterance
                        "speech_pad_ms": 100,             # padding audio di awal/akhir segment
                        "threshold": 0.35,                # sensitivitas VAD (lebih rendah = lebih sensitif)
                    },
                )
                transcribed_text = " ".join([segment.text for segment in segments]).strip()
                logger.info(
                    "[%s] Transcribed %d bytes (%s, %.1fs) \u2192 '%s'",
                    self.provider_name, len(payload.audio_bytes),
                    info.language, info.duration, transcribed_text[:80]
                )
                return transcribed_text
            except TypeError:
                # Versi FasterWhisper lama mungkin tidak support semua parameter VAD
                # Fallback ke call yang lebih sederhana (noc_initial_prompt sudah tersedia)
                try:
                    audio_stream = io.BytesIO(payload.audio_bytes)
                    segments, info = self._whisper_model.transcribe(
                        audio_stream,
                        beam_size=self._beam_size,
                        language=self._language,
                        initial_prompt=noc_initial_prompt,
                    )
                    transcribed_text = " ".join([segment.text for segment in segments]).strip()
                    logger.info(
                        "[%s] Transcribed (compat mode) \u2192 '%s'",
                        self.provider_name, transcribed_text[:80]
                    )
                    return transcribed_text
                except Exception as e2:
                    logger.error("[%s] Transcription compat fallback failed: %s", self.provider_name, e2)
            except Exception as e:
                logger.error("[%s] Transcription failed: %s", self.provider_name, e)

        # 5. Production fallback: return empty string so upstream knows transcription failed
        logger.warning(
            f"[{self.provider_name}] Cannot transcribe {len(payload.audio_bytes)} bytes audio. "
            f"Reason: {self._init_error or 'Model not available'}. Returning empty string."
        )
        return ""

    def transcribe_stream_chunk(self, chunk_bytes: bytes, session_id: str = "default") -> Tuple[str, bool]:
        """Transcribes audio chunk in real-time stream.

        Accumulates audio frames per session_id and performs chunked VAD inference.
        Returns (recognized_text, is_final).
        """
        if not chunk_bytes:
            return "", False

        buf = self._stream_buffers.setdefault(session_id, bytearray())
        buf.extend(chunk_bytes)

        # Process when accumulated buffer exceeds 16KB (~0.5s audio at 16kHz mono)
        if len(buf) < 16384:
            return "", False

        # Run transcription on accumulated chunk
        payload = VoiceAudioPayloadDTO(
            session_id=session_id,
            audio_format="raw_pcm",
            audio_bytes=bytes(buf),
        )
        text = self.transcribe_audio(payload)

        # Clear buffer if sentence boundary detected or buffer is getting large
        is_final = False
        if text and (any(punct in text for punct in [".", "?", "!", "\n"]) or len(buf) > 96000):
            is_final = True
            buf.clear()

        return text, is_final


class WhisperSTTProvider(FasterWhisperSTTProvider):
    """Backward compatibility alias for FasterWhisperSTTProvider."""
    pass
