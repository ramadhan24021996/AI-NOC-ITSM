"""
SERVER.jarvis.voice — Wake Word Detector Component
===================================================
Tahap 2.6B — Voice Integration

Mendeteksi kata kunci aktivasi (Wake Word) seperti:
 - "Hello Jarvis"
 - "Jarvis"
 - "Hey Jarvis"
 - "Halo Jarvis"

Memicu perubahan state Jarvis Presentation Runtime dari WAITING ke LISTENING
tanpa harus selalu menekan tombol mikrofon secara manual dan tanpa memakan CPU tinggi.

Dukungan Engine:
 1. OpenWakeWordEngine (OpenSource ONNX / Lightweight CPU)
 2. PorcupineWakeWordEngine (Picovoice Porcupine C-engine)
 3. TextRegexWakeWordEngine (Text caption matching fallback)
"""
import logging
import re
import importlib
import struct
from abc import ABC, abstractmethod
from typing import Tuple, List, Optional, Any

logger = logging.getLogger("jarvis.voice.wake_word")

DEFAULT_WAKE_WORDS = [
    "hello jarvis", "jarvis", "javis", "jarfis", "yarvis", "jabis", "hey jarvis", "halo jarvis", "hai jarvis",
    "bangun jarvis", "wakeup jarvis", "wake up jarvis", "bangun", "standby jarvis"
]


class BaseWakeWordEngine(ABC):
    """Abstract Base Class for Wake Word Audio Engines."""

    @property
    @abstractmethod
    def engine_name(self) -> str:
        pass

    @abstractmethod
    def process_frame(self, pcm_frame: bytes, sample_rate: int = 16000) -> Tuple[bool, Optional[str]]:
        """Processes raw PCM audio bytes frame and returns (is_detected, keyword)."""
        pass


class OpenWakeWordEngine(BaseWakeWordEngine):
    """Lightweight CPU OpenWakeWord Engine using ONNX runtime."""

    def __init__(self, target_keywords: Optional[List[str]] = None, threshold: float = 0.5):
        self.target_keywords = target_keywords or ["hey_jarvis", "jarvis"]
        self.threshold = threshold
        self._model: Any = None
        self._is_initialized = False

    def _lazy_init(self):
        if self._is_initialized:
            return
        try:
            oww_mod = importlib.import_module("openwakeword.model")
            Model = getattr(oww_mod, "Model")
            logger.info(f"[OpenWakeWordEngine] Initializing OpenWakeWord ONNX models for keywords {self.target_keywords}...")
            self._model = Model(wakeword_models=self.target_keywords, inference_framework="onnx")
            self._is_initialized = True
        except ImportError:
            logger.warning("[OpenWakeWordEngine] 'openwakeword' package not installed. Engine inactive.")
            self._is_initialized = False
        except Exception as e:
            logger.error(f"[OpenWakeWordEngine] Failed to initialize OpenWakeWord: {e}")
            self._is_initialized = False

    @property
    def engine_name(self) -> str:
        return "OpenWakeWord"

    def process_frame(self, pcm_frame: bytes, sample_rate: int = 16000) -> Tuple[bool, Optional[str]]:
        self._lazy_init()
        if not self._is_initialized or not self._model:
            return False, None

        try:
            # Convert raw bytes to int16 array
            num_samples = len(pcm_frame) // 2
            samples = struct.unpack(f"<{num_samples}h", pcm_frame)
            prediction = self._model.predict(samples)

            for key, score in prediction.items():
                if score >= self.threshold:
                    logger.info(f"[OpenWakeWordEngine] Wake word DETECTED: '{key}' (score: {score:.2f})")
                    return True, key
        except Exception as e:
            logger.error(f"[OpenWakeWordEngine] Audio processing error: {e}")

        return False, None


