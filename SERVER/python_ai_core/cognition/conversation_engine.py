import logging
import json
import re
import random
import time
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("CONVERSATION_ENGINE")

class ConfidenceEngine:
    """Sub-module 1: Confidence Engine (Evaluates Certainty Score)"""
    def evaluate_confidence(self, response_text: str, confidence_score: float = 1.0) -> Tuple[str, float]:
        if confidence_score < 0.70:
            humble_prefix = "Saya belum cukup yakin dengan penyebab pastinya. Namun dari data awal, saya menemukan beberapa kemungkinan yang perlu kita verifikasi bersama: "
            return f"{humble_prefix}{response_text}", confidence_score
        return response_text, confidence_score


class SilenceEngine:
    """Sub-module 2: Silence & Short-Response Engine (Concise Natural Answers)"""
    def check_short_response(self, user_query: str, operator_name: str = "Rama") -> Optional[str]:
        q_clean = user_query.strip().lower().rstrip(".!?,")
        
        thanks_patterns = ["terima kasih", "makasih", "thanks", "thank you", "trims"]
        if any(p == q_clean or q_clean.startswith(p) for p in thanks_patterns):
            return f"Sama-sama, {operator_name}. Saya selalu siap jika Anda membutuhkan bantuan lebih lanjut."
            
        ack_patterns = ["ya", "iya", "lanjut", "lanjutkan", "ok", "oke", "siap", "baik"]
        if q_clean in ack_patterns:
            return f"Baik, {operator_name}. Saya lanjutkan."
            
        bye_patterns = ["dulu", "daah", "dadah", "sampai jumpa", "bye"]
        if any(p in q_clean for p in bye_patterns):
            return f"Baik, {operator_name}. Saya tetap memantau infrastruktur di latar belakang."
            
        return None


class ClarificationEngine:
    """Sub-module 3: Clarification Engine (Resolves Ambiguous Queries)"""
    def check_ambiguity(self, user_query: str) -> Optional[str]:
        q_clean = user_query.strip().lower()
        
        if q_clean in ["status server", "cek server", "bagaimana server", "kondisi server"]:
            return "Maksud Anda server database, server web, atau seluruh node infrastruktur?"
            
        if q_clean in ["cek jaringan", "status jaringan", "bagaimana jaringan"]:
            return "Maksud Anda antarmuka router core, status BGP routing, atau latensi link secara keseluruhan?"
            
        if q_clean in ["bagaimana insiden", "status insiden"]:
            return "Maksud Anda insiden aktif hari ini, atau riwayat insiden yang baru saja ditangani?"
            
        return None


class GoalTracker:
    """Sub-module 4: Conversation Goal Tracker"""
    def __init__(self):
        self._active_goals: Dict[str, Dict[str, Any]] = {}

    def get_goal(self, session_id: str) -> Optional[Dict[str, Any]]:
        return self._active_goals.get(session_id)

    def set_goal(self, session_id: str, goal_name: str, details: Optional[Dict[str, Any]] = None):
        self._active_goals[session_id] = {
            "goal": goal_name,
            "details": details or {},
            "updated_at": time.time()
        }

    def clear_goal(self, session_id: str):
        if session_id in self._active_goals:
            del self._active_goals[session_id]


class ActionExplanationLayer:
    """Sub-module 5: Action Explanation Layer (Explains AI Thought Process)"""
    def explain_action(self, action_name: str, target: str) -> str:
        explanations = {
            "CHECK_LOGS": f"Saya akan memeriksa log sistem pada {target} terlebih dahulu, kemudian membandingkannya dengan insiden serupa.",
            "RESTART_SERVICE": f"Saya sedang menyiapkan langkah pemulihan service pada {target} dan akan memverifikasi kesehatannya setelahnya.",
            "CHECK_METRICS": f"Saya sedang mengumpulkan telemetri CPU dan memori terbaru dari {target} untuk menganalisis lonjakan load."
        }
        return explanations.get(action_name, f"Saya sedang memproses analisis pada {target}...")


