"""
SERVER.jarvis.voice.voice_config_store — JARVIS Voice & Gender Config Store
===========================================================================
Thread-safe, singleton store for runtime voice configuration.
Persists to JSON file so settings survive server restart.

Settings persisted:
  - active_persona   : noc_engineer | incident_manager | executive | alert_mode
  - voice_gender     : male | female | formal
  - voice_name       : id-ID-ArdiNeural | id-ID-GadisNeural | en-US-AriaNeural
  - speech_rate      : "-20%" ... "+20%"
  - speech_pitch     : "-5Hz" ... "+5Hz"
  - offline_mode     : true | false  (force local Formant engine)
  - tts_engine       : edge | kokoro | auto
"""
from __future__ import annotations

import json
import logging
import os
import threading
from dataclasses import asdict, dataclass, field
from typing import Any, Dict

logger = logging.getLogger("jarvis.voice.config_store")

# ─── Config Storage Path ──────────────────────────────────────────────────────
_STORE_PATH = os.path.join(
    os.path.dirname(__file__), "_jarvis_voice_config.json"
)

# ─── Voice Profile Catalog (available voices) ─────────────────────────────────
AVAILABLE_VOICES: Dict[str, Dict[str, Any]] = {
    "id-ID-ArdiNeural": {
        "display_name": "Ardi — Bahasa Indonesia (Pria Neural)",
        "gender": "male",
        "locale": "id-ID",
        "engine": "edge",
        "description": "Suara pria profesional Bahasa Indonesia, jernih & tegas untuk NOC.",
        "badge": "🎙️ PRIA",
        "badge_color": "#38bdf8",
    },
    "id-ID-GadisNeural": {
        "display_name": "Gadis — Bahasa Indonesia (Wanita Neural)",
        "gender": "female",
        "locale": "id-ID",
        "engine": "edge",
        "description": "Suara wanita jernih Bahasa Indonesia, ramah & natural untuk operator.",
        "badge": "🎤 WANITA",
        "badge_color": "#f472b6",
    },
    "en-US-AriaNeural": {
        "display_name": "Aria — English US (Female, Formal)",
        "gender": "female",
        "locale": "en-US",
        "engine": "edge",
        "description": "English US female neural voice, calm and formal for executive mode.",
        "badge": "👔 FORMAL",
        "badge_color": "#a78bfa",
    },
    "en-US-GuyNeural": {
        "display_name": "Guy — English US (Male, Clear)",
        "gender": "male",
        "locale": "en-US",
        "engine": "edge",
        "description": "English US male voice, clear and authoritative for technical readouts.",
        "badge": "📢 MALE EN",
        "badge_color": "#34d399",
    },
    "formant-id-offline": {
        "display_name": "Acoustic Formant (Offline 100%)",
        "gender": "neutral",
        "locale": "id-ID",
        "engine": "kokoro",
        "description": "Engine lokal berbasis Klatt Formant Resonator — aktif saat internet putus.",
        "badge": "📡 OFFLINE",
        "badge_color": "#f59e0b",
    },
}

# ─── Default Config ────────────────────────────────────────────────────────────
@dataclass
class VoiceConfig:
    """JARVIS Runtime Voice Configuration — stored and served via REST."""

    active_persona: str = "noc_engineer"
    voice_name: str = "id-ID-GadisNeural"       # Default: suara wanita Gadis
    speech_rate: str = "-3%"
    speech_pitch: str = "+0Hz"
    speech_volume: str = "default"
    offline_mode: bool = False          # Force Formant offline engine
    tts_engine: str = "auto"           # "edge" | "kokoro" | "auto"
    preview_enabled: bool = True
    # Computed display fields (not persisted separately)
    current_voice_display: str = "Gadis — Bahasa Indonesia (Wanita Neural)"
    current_badge: str = "🎤 WANITA"

    def to_dict(self) -> Dict[str, Any]:
        d = asdict(self)
        # Attach full catalog for UI rendering
        d["available_voices"] = AVAILABLE_VOICES
        d["available_personas"] = {
            "noc_engineer": {
                "display": "NOC Engineer",
                "description": "Suara teknis, kecepatan normal, nada profesional",
                "icon": "fa-server",
                "color": "#38bdf8",
            },
            "incident_manager": {
                "display": "Incident Manager",
                "description": "Lebih formal, otoritatif, cocok untuk eskalasi",
                "icon": "fa-triangle-exclamation",
                "color": "#f59e0b",
            },
            "executive": {
                "display": "Executive",
                "description": "Tenang, prestige, perlahan dan jelas",
                "icon": "fa-briefcase",
                "color": "#a78bfa",
            },
            "alert_mode": {
                "display": "Alert / Emergency",
                "description": "Mode darurat — cepat, keras, tegas",
                "icon": "fa-bell",
                "color": "#ef4444",
            },
        }
        return d


