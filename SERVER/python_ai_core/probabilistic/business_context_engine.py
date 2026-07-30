"""
ENTERPRISE BUSINESS CONTEXT ENGINE
Provides multi-dimensional operational context (Business Calendar, Maintenance Windows, Software Versions, Event Types)
to dynamically scale DBN transition matrices beyond static time-of-day multipliers.
"""

import datetime
import logging
from typing import Dict, Any, Optional

logger = logging.getLogger("BUSINESS_CONTEXT_ENGINE")

class BusinessContextEngine:
    """
    Engine Konteks Operasional Enterprise.
    Mengkombinasikan Kalender Bisnis, Maintenance Window, dan Event Type.
    """

    def __init__(self):
        # Default Event Calendar Table
        self.special_events = {
            "PAYROLL_DAY": [25, 26, 27, 28, 29, 30], # Tanggal penggajian
            "HOLIDAY_SALE": ["11-11", "12-12", "01-01"], # Event diskon besar
            "STORE_OPENING_PEAK": list(range(8, 12)) # Peak jam buka toko
        }

    def get_current_operational_context(
        self,
        device_id: str,
        software_version: str = "v2.4.1",
        is_maintenance_active: bool = False,
        event_override: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Mengembalikan Konteks Operasional Lengkap untuk penyesuaian DBN.
        """
        now = datetime.datetime.now()
        current_hour = now.hour
        current_day = now.day
        date_str = now.strftime("%m-%d")

        # 1. Tentukan Event Type
        event_type = "NORMAL_OPERATION"
        if event_override:
            event_type = event_override
        elif date_str in self.special_events["HOLIDAY_SALE"]:
            event_type = "HOLIDAY_SALE_MEGA_PEAK"
        elif current_day in self.special_events["PAYROLL_DAY"]:
            event_type = "PAYROLL_DAY_TRAFFIC_SPIKE"
        elif current_hour in self.special_events["STORE_OPENING_PEAK"]:
            event_type = "STORE_OPENING_PEAK"

        # 2. Multiplier Penyesuaian Anomali (Risk Scale Factor)
        risk_scale = 1.0
        if is_maintenance_active:
            risk_scale = 0.50 # Selama maintenance window, anomali dianggap terkontrol
        elif event_type == "HOLIDAY_SALE_MEGA_PEAK":
            risk_scale = 1.80 # 1.8x peka saat mega sale!
        elif event_type == "PAYROLL_DAY_TRAFFIC_SPIKE":
            risk_scale = 1.45
        elif event_type == "STORE_OPENING_PEAK":
            risk_scale = 1.25

        # 3. Penyesuaian Versi Software (Canary / Legacy vs Stable)
        if "canary" in software_version.lower() or "beta" in software_version.lower():
            risk_scale *= 1.30 # Build canary lebih rawan anomali

        context_res = {
            "device_id": device_id,
            "software_version": software_version,
            "is_maintenance_active": is_maintenance_active,
            "event_type": event_type,
            "current_hour": current_hour,
            "risk_scale_factor": round(risk_scale, 2),
            "context_reasoning": (
                f"Context '{event_type}' (Version={software_version}, Maintenance={is_maintenance_active}). "
                f"DBN Risk Scale Factor set to {risk_scale:.2f}x."
            )
        }

        logger.info(f"[BUSINESS CONTEXT] Device '{device_id}': {context_res['context_reasoning']}")
        return context_res


# Self-Test Business Context Engine Demo
if __name__ == "__main__":
    engine = BusinessContextEngine()

    print("=== ENTERPRISE BUSINESS CONTEXT ENGINE DEMO ===")
    
    c1 = engine.get_current_operational_context("POS-KASIR-01", "v2.5.0-canary", False, "HOLIDAY_SALE")
    c2 = engine.get_current_operational_context("DB-PROD-01", "v2.4.1", True)

    print(f"📌 Context 1 (POS Canary on Sale): Scale = {c1['risk_scale_factor']}x | Event = {c1['event_type']}")
    print(f"📌 Context 2 (DB on Maintenance) : Scale = {c2['risk_scale_factor']}x | Event = {c2['event_type']}")