class ResponseFormatter:
    """Sub-module 6: Response Formatter (Strips Boilerplate & Natural Openers)"""
    def format_text(self, text: str) -> str:
        # Strip dry robotic phrases
        patterns_to_strip = [
            r"berdasarkan (hasil )?analisis( telemetri)?( real-time)?,?",
            r"berdasarkan data di atas,?",
            r"berdasarkan informasi yang diberikan,?",
            r"berdasarkan sistem ai noc,?",
            r"berikut (adalah )?hasil analisis:?",
            r"kesimpulannya( adalah)?,?",
            r"secara keseluruhan,?"
        ]
        
        formatted = text
        for p in patterns_to_strip:
            formatted = re.sub(p, "", formatted, flags=re.IGNORECASE).strip()

        # Capitalize first letter cleanly
        if formatted and len(formatted) > 1:
            formatted = formatted[0].upper() + formatted[1:]

        return formatted


class SentenceVariationEngine:
    """Sub-module 7: Sentence Variation Engine (Dynamic Non-monotonous Patterns)"""
    def __init__(self):
        self.normal_openers = [
            "Saya menemukan",
            "Sejauh pengamatan saya",
            "Dari data terbaru",
            "Ada satu hal yang perlu diperhatikan",
            "Hasil pantauan menunjukkan",
            "Catatan telemetri memperlihatkan"
        ]
        self.urgent_openers = [
            "Perlu perhatian segera",
            "Terdeteksi anomali kritis",
            "Indikasi gangguan terdeteksi pada"
        ]

    def add_opener(self, text: str, is_urgent: bool = False) -> str:
        # If text already starts with a natural opener or greeting, leave it
        if any(text.lower().startswith(w.lower()) for w in ["halo", "selamat", "rama", "saya", "saat ini"]):
            return text
            
        opener = random.choice(self.urgent_openers if is_urgent else self.normal_openers)
        return f"{opener}, {text[0].lower() + text[1:] if len(text) > 1 else text}"


class EmotionLayer:
    """Sub-module 8: Emotion & Tone Layer (CALM / WARN / CRITICAL Tones)"""
    def determine_tone(self, severity: str = "LOW") -> Dict[str, Any]:
        sev_upper = severity.upper().strip()
        if sev_upper == "CRITICAL":
            return {"emotion": "URGENT", "speed": 1.05, "pitch": 1.0, "prefix_style": "CRITICAL_ALERT"}
        elif sev_upper in ["HIGH", "WARN", "WARNING"]:
            return {"emotion": "CAUTIOUS", "speed": 0.98, "pitch": 1.0, "prefix_style": "WARNING_ALERT"}
        else:
            return {"emotion": "CALM", "speed": 0.95, "pitch": 1.0, "prefix_style": "NORMAL"}


class AdaptiveConversationEngine:
    """Sub-module 9: Adaptive Conversation Engine (4 Audience Modes)"""
    def adapt_to_audience(self, text: str, mode: str = "OPERATOR") -> str:
        mode_clean = mode.upper().strip()
        
        if mode_clean == "OPERATOR":
            # Concise, direct to the point
            sentences = [s.strip() for s in text.split(".") if s.strip()]
            return ". ".join(sentences[:3]) + "." if len(sentences) > 3 else text
            
        elif mode_clean == "ADMINISTRATOR":
            # Highly technical with log & metrics focus
            return f"[ADMIN METRICS] {text}"
            
        elif mode_clean == "EXECUTIVE":
            # High-level business SLA impact & risk summary
            return f"Ringkasan Eksekutif: {text}"
            
        elif mode_clean == "TRAINING":
            # Educational step-by-step walkthrough
            return f"Penjelasan Edukatif: {text}"
            
        return text


class ProsodyMetadataGenerator:
    """Sub-module 10: Prosody Metadata Generator (Web Speech Audio Metadata)"""
    def generate_metadata(
        self,
        text: str,
        emotion: str = "CALM",
        speed: float = 0.95,
        pause_before_ms: int = 200,
        pause_after_ms: int = 150
    ) -> Dict[str, Any]:
        return {
            "text": text,
            "emotion": emotion,
            "speed": speed,
            "pause_before_ms": pause_before_ms,
            "pause_after_ms": pause_after_ms,
            "emphasis": ["normal"]
        }


