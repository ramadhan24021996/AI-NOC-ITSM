import random
import logging
from typing import Optional, Dict, Any
from core.jarvis_opening_engine import JarvisOpeningEngine

logger = logging.getLogger(__name__)

class JarvisResponseEngine:
    """
    Jarvis Presentation Layer: Transforms raw technical data into clean, 
    eloquent, natural Indonesian spoken responses (Jarvis persona).
    """

    def __init__(self):
        self.opening_engine = JarvisOpeningEngine()

    NOC_PREFIXES = [
        "Saya mendeteksi indikasi pada sistem jaringan. ",
        "Hasil analisis telemetri sistem menunjukkan: ",
        "Pemeriksaan jaringan selesai, Pak. ",
        "Berikut hasil pemantauan AI NOC: "
    ]

    GENERAL_PREFIXES = [
        "Tentu, Rama. ",
        "Baik. ",
        "Berikut penjelasannya: ",
        "Sesuai informasi yang saya miliki, "
    ]

    def get_dynamic_opening(self, context: Optional[Dict[str, Any]] = None) -> str:
        """Generates a context-aware dynamic opening sentence."""
        return self.opening_engine.generate_opening(context)

    def format_noc_response(self, raw_text: str) -> str:
        """Sanitizes raw NOC data into natural speech."""
        prefix = random.choice(self.NOC_PREFIXES)
        
        # Clean up repetitive boilerplate if present
        text = raw_text.replace("Baik, Rama. ", "").replace("Sistem merespons. ", "").replace("Sesuai perintah Anda, ", "")
        
        return f"{prefix}{text}"

    def format_general_response(self, raw_text: str) -> str:
        """Formats general GPT response with Jarvis etiquette."""
        prefix = random.choice(self.GENERAL_PREFIXES)
        
        # If response already starts with polite greeting, don't duplicate
        if any(raw_text.startswith(p) for p in ["Tentu", "Baik", "Halo", "Selamat"]):
            return raw_text
            
        return f"{prefix}{raw_text}"

    def format_mixed_response(self, noc_response: str, general_response: str) -> str:
        """Merges NOC analysis and General Chat answers seamlessly."""
        clean_noc = self.format_noc_response(noc_response)
        clean_general = self.format_general_response(general_response)
        
        return f"{clean_noc}\n\nMengenai pertanyaan Anda selanjutnya:\n{clean_general}"

    def format_as_jarvis(self, raw_response: str, intent_type: str = "NOC") -> str:
        """Sanitizes raw technical response according to intent type into Jarvis spoken persona."""
        intent_type = intent_type.upper()
        if intent_type == "GENERAL_CHAT":
            return self.format_general_response(raw_response)
        elif intent_type == "MIXED":
            return self.format_general_response(raw_response)
        else:
            return self.format_noc_response(raw_response)
