"""
SERVER.jarvis.voice.persona_voice_config — Persona Voice Registry
=================================================================
Sumber kebenaran tunggal untuk konfigurasi suara per persona JARVIS.
Mendefinisikan voice name, prosody defaults, dan SSML parameters
untuk setiap persona aktif.

Persona yang tersedia:
  - noc_engineer      : Suara teknis, kecepatan normal, nada tegas
  - incident_manager  : Lebih formal, sedikit lebih lambat, otoritatif
  - executive         : Tenang, bicara perlahan, prestige
  - alert_mode        : Mode darurat — lebih cepat, lebih keras
"""
from dataclasses import dataclass, field
from typing import Dict, Optional

# =============================================================================
# PERSONA VOICE CONFIG DATACLASS
# =============================================================================

@dataclass
class PersonaVoiceProfile:
    """Profil suara lengkap untuk satu persona JARVIS."""

    persona_id: str

    # EdgeTTS Neural Voice Name (Microsoft Azure Neural TTS)
    # Daftar lengkap: https://learn.microsoft.com/azure/cognitive-services/speech-service/language-support
    primary_voice: str          # Voice utama (id-ID)
    fallback_voice: str         # Fallback jika primary gagal

    # SSML Prosody Defaults
    rate: str = "+0%"           # Kecepatan bicara: "-20%" s.d. "+20%"
    pitch: str = "+0Hz"         # Nada dasar: "-5Hz" s.d. "+5Hz"
    volume: str = "default"     # Volume: "loud", "medium", "soft", "x-loud"

    # Per-severity prosody overrides
    # Format: severity → {rate, pitch, volume}
    severity_overrides: Dict[str, Dict[str, str]] = field(default_factory=dict)

    # Deskripsi persona untuk logging/debug
    description: str = ""


# =============================================================================
# REGISTRY PERSONA — tambahkan persona baru di sini
# =============================================================================

PERSONA_VOICE_REGISTRY: Dict[str, PersonaVoiceProfile] = {

    "noc_engineer": PersonaVoiceProfile(
        persona_id="noc_engineer",
        primary_voice="id-ID-ArdiNeural",
        fallback_voice="id-ID-GadisNeural",
        rate="-3%",           # Sedikit lebih lambat dari default agar jelas
        pitch="+0Hz",
        volume="default",
        severity_overrides={
            "CRITICAL": {"rate": "+10%", "pitch": "+1Hz", "volume": "loud"},
            "HIGH":     {"rate": "+5%",  "pitch": "+0Hz", "volume": "default"},
            "MEDIUM":   {"rate": "-3%",  "pitch": "+0Hz", "volume": "default"},
            "LOW":      {"rate": "-8%",  "pitch": "-1Hz", "volume": "soft"},
            "INFO":     {"rate": "-8%",  "pitch": "-1Hz", "volume": "soft"},
        },
        description="NOC Engineer: suara teknis, kecepatan normal, informasi langsung",
    ),

    "incident_manager": PersonaVoiceProfile(
        persona_id="incident_manager",
        primary_voice="id-ID-ArdiNeural",
        fallback_voice="id-ID-GadisNeural",
        rate="-8%",           # Lebih lambat, lebih berwibawa
        pitch="+1Hz",
        volume="default",
        severity_overrides={
            "CRITICAL": {"rate": "+5%",  "pitch": "+2Hz", "volume": "loud"},
            "HIGH":     {"rate": "+0%",  "pitch": "+1Hz", "volume": "default"},
            "MEDIUM":   {"rate": "-8%",  "pitch": "+0Hz", "volume": "default"},
            "LOW":      {"rate": "-12%", "pitch": "-1Hz", "volume": "soft"},
            "INFO":     {"rate": "-12%", "pitch": "-1Hz", "volume": "soft"},
        },
        description="Incident Manager: formal, otoritatif, cocok untuk eskalasi",
    ),

    "executive": PersonaVoiceProfile(
        persona_id="executive",
        primary_voice="id-ID-GadisNeural",
        fallback_voice="id-ID-ArdiNeural",
        rate="-12%",          # Paling lambat, paling tenang
        pitch="+0Hz",
        volume="default",
        severity_overrides={
            "CRITICAL": {"rate": "-5%",  "pitch": "+1Hz", "volume": "default"},
            "HIGH":     {"rate": "-8%",  "pitch": "+0Hz", "volume": "default"},
            "MEDIUM":   {"rate": "-12%", "pitch": "+0Hz", "volume": "soft"},
            "LOW":      {"rate": "-15%", "pitch": "-1Hz", "volume": "soft"},
            "INFO":     {"rate": "-15%", "pitch": "-1Hz", "volume": "soft"},
        },
        description="Executive: tenang, prestige, tidak terburu-buru",
    ),

    "alert_mode": PersonaVoiceProfile(
        persona_id="alert_mode",
        primary_voice="id-ID-ArdiNeural",
        fallback_voice="id-ID-GadisNeural",
        rate="+5%",           # Mode darurat: cepat dan tegas
        pitch="+2Hz",
        volume="loud",
        severity_overrides={
            "CRITICAL": {"rate": "+15%", "pitch": "+3Hz", "volume": "x-loud"},
            "HIGH":     {"rate": "+10%", "pitch": "+2Hz", "volume": "loud"},
            "MEDIUM":   {"rate": "+5%",  "pitch": "+1Hz", "volume": "default"},
            "LOW":      {"rate": "+0%",  "pitch": "+0Hz", "volume": "default"},
            "INFO":     {"rate": "+0%",  "pitch": "+0Hz", "volume": "default"},
        },
        description="Alert Mode: darurat penuh, kecepatan dan volume maksimum",
    ),
}

