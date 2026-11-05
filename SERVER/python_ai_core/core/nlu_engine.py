import re
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional

logger = logging.getLogger(__name__)

@dataclass
class NLUPayload:
    raw_query: str
    intent: str = "GENERAL_CHAT"
    confidence: float = 0.95
    entities: Dict[str, Any] = field(default_factory=dict)
    urgency: str = "NORMAL"
    sentiment: str = "NEUTRAL"
    language: str = "id"
    sub_queries: Dict[str, str] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "raw_query": self.raw_query,
            "intent": self.intent,
            "confidence": self.confidence,
            "entities": self.entities,
            "urgency": self.urgency,
            "sentiment": self.sentiment,
            "language": self.language,
            "sub_queries": self.sub_queries
        }

class NLUEngine:
    """
    Enterprise Natural Language Understanding (NLU) Engine:
    Performs intent classification, named entity recognition (NER), slot filling, 
    urgency detection, sentiment analysis, and multi-query decomposition.
    """

    DEVICE_PATTERNS = [
        r"\b(?:pc|tms|kasir|gudang|server|router|switch|nuc|node|dev|host)[-\w]*\b",
        r"\b[a-zA-Z0-9]+-[a-zA-Z0-9]+-[a-zA-Z0-9]+\b",
        r"\b[a-zA-Z0-9]+-[a-zA-Z0-9]+\b"
    ]

    IP_PATTERN = r"\b(?:\d{1,3}\.){3}\d{1,3}\b"

    EMERGENCY_KEYWORDS = [
        # Only truly critical/urgent phrases — NOT common Indonesian time words like 'sekarang'/'segera'
        "darurat", "urgens", "urgent", "mati total", "down parah",
        "critical", "kritis", "bahaya", "emergency", "down total",
        "tidak bisa diakses sama sekali", "blackout", "sistem mati"
    ]

    HIGH_URGENCY_KEYWORDS = [
        "segera", "cepat", "sekarang",   # time-pressure words → HIGH, not EMERGENCY
        "gangguan", "error", "problem", "masalah", "isu", "kendala", "macet", "timeout", "lag"
    ]

    SYMPTOM_KEYWORDS = {
        "ping timeout": ["ping timeout", "timeout", "rto", "request time out"],
        "offline": ["offline", "mati", "down", "terputus", "tidak bisa konek"],
        "disk full": ["disk full", "penuh", "storage full", "memori penuh", "ruang habis"],
        "spooler macet": ["spooler", "print spooler", "antrean macet", "printer macet", "tidak bisa ngeprint"],
        "high cpu": ["cpu tinggi", "lag", "lemot", "lambat", "hang"]
    }

    ACTION_KEYWORDS = {
        "OPEN_REMOTE": ["remote", "remot", "buka remot", "rustdesk", "vnc"],
        "CLEAR_QUEUE": ["bersihkan", "clear queue", "hapus antrean", "flush"],
        "RUN_PLAYBOOK": ["eksekusi", "jalankan", "playbook", "perintah", "remediasi"],
        "ANALYZE": ["analisis", "analisa", "cek", "periksa", "status", "kesehatan"]
    }

    def extract_entities(self, query: str) -> Dict[str, Any]:
        entities: Dict[str, Any] = {}
        q_lower = query.lower()

        # 1. IP Address Extraction
        ip_match = re.search(self.IP_PATTERN, query)
        if ip_match:
            entities["ip_address"] = ip_match.group(0)

        # 2. Target Device Extraction
        words = query.replace("?", "").replace("!", "").replace(",", "").split()
        target_pc = None
        for w in words:
            w_lower = w.lower()
            if any(prefix in w_lower for prefix in ["pc", "tms", "kasir", "gudang", "nuc", "router", "switch", "server"]):
                target_pc = w
                break
        
        if not target_pc:
            for pattern in self.DEVICE_PATTERNS:
                match = re.search(pattern, query, re.IGNORECASE)
                if match:
                    matched_str = match.group(0)
                    if matched_str.lower() not in ["pc", "status", "printer", "router", "switch", "server", "device"]:
                        target_pc = matched_str
                        break

        if target_pc:
            entities["device_name"] = target_pc

        # 3. Symptom Extraction
        detected_symptoms = []
        for symptom, keywords in self.SYMPTOM_KEYWORDS.items():
            if any(kw in q_lower for kw in keywords):
                detected_symptoms.append(symptom)
        if detected_symptoms:
            entities["symptoms"] = detected_symptoms

        # 4. Action Extraction
        detected_actions = []
        for action, keywords in self.ACTION_KEYWORDS.items():
            if any(kw in q_lower for kw in keywords):
                detected_actions.append(action)
        if detected_actions:
            entities["actions"] = detected_actions

        return entities

    def extract_urgency(self, query: str) -> str:
        q_lower = query.lower()
        if any(kw in q_lower for kw in self.EMERGENCY_KEYWORDS):
            return "EMERGENCY"
        elif any(kw in q_lower for kw in self.HIGH_URGENCY_KEYWORDS):
            return "HIGH"
        return "NORMAL"

    def extract_sentiment(self, query: str) -> str:
        q_lower = query.lower()
        negative_words = ["mati", "down", "error", "macet", "rusak", "parah", "gangguan", "gagal", "lemot", "rugi"]
        positive_words = ["bagus", "terima kasih", "berhasil", "lancar", "mantap", "ok", "oke", "siap"]

        neg_count = sum(1 for w in negative_words if w in q_lower)
        pos_count = sum(1 for w in positive_words if w in q_lower)

        if neg_count > pos_count:
            return "NEGATIVE"
        elif pos_count > neg_count:
            return "POSITIVE"
        return "NEUTRAL"

    def understand(self, query: str) -> NLUPayload:
        """
        Parses raw text query into structured NLUPayload.
        """
        entities = self.extract_entities(query)
        urgency = self.extract_urgency(query)
        sentiment = self.extract_sentiment(query)

        # Detect English vs Indonesian
        q_lower = query.lower()
        is_en = any(w in q_lower for w in ["what", "why", "how", "show", "check", "please", "status", "device"]) and not any(w in q_lower for w in ["apa", "kenapa", "bagaimana", "tolong", "cek", "saya"])
        language = "en" if is_en else "id"

        return NLUPayload(
            raw_query=query,
            confidence=0.98 if entities else 0.90,
            entities=entities,
            urgency=urgency,
            sentiment=sentiment,
            language=language
        )
