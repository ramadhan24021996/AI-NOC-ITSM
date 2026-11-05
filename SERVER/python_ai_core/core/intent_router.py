import re
import logging
from typing import Dict, Any
from core.nlu_engine import NLUEngine

logger = logging.getLogger(__name__)

class IntentRouter:
    """
    Intelligent Intent Router that classifies input queries into:
    - NOC: Incident analysis, network status, PC telemetry, remote commands
    - GENERAL_CHAT: General knowledge, concept explanation, casual chat
    - MIXED: Queries containing both NOC inquiry and General Chat
    """

    def __init__(self):
        self.nlu = NLUEngine()

    NOC_KEYWORDS = [
        "internet", "mati", "down", "pc", "tms", "gudang", "kasir", "remote",
        "insiden", "issue", "isu", "masalah", "kendala", "problem", "error", "trouble",
        "jaringan", "status", "kesehatan", "ping", "packet loss", "router", "switch",
        "printer", "playbook", "perintah", "analisa", "cek", "buka", "gangguan", "offline", "laporan",
        # Fix F3: Service status, n8n, NATS, audit, SLA
        "service", "layanan", "n8n", "workflow", "nats", "audit", "riwayat", "sla", "uptime",
        # Feature: panel navigation, network diagnostics, remediation
        "panel", "dashboard", "tampilkan", "navigate", "spooler", "flush", "sandbox",
        "teknisi", "assign", "tugaskan", "dispatch", "work order", "hitl", "approve", "setujui", "tolak",
        "network", "traceroute", "koneksi", "diagnosa", "diagnostik"
    ]

    GENERAL_TOPIC_KEYWORDS = [
        "apa itu", "jelaskan", "bagaimana cara", "siapa", "pengertian",
        "bgp", "ospf", "dns", "dhcp", "ip address", "tcp/ip", "subnetting",
        "resep", "cerita", "coding", "python"
    ]

    GREETING_KEYWORDS = [
        "halo", "hallo", "hai", "hi",
        "selamat", "pagi", "siang", "sore", "malam", "tes", "test",
        "jarvis", "ada", "siap", "halo cantik"
    ]

    GENERAL_KEYWORDS = GENERAL_TOPIC_KEYWORDS + GREETING_KEYWORDS

    def route_query(self, query: str) -> Dict[str, Any]:
        q_lower = query.lower()
        nlu_payload = self.nlu.understand(query)
        
        has_noc = any(kw in q_lower for kw in self.NOC_KEYWORDS) or bool(nlu_payload.entities.get("device_name"))
        has_general_topic = any(kw in q_lower for kw in self.GENERAL_TOPIC_KEYWORDS)
        has_greeting = any(kw in q_lower for kw in self.GREETING_KEYWORDS)
        has_general = has_general_topic or has_greeting
        
        # Check for mixed intents explicitly (explicit conjunction with both NOC and general topic)
        if ("sekalian" in q_lower or "sambil" in q_lower or "dan juga" in q_lower or "lalu" in q_lower) and (has_noc and has_general):
            intent_type = "MIXED"
            # Split query heuristically around conjunctions
            parts = re.split(r',?\s*(?:sekalian|sambil|dan juga|lalu)\s*', query, flags=re.IGNORECASE)
            
            noc_part = ""
            general_part = ""
            for part in parts:
                p_lower = part.lower()
                if any(kw in p_lower for kw in self.NOC_KEYWORDS):
                    noc_part += (" " + part if noc_part else part)
                else:
                    general_part += (" " + part if general_part else part)
                    
            return {
                "intent": "MIXED",
                "noc_query": noc_part.strip() or query,
                "general_query": general_part.strip() or query
            }
            
        if has_noc and not has_general_topic:
            # Clear NOC inquiry even if accompanied by greeting/assistant callout
            return {"intent": "NOC", "query": query}
        elif has_general and not has_noc:
            return {"intent": "GENERAL_CHAT", "query": query}
        elif has_noc and has_general_topic:
            # Query contains both operational NOC terms and general knowledge explanation topics
            return {
                "intent": "MIXED",
                "noc_query": query,
                "general_query": query
            }
        else:
            # Fallback to General Chat if unknown
            return {"intent": "GENERAL_CHAT", "query": query}

    def classify_and_split(self, query: str) -> Dict[str, Any]:
        """Alias method matching Enterprise AI OS Intent Router architecture spec."""
        return self.route_query(query)