# Default fallback jika persona tidak ditemukan
DEFAULT_PERSONA_ID = "noc_engineer"


def get_voice_profile(persona_id: str) -> PersonaVoiceProfile:
    """
    Ambil PersonaVoiceProfile untuk persona_id yang diminta.
    Fallback ke 'noc_engineer' jika persona tidak dikenali.

    Args:
        persona_id: ID persona (noc_engineer | incident_manager | executive | alert_mode)

    Returns:
        PersonaVoiceProfile yang sesuai.
    """
    profile = PERSONA_VOICE_REGISTRY.get(persona_id)
    if profile is None:
        import logging
        logging.getLogger("jarvis.voice.persona_voice_config").warning(
            "[PersonaVoiceConfig] Unknown persona '%s', falling back to '%s'.",
            persona_id, DEFAULT_PERSONA_ID,
        )
        profile = PERSONA_VOICE_REGISTRY[DEFAULT_PERSONA_ID]
    return profile


def get_prosody_for_severity(persona_id: str, severity: str) -> Dict[str, str]:
    """
    Dapatkan prosody parameters (rate, pitch, volume) untuk kombinasi
    persona + severity tertentu.

    Args:
        persona_id: ID persona
        severity: CRITICAL | HIGH | MEDIUM | LOW | INFO

    Returns:
        Dict dengan keys: rate, pitch, volume
    """
    profile = get_voice_profile(persona_id)
    sev_upper = severity.upper()
    overrides = profile.severity_overrides.get(sev_upper, {})

    return {
        "rate":   overrides.get("rate",   profile.rate),
        "pitch":  overrides.get("pitch",  profile.pitch),
        "volume": overrides.get("volume", profile.volume),
    }


def get_voice_name(persona_id: str) -> str:
    """
    Kembalikan nama Microsoft Neural TTS voice untuk persona yang diminta.

    Args:
        persona_id: ID persona

    Returns:
        Voice name string (misal: "id-ID-ArdiNeural")
    """
    return get_voice_profile(persona_id).primary_voice


def list_all_personas() -> Dict[str, str]:
    """Kembalikan dict persona_id → description untuk semua persona terdaftar."""
    return {pid: p.description for pid, p in PERSONA_VOICE_REGISTRY.items()}
