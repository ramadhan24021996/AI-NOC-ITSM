"""
SERVER.orchestrator.cognitive.context_tracker
===============================================
Component: Conversation Context Tracker (Builder)

Tracks ongoing conversation context parameters across turns:
  - topic (e.g. "CPU Server", "Database High Latency")
  - device (e.g. "srv-accounting-01", "192.168.1.10")
  - stage (e.g. "Diagnosis", "Recovery", "Risk Assessment")
"""
import re
import logging
from dataclasses import dataclass
from typing import Dict, Any, Optional

logger = logging.getLogger("orchestrator.cognitive.tracker")


@dataclass
class ConversationContextState:
    topic: str = "General Incident"
    device: str = "N/A"
    stage: str = "Diagnosis"
    user_role: str = "NOC Engineer"
    site_location: str = "N/A"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "topic": self.topic,
            "device": self.device,
            "stage": self.stage,
            "user_role": self.user_role,
            "site_location": self.site_location,
        }


class ConversationContextTracker:
    """
    Tracks and updates conversation context parameters per session.
    """

    def __init__(self):
        self._states: Dict[str, ConversationContextState] = {}

    def get_or_create_state(self, session_id: str) -> ConversationContextState:
        if not session_id:
            session_id = "default_session"
        if session_id not in self._states:
            self._states[session_id] = ConversationContextState()
        return self._states[session_id]

    def update_context(
        self,
        session_id: str,
        query_text: str,
        telemetry_context: Optional[Dict[str, Any]] = None,
        user_role: str = "NOC Engineer",
        site_location: str = "",
    ) -> ConversationContextState:
        state = self.get_or_create_state(session_id)
        state.user_role = user_role
        if site_location:
            state.site_location = site_location

        query_lower = query_text.lower()
        telemetry = telemetry_context or {}

        # 1. Device Extraction
        device_from_telem = telemetry.get("device_id") or telemetry.get("host") or telemetry.get("hostname")
        if device_from_telem:
            state.device = str(device_from_telem)
        else:
            dev_match = re.search(r"\b(srv-[a-z0-9-]+|node-[0-9]+|router-[0-9a-z-]+|host-[0-9a-z-]+)\b", query_lower)
            if dev_match:
                state.device = dev_match.group(1)
            else:
                ip_match = re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", query_text)
                if ip_match:
                    state.device = ip_match.group(0)

        # 2. Topic Extraction
        if "cpu" in query_lower:
            state.topic = "CPU High Utilization"
        elif "ram" in query_lower or "memory" in query_lower:
            state.topic = "Memory Exhaustion"
        elif "disk" in query_lower or "storage" in query_lower:
            state.topic = "Storage Capacity"
        elif "latency" in query_lower or "ping" in query_lower or "slow" in query_lower:
            state.topic = "Network Latency"
        elif "bgp" in query_lower or "link" in query_lower or "flap" in query_lower:
            state.topic = "BGP Routing Flap"
        elif "database" in query_lower or "postgres" in query_lower or "mysql" in query_lower:
            state.topic = "Database Operations"

        # 3. Stage Progression Tracking
        if any(kw in query_lower for kw in ["kenapa", "mengapa", "diagnosa", "sebab", "why", "root cause"]):
            state.stage = "Diagnosis"
        elif any(kw in query_lower for kw in ["terus bagaimana", "solusi", "recovery", "mitigasi", "fix", "restart"]):
            state.stage = "Recovery"
        elif any(kw in query_lower for kw in ["apakah aman", "resiko", "risk", "efek samping", "impact"]):
            state.stage = "Risk Assessment"

        logger.debug(f"[ContextTracker] Updated conv state | session={session_id} | topic={state.topic} | stage={state.stage}")
        return state