class PorcupineWakeWordEngine(BaseWakeWordEngine):
    """Picovoice Porcupine Ultra-Low CPU Wake Word Engine."""

    def __init__(self, keyword: str = "jarvis", access_key: Optional[str] = None):
        self.keyword = keyword
        self.access_key = access_key
        self._porcupine: Any = None
        self._is_initialized = False

    def _lazy_init(self):
        if self._is_initialized or not self.access_key:
            return
        try:
            pv_mod = importlib.import_module("pvporcupine")
            create = getattr(pv_mod, "create")
            logger.info(f"[PorcupineWakeWordEngine] Initializing Porcupine for keyword '{self.keyword}'...")
            self._porcupine = create(access_key=self.access_key, keywords=[self.keyword])
            self._is_initialized = True
        except ImportError:
            logger.warning("[PorcupineWakeWordEngine] 'pvporcupine' package not installed. Engine inactive.")
            self._is_initialized = False
        except Exception as e:
            logger.error(f"[PorcupineWakeWordEngine] Failed to initialize Porcupine: {e}")
            self._is_initialized = False

    @property
    def engine_name(self) -> str:
        return "Porcupine"

    def process_frame(self, pcm_frame: bytes, sample_rate: int = 16000) -> Tuple[bool, Optional[str]]:
        self._lazy_init()
        if not self._is_initialized or not self._porcupine:
            return False, None

        try:
            num_samples = len(pcm_frame) // 2
            pcm = struct.unpack(f"<{num_samples}h", pcm_frame)
            result = self._porcupine.process(pcm)
            if result >= 0:
                logger.info(f"[PorcupineWakeWordEngine] Wake word DETECTED: '{self.keyword}'")
                return True, self.keyword
        except Exception as e:
            logger.error(f"[PorcupineWakeWordEngine] Audio frame processing error: {e}")

        return False, None


class WakeWordDetector:
    """
    Detector utama yang menggabungkan deteksi audio streaming ultra-rendah CPU (OpenWakeWord/Porcupine)
    dengan deteksi teks/caption fallback.
    """

    def __init__(
        self,
        wake_words: Optional[List[str]] = None,
        sensitivity: float = 0.85,
        audio_engine: Optional[BaseWakeWordEngine] = None,
    ):
        self.wake_words = [w.lower() for w in (wake_words or DEFAULT_WAKE_WORDS)]
        self.sensitivity = sensitivity
        self.audio_engine = audio_engine or OpenWakeWordEngine()

    def detect_in_audio(self, pcm_bytes: bytes, sample_rate: int = 16000) -> Tuple[bool, Optional[str]]:
        """
        Mendeteksi wake word langsung dari stream frame audio PCM mentah tanpa memakan CPU tinggi.
        """
        if not pcm_bytes:
            return False, None

        return self.audio_engine.process_frame(pcm_bytes, sample_rate=sample_rate)

    def detect_in_text(self, text: str) -> Tuple[bool, Optional[str]]:
        """
        Memeriksa apakah teks mengandung salah satu kata kunci wake word.

        Returns:
            (is_detected, detected_keyword)
        """
        if not text or not text.strip():
            return False, None

        clean_text = text.strip().lower()
        for word in self.wake_words:
            # Match word boundary or prefix match with flexible punctuation
            pattern = r"(?:\b|^)" + re.escape(word) + r"(?:\b|[\s,\.\!\?:]|$)"
            if re.search(pattern, clean_text, re.IGNORECASE) or clean_text.startswith(word):
                logger.info(f"[WakeWordDetector] Wake word DETECTED: '{word}' in '{clean_text[:40]}'")
                return True, word

        return False, None

    def strip_wake_word(self, text: str) -> str:
        """
        Menghapus wake word dari awal, akhir, atau kata mandiri dalam teks query agar hanya perintah inti yang diteruskan.
        Contoh: "Jarvis, kenapa CPU server 98%?" → "kenapa CPU server 98%?"
        Contoh: "Play music romantis Javis" → "Play music romantis"
        Contoh: "kirim pesan Jarvis" → "kirim pesan"
        """
        if not text:
            return ""

        result = text.strip()
        words_to_strip = list(self.wake_words) + ["jarvis", "javis", "jarfis", "yarvis", "jabis", "jabes"]
        # Sort by length descending to match multi-word phrases first
        words_to_strip.sort(key=len, reverse=True)

        for word in words_to_strip:
            if not word:
                continue
            # 1. Beginning of text
            pattern_start = r"^\s*" + re.escape(word) + r"[\s,\.\!\?:]*"
            result = re.sub(pattern_start, "", result, flags=re.IGNORECASE).strip()
            # 2. End of text
            pattern_end = r"[\s,\.\!\?:]*" + re.escape(word) + r"\s*$"
            result = re.sub(pattern_end, "", result, flags=re.IGNORECASE).strip()
            # 3. Standalone word with boundaries
            pattern_word = r"\b" + re.escape(word) + r"\b"
            result = re.sub(pattern_word, "", result, flags=re.IGNORECASE).strip()

        # Clean trailing/leading punctuation (commas, colons, spaces) without stripping question marks/periods
        result = re.sub(r'\s+', ' ', result).strip(' ,:')
        return result if result else text.strip()
