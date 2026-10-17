"""
SERVER.jarvis.runtime.startup_reporter — JARVIS Startup Dashboard Reporter
==========================================================================
P5 Implementation: Laporan otomatis saat JARVIS pertama kali login ke dashboard.
Membaca semua status live dan menyajikan ringkasan dalam format yang sesuai
dengan persona yang aktif.

Dipanggil oleh JarvisPresentationRuntime pada sesi baru (saat tidak ada histori).
"""
import logging
from typing import Dict, Any, Optional
from SERVER.jarvis.noc.noc_bridge import JarvisNOCBridge
from SERVER.jarvis.personas.persona_registry import PersonaConfig

logger = logging.getLogger("jarvis.runtime.startup_reporter")


class JarvisStartupReporter:
    """
    P5 — JARVIS Startup Dashboard Reporter.
    Menghasilkan laporan status sistem saat operator login.

    Contoh output (persona = noc_engineer):
    ----------------------------------------
    Halo Engineer, Jarvis siap membantu diagnosa jaringan.

    📊 STATUS SISTEM (Live):
    ├── Health Score : 94/100 [HEALTHY]
    ├── CPU          : 23.4% ✅
    ├── RAM          : 61.2% ✅
    └── Disk         : 47.8% ✅

    🌐 SITE STATUS:
    ├── Jakarta  : ONLINE (12ms) ✅
    └── Bandung  : DEGRADED ⚠️

    ⚡ HITL QUEUE: 2 aksi menunggu approval!
    Silakan konfirmasi jika butuh investigasi lanjutan.
    """

    def __init__(self, noc_bridge: Optional[JarvisNOCBridge] = None):
        self.bridge = noc_bridge or JarvisNOCBridge()

    def generate_startup_report(self, persona: Optional[PersonaConfig] = None) -> str:
        """
        Hasilkan laporan startup yang disesuaikan dengan persona.

        Args:
            persona: PersonaConfig aktif (noc_engineer/incident_manager/executive).

        Returns:
            String laporan yang siap ditampilkan/diucapkan oleh JARVIS.
        """
        detail_level = persona.detail_level if persona else "high"
        greeting = persona.greeting if persona else "Jarvis siap."

        sections: list[str] = [greeting, ""]

        # Cek apakah dashboard dapat dijangkau
        if not self.bridge.is_dashboard_reachable():
            logger.warning("[StartupReporter] Dashboard tidak dapat dijangkau.")
            sections.append(
                "⚠️ Dashboard server tidak dapat dijangkau saat ini. "
                "Jarvis beroperasi dalam mode offline."
            )
            return "\n".join(sections)

        # ── Blok 1: System Health (semua persona) ──────────────────────────
        health_resp = self.bridge.get_system_health()
        if health_resp.success:
            score = health_resp.data.get("health_score", "?")
            status = health_resp.data.get("status", "UNKNOWN")
            status_icon = {"HEALTHY": "✅", "DEGRADED": "⚠️", "CRITICAL": "🔴"}.get(status, "❓")
            sections.append(f"📊 STATUS SISTEM (Live):")
            sections.append(f"├── Health Score : {score}/100 [{status}] {status_icon}")

            if detail_level == "high":
                # CPU/RAM/Disk
                metrics_resp = self.bridge.get_host_metrics()
                if metrics_resp.success:
                    cpu = metrics_resp.data.get("cpu_pct", "?")
                    ram = metrics_resp.data.get("ram_pct", "?")
                    disk = metrics_resp.data.get("disk_pct", "?")

                    def _icon(v):
                        try:
                            return "⚠️" if float(v) > 80 else ("🔴" if float(v) > 90 else "✅")
                        except Exception:
                            return "❓"

                    sections.append(f"├── CPU          : {cpu}% {_icon(cpu)}")
                    sections.append(f"├── RAM          : {ram}% {_icon(ram)}")
                    sections.append(f"└── Disk         : {disk}% {_icon(disk)}")
                sections.append("")

        # ── Blok 2: Site Status ────────────────────────────────────────────
        if detail_level in ("high", "medium"):
            sites_resp = self.bridge.ping_sites()
            if sites_resp.success:
                sites = sites_resp.data if isinstance(sites_resp.data, list) else []
                if sites:
                    sections.append("🌐 SITE STATUS:")
                    online_sites = [s for s in sites if s.get("online", False)]
                    offline_sites = [s for s in sites if not s.get("online", False)]
                    for s in online_sites[:5]:  # Max 5 entries
                        name = s.get("site_name", s.get("site_id", "?"))
                        latency = s.get("latency_ms", "?")
                        sections.append(f"├── {name:<12}: ONLINE ({latency}ms) ✅")
                    for s in offline_sites:
                        name = s.get("site_name", s.get("site_id", "?"))
                        sections.append(f"├── {name:<12}: ❌ OFFLINE")
                    sections.append("")

        # ── Blok 3: SLA Summary (executive dan manager) ───────────────────
        if detail_level in ("medium", "summary_only"):
            sla_resp = self.bridge.get_sla_compliance()
            if sla_resp.success and sla_resp.summary:
                sections.append(f"📈 {sla_resp.summary}")
                sections.append("")

        # ── Blok 4: HITL Queue Alert ──────────────────────────────────────
        queues_resp = self.bridge.get_system_queues()
        if queues_resp.success and queues_resp.requires_followup:
            sections.append(f"⚡ HITL QUEUE: {queues_resp.summary}")
            sections.append("")

        # ── Blok 5: Printer Status (noc_engineer only) ────────────────────
        if detail_level == "high":
            printer_resp = self.bridge.get_printers_live()
            if printer_resp.success and printer_resp.summary:
                sections.append(f"🖨️  {printer_resp.summary}")
                sections.append("")

        # ── Blok 6: n8n Status (high + medium) ───────────────────────────
        if detail_level in ("high", "medium"):
            n8n_resp = self.bridge.get_n8n_health()
            if n8n_resp.success and n8n_resp.summary:
                sections.append(f"⚙️  {n8n_resp.summary}")

        # Closing
        closing = persona.closing if persona else "Siap menerima perintah."
        sections.extend(["", closing])

        return "\n".join(sections)

    def generate_brief_status(self) -> str:
        """Versi ringkas untuk respons cepat."""
        health_resp = self.bridge.get_system_health()
        metrics_resp = self.bridge.get_host_metrics()
        if not health_resp.success:
            return "Dashboard tidak dapat dijangkau."
        score = health_resp.data.get("health_score", "?")
        status = health_resp.data.get("status", "UNKNOWN")
        metrics_summary = metrics_resp.summary if metrics_resp.success else "Metrics N/A"
        return f"Health: {score}/100 [{status}] | {metrics_summary}"
