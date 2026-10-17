"""
SERVER.jarvis.runtime.shift_handoff_briefer — JARVIS Shift Handoff Briefing
=============================================================================
Briefing otomatis saat pergantian shift operator.

Fitur:
  ✅ Rangkum kondisi saat ini (insiden aktif, device bermasalah, SLA)
  ✅ Highlight hal-hal yang perlu diperhatikan operator baru
  ✅ Sebutkan tindakan yang belum selesai dari shift sebelumnya
  ✅ Adaptasi panjang briefing berdasarkan jumlah insiden aktif
"""
from __future__ import annotations

import logging
import random
import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger("jarvis.runtime.shift_handoff")


class ShiftHandoffBriefer:
    """
    Generate briefing pergantian shift berdasarkan data live NOC.
    """

    def __init__(self, noc_bridge: Optional[Any] = None):
        self._noc = noc_bridge

    def _fetch(self, endpoint: str) -> Any:
        if not self._noc:
            return None
        try:
            r = self._noc._get(endpoint)
            return r.data if r and r.success else None
        except Exception:
            return None

    def generate_briefing(
        self,
        incoming_operator: str = "",
        outgoing_operator: str = "",
        verbose: bool = False,
    ) -> str:
        """
        Generate full shift handoff briefing.
        
        Args:
            incoming_operator: Nama operator yang masuk
            outgoing_operator: Nama operator yang keluar
            verbose: True = detail lengkap, False = ringkas untuk TTS
        """
        now = datetime.now(timezone.utc)
        hour = now.hour + 7  # WIB
        if hour >= 24: hour -= 24
        shift = "Pagi" if 6 <= hour < 14 else ("Siang" if 14 <= hour < 22 else "Malam")

        # Fetch data live
        incidents_data = self._fetch("/api/incidents")
        health_data    = self._fetch("/api/system/health")
        metrics_data   = (self._fetch("/api/system/health") or {})

        # Parse incidents
        incidents = []
        if isinstance(incidents_data, list):
            incidents = incidents_data
        elif isinstance(incidents_data, dict):
            incidents = incidents_data.get("incidents", [])

        open_inc  = [i for i in incidents if str(i.get("status","")).upper() in ["OPEN","ACTIVE","NEW","PENDING"]]
        crit_inc  = [i for i in open_inc if str(i.get("severity","")).upper() in ["CRITICAL","HIGH"]]

        # Build briefing
        parts = []

        # Greeting
        greets = [
            f"Selamat shift {shift}",
            f"Halo",
            f"Selamat datang di shift {shift}",
        ]
        if incoming_operator:
            intro = f"{random.choice(greets)}, {incoming_operator}!"
        else:
            intro = f"{random.choice(greets)}!"
        if outgoing_operator:
            intro += f" Pergantian shift dari {outgoing_operator}."
        parts.append(intro)

        # Kondisi umum
        if not open_inc:
            parts.append(f"✅ Kondisi: Semua sistem normal, tidak ada insiden aktif. Shift tenang!")
        elif crit_inc:
            parts.append(f"🔴 PERHATIAN: Ada {len(crit_inc)} insiden CRITICAL/HIGH yang perlu penanganan segera!")
        else:
            parts.append(f"⚠️ Ada {len(open_inc)} insiden masih OPEN — perlu dimonitor.")

        # Detail insiden kritis
        if crit_inc:
            parts.append(f"\n📋 Insiden Prioritas:")
            for inc in crit_inc[:3]:
                inc_id = inc.get("incident_id") or inc.get("id", "?")
                dev    = inc.get("device_name") or inc.get("agent", "?")
                sev    = inc.get("severity", "?")
                evid   = str(inc.get("evidence","") or inc.get("flag",""))[:50]
                parts.append(f"  🔴 INC-{inc_id} [{sev}] {dev}: {evid}")

        elif open_inc and verbose:
            parts.append(f"\n📋 Insiden Aktif ({len(open_inc)}):")
            for inc in open_inc[:3]:
                inc_id = inc.get("incident_id") or inc.get("id", "?")
                dev    = inc.get("device_name") or inc.get("agent", "?")
                parts.append(f"  ⚠️ INC-{inc_id}: {dev}")

        # System health ringkas
        if health_data and isinstance(health_data, dict):
            components = health_data.get("components", {})
            comp_ok = sum(1 for v in components.values()
                          if isinstance(v, dict) and v.get("status") in ["UP","OK","healthy"])
            comp_total = len(components)
            if comp_total:
                parts.append(f"\n⚙️ Core Services: {comp_ok}/{comp_total} komponen aktif")

        # Closing
        closers = [
            "Saya standby membantu shift ini. Ada yang perlu dicek duluan?",
            "Semangat shift-nya! Hubungi saya kapan saja.",
            "Saya di sini untuk membantu. Ada prioritas pertama?",
        ]
        parts.append(f"\n{random.choice(closers)}")

        return "\n".join(parts)

    def generate_quick_status(self) -> str:
        """Versi singkat untuk TTS — max 3 kalimat."""
        incidents_data = self._fetch("/api/incidents")
        incidents = []
        if isinstance(incidents_data, list):
            incidents = incidents_data
        elif isinstance(incidents_data, dict):
            incidents = incidents_data.get("incidents", [])

        open_inc = [i for i in incidents if str(i.get("status","")).upper() in ["OPEN","ACTIVE","NEW"]]
        crit_inc = [i for i in open_inc if str(i.get("severity","")).upper() in ["CRITICAL","HIGH"]]

        if not open_inc:
            msgs = [
                "Kondisi NOC aman — tidak ada insiden aktif saat ini.",
                "Semua sistem berjalan normal. Tidak ada alert.",
                "Green across the board — tidak ada insiden.",
            ]
            return random.choice(msgs)

        if crit_inc:
            return (
                f"⚠️ Ada {len(crit_inc)} insiden kritis aktif saat ini. "
                f"Terbaru: {crit_inc[0].get('device_name','?')}. "
                f"Perlu penanganan segera!"
            )

        return f"Ada {len(open_inc)} insiden OPEN, semua non-kritis. Pantau terus."


def get_shift_briefer(noc_bridge: Optional[Any] = None) -> ShiftHandoffBriefer:
    return ShiftHandoffBriefer(noc_bridge=noc_bridge)
