"""
agent_tray_formatter.py
========================
Adaptive Agent Tray PC Notification Message Formatter.
Menghasilkan payload pesan terstruktur dan kontekstual untuk ditampilkan pada
Agent Tray PC / Edge Client tanpa pesan generik.
"""

import json
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("AgentTrayFormatter")


class AgentTrayContextFormatter:
    """
    Formatter Pesan Adaptif Kontekstual untuk Agent Tray PC Kasir / Workstation.
    """

    def format_agent_tray_payload(
        self,
        incident_context: Any
    ) -> Dict[str, Any]:
        """
        Menyusun payload JSON terstruktur untuk dikirimkan ke Edge Agent Tray.
        """
        evidence_checks = []
        for ev in incident_context.evidence:
            k = ev.get("key", "")
            v = ev.get("value", "")
            evidence_checks.append(f"• {k}: {v}")

        if not evidence_checks:
            evidence_checks = ["• Status telemetri awal terkumpul."]

        selected_action_name = "N/A"
        if incident_context.current_action:
            selected_action_name = incident_context.current_action.get("name", "N/A")
        elif incident_context.next_action:
            selected_action_name = incident_context.next_action.get("name", "N/A")

        verif_summary = "VERIFICATION_PENDING"
        if incident_context.verification_result:
            verif_summary = incident_context.verification_result.get("verification_status", "UNKNOWN")

        payload = {
            "title": f"INCIDENT #{incident_context.incident_id}",
            "device": incident_context.device_id,
            "device_type": incident_context.device_type,
            "issue": f"Isu layanan {incident_context.service} ({incident_context.severity})",
            "osi_layer": f"Primary: {incident_context.osi_layers[0] if incident_context.osi_layers else 'L7_APPLICATION'}",
            "evidence": evidence_checks,
            "root_cause_probability": f"{round(incident_context.confidence * 100, 1)}%",
            "proposed_action": selected_action_name,
            "status": incident_context.current_state,
            "hitl_status": incident_context.hitl_status,
            "verification_result": verif_summary,
            "escalation_level": f"Level {incident_context.escalation_level}"
        }

        logger.info(f"[AgentTrayFormatter] Formatted payload for incident {incident_context.incident_id}")
        return payload