class PersonaEngine:
    """Sub-module 11: Persona Engine (J.A.R.V.I.S. Iron Man Persona)"""
    def apply_jarvis_persona(self, text: str, operator_name: str = "Rama", severity: str = "LOW") -> str:
        # Add respectful personal addressing
        clean_text = text.strip()
        
        if severity.upper() == "CRITICAL":
            return f"{operator_name}, {clean_text[0].lower() + clean_text[1:] if len(clean_text) > 1 else clean_text}"
        
        if not clean_text.lower().startswith(operator_name.lower()) and not clean_text.lower().startswith("halo"):
            return f"{operator_name}, {clean_text[0].lower() + clean_text[1:] if len(clean_text) > 1 else clean_text}"
            
        return clean_text


class JarvisConversationEngine:
    """
    Unified Facade: Jarvis Iron Man Enterprise Conversation Engine
    Connects all 11 conversation sub-modules into a seamless, production-ready pipeline.
    """

    def __init__(self):
        self.confidence = ConfidenceEngine()
        self.silence = SilenceEngine()
        self.clarification = ClarificationEngine()
        self.goal_tracker = GoalTracker()
        self.explanation = ActionExplanationLayer()
        self.formatter = ResponseFormatter()
        self.variation = SentenceVariationEngine()
        self.emotion = EmotionLayer()
        self.adaptive = AdaptiveConversationEngine()
        self.prosody = ProsodyMetadataGenerator()
        self.persona = PersonaEngine()

    def process_conversation(
        self,
        user_query: str,
        raw_llm_response: str,
        operator_name: str = "Rama",
        confidence_score: float = 1.0,
        severity: str = "LOW",
        audience_mode: str = "OPERATOR",
        session_id: str = "default_session"
    ) -> Dict[str, Any]:
        """
        Processes LLM output through the full 11-stage Jarvis Conversation Engine pipeline.
        """
        # 1. Silence & Short-Response Check
        short_res = self.silence.check_short_response(user_query, operator_name=operator_name)
        if short_res:
            meta = self.prosody.generate_metadata(short_res, emotion="CALM", speed=1.0)
            return {
                "final_text": short_res,
                "prosody": meta,
                "confidence_score": 1.0,
                "severity": "LOW",
                "audience_mode": audience_mode
            }

        # 2. Clarification Check for Ambiguous Queries
        clarify_res = self.clarification.check_ambiguity(user_query)
        if clarify_res:
            text = f"{operator_name}, {clarify_res[0].lower() + clarify_res[1:]}"
            meta = self.prosody.generate_metadata(text, emotion="CALM", speed=0.95)
            return {
                "final_text": text,
                "prosody": meta,
                "confidence_score": 1.0,
                "severity": "LOW",
                "audience_mode": audience_mode
            }

        # 3. Confidence Engine Evaluation
        conf_text, calibrated_conf = self.confidence.evaluate_confidence(raw_llm_response, confidence_score)

        # 4. Response Formatter (Strips robotic boilerplate)
        formatted_text = self.formatter.format_text(conf_text)

        # 5. Sentence Variation
        varied_text = self.variation.add_opener(formatted_text, is_urgent=(severity.upper() == "CRITICAL"))

        # 6. Persona Engine (J.A.R.V.I.S. persona & personal context)
        persona_text = self.persona.apply_jarvis_persona(varied_text, operator_name=operator_name, severity=severity)

        # 7. Adaptive Audience Mode
        adapted_text = self.adaptive.adapt_to_audience(persona_text, mode=audience_mode)

        # 8. Emotion & Prosody Metadata Generation
        tone = self.emotion.determine_tone(severity)
        prosody_meta = self.prosody.generate_metadata(
            text=adapted_text,
            emotion=tone["emotion"],
            speed=tone["speed"]
        )

        return {
            "final_text": adapted_text,
            "prosody": prosody_meta,
            "confidence_score": calibrated_conf,
            "severity": severity.upper(),
            "audience_mode": audience_mode.upper()
        }


_CONVERSATION_ENGINE_SINGLETON: Optional[JarvisConversationEngine] = None

def get_conversation_engine() -> JarvisConversationEngine:
    global _CONVERSATION_ENGINE_SINGLETON
    if _CONVERSATION_ENGINE_SINGLETON is None:
        _CONVERSATION_ENGINE_SINGLETON = JarvisConversationEngine()
    return _CONVERSATION_ENGINE_SINGLETON