# ─── Singleton Store ───────────────────────────────────────────────────────────
class VoiceConfigStore:
    """Thread-safe singleton store for JARVIS Voice Config."""

    _instance: "VoiceConfigStore | None" = None
    _lock: threading.Lock = threading.Lock()

    def __new__(cls) -> "VoiceConfigStore":
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    inst = super().__new__(cls)
                    inst._config = VoiceConfig()
                    inst._rw_lock = threading.RLock()
                    inst._load()
                    cls._instance = inst
        return cls._instance

    # ── Persistence ────────────────────────────────────────────────────────
    def _load(self) -> None:
        if not os.path.exists(_STORE_PATH):
            return
        try:
            with open(_STORE_PATH, "r", encoding="utf-8") as f:
                saved = json.load(f)
            for key, val in saved.items():
                if hasattr(self._config, key) and key != "available_voices" and key != "available_personas":
                    setattr(self._config, key, val)
            self._update_display_fields()
            logger.info("[VoiceConfigStore] Loaded config from %s", _STORE_PATH)
        except Exception as e:
            logger.warning("[VoiceConfigStore] Failed to load config: %s", e)

    def _save(self) -> None:
        try:
            data = asdict(self._config)
            with open(_STORE_PATH, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.warning("[VoiceConfigStore] Failed to save config: %s", e)

    def _update_display_fields(self) -> None:
        voice_meta = AVAILABLE_VOICES.get(self._config.voice_name, {})
        self._config.current_voice_display = voice_meta.get("display_name", self._config.voice_name)
        self._config.current_badge = voice_meta.get("badge", "🎙️")

    # ── Public API ─────────────────────────────────────────────────────────
    def get(self) -> Dict[str, Any]:
        """Return current config as dict (with full catalog for UI)."""
        with self._rw_lock:
            return self._config.to_dict()

    def update(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Update config from payload dict. Returns updated config."""
        allowed_keys = {
            "active_persona", "voice_name", "speech_rate",
            "speech_pitch", "speech_volume", "offline_mode",
            "tts_engine", "preview_enabled",
        }
        with self._rw_lock:
            changed = False
            for key, val in payload.items():
                if key in allowed_keys and hasattr(self._config, key):
                    setattr(self._config, key, val)
                    changed = True

            if changed:
                # Sync persona primary voice if persona changed
                if "active_persona" in payload and "voice_name" not in payload:
                    from SERVER.jarvis.voice.persona_voice_config import get_voice_profile
                    try:
                        profile = get_voice_profile(self._config.active_persona)
                        self._config.voice_name = profile.primary_voice
                        self._config.speech_rate = profile.rate
                        self._config.speech_pitch = profile.pitch
                    except Exception:
                        pass

                self._update_display_fields()
                self._save()
                logger.info(
                    "[VoiceConfigStore] Config updated: persona=%s voice=%s engine=%s offline=%s",
                    self._config.active_persona,
                    self._config.voice_name,
                    self._config.tts_engine,
                    self._config.offline_mode,
                )

        return self.get()

    def get_active_voice_name(self) -> str:
        """Return the active EdgeTTS voice name for current config."""
        with self._rw_lock:
            return self._config.voice_name

    def get_active_persona(self) -> str:
        with self._rw_lock:
            return self._config.active_persona

    def is_offline_mode(self) -> bool:
        with self._rw_lock:
            return self._config.offline_mode

    def get_tts_engine(self) -> str:
        with self._rw_lock:
            return self._config.tts_engine


# ─── Global accessor ──────────────────────────────────────────────────────────
def get_voice_config_store() -> VoiceConfigStore:
    """Return the singleton VoiceConfigStore instance."""
    return VoiceConfigStore()
