"""
SERVER.jarvis.conversation — Conversation Opening Engine
=========================================================
Generates dynamic, contextual opening greetings for Jarvis Voice & Presentation sessions.
Factors in:
 - Time of day (Morning, Afternoon, Evening, Night)
 - Operator/User Identity
 - Active incident status & system health summary
 - Active Persona formatting (NOC Engineer, Incident Manager, Executive)
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from SERVER.jarvis.personas.persona_registry import PersonaRegistry, PersonaConfig

logger = logging.getLogger("jarvis.conversation.opening_engine")


class ConversationOpeningEngine:
    """Engine for generating contextual session opening greetings."""

    def __init__(self, persona_registry: Optional[PersonaRegistry] = None):
        self.persona_registry = persona_registry or PersonaRegistry()

    def _get_time_salutation(self, hour: Optional[int] = None) -> str:
        """Returns time-appropriate greeting in Indonesian."""
        if hour is None:
            hour = datetime.now().hour

        if 4 <= hour < 11:
            return "Selamat pagi"
        elif 11 <= hour < 15:
            return "Selamat siang"
        elif 15 <= hour < 18:
            return "Selamat sore"
        else:
            return "Selamat malam"

    def generate_opening(
        self,
        session_id: str,
        operator_name: str = "Operator",
        persona_id: str = "noc_engineer",
        system_status: Optional[Dict[str, Any]] = None,
        hour_override: Optional[int] = None,
    ) -> str:
        """
        Generates contextual opening statement.

        Args:
            session_id: Session identifier.
            operator_name: Name of the active user/operator.
            persona_id: Target persona ID ('noc_engineer', 'incident_manager', 'executive').
            system_status: Optional dict with system metrics (e.g. {'critical_incidents': 2, 'open_alerts': 5}).
            hour_override: Optional hour for testing (0-23).

        Returns:
            Opening greeting string formatted according to active persona.
        """
        salutation = self._get_time_salutation(hour_override)
        persona = self.persona_registry.get(persona_id) or self.persona_registry.get("noc_engineer")

        if persona is None:
            # Type safety fallback if persona registry is completely uninitialized
            persona = PersonaConfig(
                persona_id="noc_engineer",
                name="Jarvis NOC Specialist",
                tone="technical",
                greeting="Halo, Jarvis siap membantu diagnosa sistem.",
                closing="Siap menerima instruksi.",
                detail_level="high",
            )

        name_str = f" {operator_name}" if operator_name and operator_name.lower() != "operator" else ""
        greeting_prefix = f"{salutation}{name_str}."

        # Analyze system status if provided
        status_addon = ""
        if system_status:
            crit_count = system_status.get("critical_incidents", 0)
            open_count = system_status.get("open_alerts", 0)

            if crit_count > 0:
                if persona.detail_level == "summary_only":
                    status_addon = f" Terdapat {crit_count} insiden kritis yang membutuhkan perhatian Anda."
                elif persona.detail_level == "medium":
                    status_addon = f" Perhatian: Terdeteksi {crit_count} insiden CRITICAL aktif dan {open_count} alert terbuka."
                else:  # high / technical
                    target_host = system_status.get("primary_target", "server utama")
                    status_addon = f" ⚠️ ALERT: Terdeteksi {crit_count} insiden CRITICAL pada {target_host}. Sistem monitoring siap menerima instruksi diagnosa."
            else:
                if persona.detail_level == "summary_only":
                    status_addon = " Seluruh layanan beroperasi secara optimal."
                else:
                    status_addon = " Seluruh server & infrastruktur dalam kondisi STABLE. Tidak ada insiden kritis."

        full_opening = f"{greeting_prefix} {persona.greeting}{status_addon}"
        logger.info(f"[OpeningEngine] Generated opening for session '{session_id[:8]}' ({persona_id}): {full_opening[:60]}...")
        return full_opening.strip()
