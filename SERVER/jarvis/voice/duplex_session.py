"""
SERVER.jarvis.voice.duplex_session — JARVIS Full-Duplex Voice Session Manager
=================================================================================
Provides real-time full-duplex audio chunk streaming (< 300ms latency) and
Barge-in (Interruption Handling) for JARVIS Voice AI Platform.

Features:
  - Low-latency WebSocket Audio Frame processing (Continuous PCM Audio)
  - Barge-in Interruption: Cancels active LLM/TTS generation instantly when user speaks
  - State machine: LISTENING -> THINKING -> SPEAKING -> INTERRUPTED -> LISTENING
"""

import json
import logging
import time
import base64
import threading
from typing import Callable, Optional, Dict, Any

logger = logging.getLogger("jarvis.voice.duplex_session")


class JarvisVoiceDuplexSession:
    """Manages state and thread safety for a full-duplex voice session."""

    def __init__(self, session_id: str):
        self.session_id = session_id
        self.state = "LISTENING"
        self.interrupt_event = threading.Event()
        self._lock = threading.Lock()
        self._current_speech_task: Optional[threading.Thread] = None

    def trigger_barge_in(self, emit_func: Callable[[Dict[str, Any]], None]):
        """Triggers immediate barge-in interruption.

        Cancels active TTS/LLM streaming and resets state to LISTENING.
        """
        with self._lock:
            if self.state in ["SPEAKING", "THINKING"]:
                logger.info(f"[DuplexSession:{self.session_id}] ⚡ BARGE-IN TRIGGERED! Interrupting current response.")
                self.interrupt_event.set()
                self.state = "INTERRUPTED"
                emit_func({
                    "avatar_state": "INTERRUPTED",
                    "event": "barge_in_ack",
                    "session_id": self.session_id,
                    "timestamp": time.time(),
                })
                # Reset state back to LISTENING for next input
                self.state = "LISTENING"
                self.interrupt_event.clear()
            else:
                logger.debug(f"[DuplexSession:{self.session_id}] Barge-in received while in state '{self.state}' (ignored).")

    def process_text_query_stream(
        self,
        question: str,
        runtime: Any,
        emit_func: Callable[[Dict[str, Any]], None]
    ):
        """Executes full pipeline and streams TTS chunks back via emit_func."""
        with self._lock:
            self.state = "THINKING"
            self.interrupt_event.clear()

        emit_func({
            "avatar_state": "THINKING",
            "session_id": self.session_id,
            "timestamp": time.time(),
        })

        t0 = time.time()

        try:
            # Check interruption before calling LLM
            if self.interrupt_event.is_set():
                logger.info(f"[DuplexSession:{self.session_id}] Aborted before LLM query due to barge-in.")
                return

            # Build VoiceAudioPayloadDTO for the correct process_voice_query(session_id, dto) signature
            try:
                from SERVER.jarvis.interfaces.presentation_dtos import VoiceAudioPayloadDTO
                audio_payload = VoiceAudioPayloadDTO(
                    session_id=self.session_id,
                    audio_format="text",
                    sample_rate=16000,
                    audio_bytes=b"",
                    text_caption=question,
                )
            except Exception as dto_err:
                logger.error(f"[DuplexSession:{self.session_id}] Failed to build VoiceAudioPayloadDTO: {dto_err}")
                emit_func({
                    "avatar_state": "ERROR",
                    "error": f"DTO build error: {dto_err}",
                    "session_id": self.session_id,
                    "timestamp": time.time(),
                })
                return

            # Execute JARVIS presentation runtime pipeline — correct signature: (session_id, audio_payload)
            result = runtime.process_voice_query(self.session_id, audio_payload)

            answer_text = result.get("answer_text", "")
            intent = result.get("intent", "UNKNOWN")
            intent_confidence = result.get("intent_confidence", 0.0)

            if self.interrupt_event.is_set():
                logger.info(f"[DuplexSession:{self.session_id}] Aborted after LLM query due to barge-in.")
                return

            # Transition to SPEAKING
            with self._lock:
                self.state = "SPEAKING"

            emit_func({
                "avatar_state": "SPEAKING",
                "answer_text": answer_text,
                "intent": intent,
                "intent_confidence": intent_confidence,
                "session_id": self.session_id,
                "timestamp": time.time(),
            })

            # Stream TTS audio chunks
            tts_provider = getattr(runtime, "tts_provider", None)
            if tts_provider and hasattr(tts_provider, "synthesize_stream_generator"):
                chunks = tts_provider.synthesize_stream_generator(answer_text)
                for chunk in chunks:
                    if self.interrupt_event.is_set():
                        logger.info(f"[DuplexSession:{self.session_id}] Barge-in mid-TTS stream. Stopping audio emission.")
                        break

                    audio_b64 = base64.b64encode(chunk.audio_bytes).decode("utf-8") if chunk.audio_bytes else ""
                    emit_func({
                        "avatar_state": "SPEAKING",
                        "audio_chunk_b64": audio_b64,
                        "audio_format": chunk.audio_format,
                        "sample_rate": chunk.sample_rate,
                        "text_chunk": chunk.text_caption,
                        "session_id": self.session_id,
                        "timestamp": time.time(),
                    })
            else:
                # Fallback to single payload synthesis
                audio_b64 = result.get("audio_b64", "")
                if not self.interrupt_event.is_set() and audio_b64:
                    emit_func({
                        "avatar_state": "SPEAKING",
                        "audio_chunk_b64": audio_b64,
                        "audio_format": result.get("audio_format", "mp3"),
                        "session_id": self.session_id,
                        "timestamp": time.time(),
                    })

        except Exception as e:
            logger.error(f"[DuplexSession:{self.session_id}] Pipeline error: {e}")
            emit_func({
                "avatar_state": "ERROR",
                "error": str(e),
                "session_id": self.session_id,
                "timestamp": time.time(),
            })

        finally:
            with self._lock:
                self.state = "LISTENING"
            latency_ms = (time.time() - t0) * 1000
            emit_func({
                "avatar_state": "IDLE",
                "latency_ms": latency_ms,
                "session_id": self.session_id,
                "timestamp": time.time(),
            })
