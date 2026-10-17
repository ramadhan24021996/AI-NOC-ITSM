"""
SERVER.jarvis.personas - Persona Registry
Configurable persona registry for Jarvis presentation formatting (NOC Engineer, Manager, Executive).
P7 Update: Tambah command_acknowledgment dan format_action_confirmation untuk semua persona.
"""
from dataclasses import dataclass
from typing import Dict, List, Optional


@dataclass
class PersonaConfig:
    persona_id: str
    name: str
    tone: str            # e.g. "technical", "casual", "concise", "executive"
    greeting: str
    closing: str
    detail_level: str    # "high", "medium", "summary_only"
    # P7: Command Acknowledgment templates
    acknowledge_query: str = ""        # Saat menerima perintah query
    acknowledge_remediate: str = ""    # Saat akan eksekusi aksi
    acknowledge_hitl: str = ""         # Saat aksi masuk HITL queue
    acknowledge_remote: str = ""       # Saat buka remote access
    acknowledge_success: str = ""      # Saat eksekusi berhasil
    acknowledge_failed: str = ""       # Saat eksekusi gagal


class PersonaRegistry:
    """Manages presentation personas dynamically without code modifications."""

    def __init__(self):
        self._personas: Dict[str, PersonaConfig] = {}
        self._register_default_personas()

    def _register_default_personas(self) -> None:
        # ── Senior NOC Engineer Persona (Professional Infrastructure Copilot) ──
        self.register(PersonaConfig(
            persona_id="noc_engineer",
            name="Jarvis Senior NOC Engineer",
            tone="professional",
            greeting="Siap! JARVIS Copilot di sini, standby amankan infrastruktur dan server.",
            closing="Apakah ada node lain yang perlu diinspeksi atau dikonfigurasi?",
            detail_level="high",
            acknowledge_query="Siap, memproses penarikan telemetri real-time {target}...",
            acknowledge_remediate="Memulai eksekusi aksi remediasi: {action} pada {target}.\nRisk Level: {risk_level}.",
            acknowledge_hitl="⚠️ Perhatian: Aksi {action} pada {target} memerlukan persetujuan (HITL).\nRisk Level: {risk_level}.\nQueue ID: {hitl_queue_id}.\nKetik 'approve {incident_id}' untuk melanjutkan.",
            acknowledge_remote="Membuka koneksi remote {tool} ke {host} ({target})...",
            acknowledge_success="✅ Eksekusi {action} berhasil. {details}",
            acknowledge_failed="❌ Eksekusi {action} mengalami kendala: {reason}\nSaran: {suggestion}"
        ))

        # ── Senior Tech Wizard Persona ─────────────────────────────────────────
        self.register(PersonaConfig(
            persona_id="senior_engineer",
            name="Jarvis Senior Tech Wizard",
            tone="casual_witty_senior",
            greeting="Siap Senior! JARVIS standby. Server & jaringan terpantau aman.",
            closing="Aman bosku, mau inspeksi node yang mana lagi?",
            detail_level="high",
            acknowledge_query="Siap Senior, lagi inspeksi telemetri {target}...",
            acknowledge_remediate="Langsung dieksekusi Senior: {action} pada {target}. Risk: {risk_level}.",
            acknowledge_hitl="⚠️ Perlu persetujuan Senior! {action} pada {target} berisiko {risk_level}. Queue: {hitl_queue_id}.",
            acknowledge_remote="Membuka sesi remote {tool} → {host}...",
            acknowledge_success="✅ Beres Senior! {action} sukses. {details}",
            acknowledge_failed="❌ Perhatian Senior! {action} mengalami kendala: {reason}"
        ))

        # ── Incident Manager Persona (Ringkas) ────────────────────────────────
        self.register(PersonaConfig(
            persona_id="incident_manager",
            name="Jarvis Manager Assistant",
            tone="concise",
            greeting="Selamat datang Manager, berikut ringkasan status insiden.",
            closing="Laporan telah disinkronkan ke dashboard.",
            detail_level="medium",
            acknowledge_query="Mengambil data {target}.",
            acknowledge_remediate="⚡ Aksi: {action} pada {target}. Risk: {risk_level}. {countdown}...",
            acknowledge_hitl="⏳ Aksi tertahan — Risk {risk_level}. Queue: {hitl_queue_id}\nMenunggu approval. Ketik 'approve {incident_id}'.",
            acknowledge_remote="Membuka {tool} → {host}...",
            acknowledge_success="✅ Berhasil: {action}. {details}",
            acknowledge_failed="❌ Gagal: {action}. {reason}"
        ))

        # ── Executive Persona (Summary Only) ─────────────────────────────────
        self.register(PersonaConfig(
            persona_id="executive",
            name="Jarvis Executive Brief",
            tone="executive",
            greeting="Berikut ringkasan eksekutif ketersediaan jaringan.",
            closing="Semua SLA dalam batas aman.",
            detail_level="summary_only",
            acknowledge_query="Menyiapkan laporan {target}.",
            acknowledge_remediate="Tindakan {action} dijadwalkan. Risk: {risk_level}.",
            acknowledge_hitl="Persetujuan diperlukan untuk tindakan {action}. Tim NOC telah dinotifikasi.",
            acknowledge_remote="Akses remote ke {target} sedang dibuka.",
            acknowledge_success="✅ {action} selesai.",
            acknowledge_failed="⚠️ Tindakan {action} tidak berhasil. Tim NOC menangani."
        ))

    def register(self, persona: PersonaConfig) -> None:
        self._personas[persona.persona_id] = persona

    def get(self, persona_id: str) -> Optional[PersonaConfig]:
        return self._personas.get(persona_id)

    def list_ids(self) -> List[str]:
        return list(self._personas.keys())

    def format_acknowledgment(
        self,
        persona_id: str,
        ack_type: str,
        **kwargs
    ) -> str:
        """
        P7: Format command acknowledgment untuk persona yang aktif.

        Args:
            persona_id: ID persona aktif.
            ack_type: Jenis acknowledgment (query/remediate/hitl/remote/success/failed).
            **kwargs: Template variables (action, target, risk_level, hitl_queue_id, dll).

        Returns:
            String acknowledgment yang sudah diformat.
        """
        persona = self.get(persona_id)
        if not persona:
            return ""

        template_map = {
            "query":     persona.acknowledge_query,
            "remediate": persona.acknowledge_remediate,
            "hitl":      persona.acknowledge_hitl,
            "remote":    persona.acknowledge_remote,
            "success":   persona.acknowledge_success,
            "failed":    persona.acknowledge_failed,
        }

        template = template_map.get(ack_type, "")
        if not template:
            return ""

        try:
            return template.format_map(_SafeDict(kwargs))
        except Exception:
            return template


class _SafeDict(dict):
    """Format dict yang aman — jika key tidak ada, biarkan placeholder."""
    def __missing__(self, key):
        return f"{{{key}}}"
