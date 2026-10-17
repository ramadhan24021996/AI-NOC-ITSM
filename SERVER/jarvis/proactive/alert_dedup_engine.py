"""
SERVER.jarvis.proactive.alert_dedup_engine — Alert Deduplication & Fatigue Prevention
=======================================================================================
Mencegah operator dibanjiri alert yang sama berulang kali.

Masalah sekarang:
  "Printer kasir-3 offline" dibunyikan 12x dalam 1 jam → operator fatigue → mulai diabaikan

Solusi:
  ✅ Smart dedup: alert yang sama hanya 1x dalam cooldown window
  ✅ Eskalasi progressif: jika tidak ditangani, intensitas naik (bukan frekuensi)
  ✅ Context-aware: bedakan "baru terjadi" vs "masih berlangsung"
  ✅ Mood tracking: banyak alert kritis → JARVIS tahu operator sedang stres

Eskalasi progressif:
  Alert ke-1 (T+0):    Suara normal — "Printer kasir-3 offline"
  Alert ke-2 (T+15):   Silent — sudah diketahui, tidak berisik
  Alert ke-3 (T+30):   Suara — "Kasir-3 masih offline, sudah 30 menit"
  Alert ke-4 (T+60):   Eskalasi — "Kasir-3 offline 1 jam! Butuh tindakan segera"
  Alert ke-5 (T+120):  Eskalasi kritis — Kirim notifikasi Telegram
"""
from __future__ import annotations

import hashlib
import logging
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Set, Tuple

logger = logging.getLogger("jarvis.proactive.alert_dedup")


# ─── Constants ────────────────────────────────────────────────────────────────
DEDUP_WINDOW_SECONDS   = 900    # 15 menit — alert sama tidak dibunyikan ulang
ESCALATION_THRESHOLDS  = [15, 30, 60, 120]  # menit sebelum eskalasi berikutnya
MAX_STRESS_LEVEL       = 5      # Jumlah alert kritis sebelum mood = STRESSED


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class AlertRecord:
    """Record satu alert yang sudah dibunyikan."""
    alert_key: str
    device: str
    alert_type: str
    severity: str
    first_seen: float = field(default_factory=time.time)
    last_announced: float = field(default_factory=time.time)
    announce_count: int = 1
    is_acknowledged: bool = False
    escalation_level: int = 0   # 0=normal, 1=reminder, 2=escalate, 3=critical


@dataclass
class AlertDecision:
    """Keputusan apakah alert harus dibunyikan dan bagaimana."""
    should_announce: bool
    escalation_level: int = 0
    message_override: str = ""      # Jika perlu pesan khusus (eskalasi)
    reason: str = ""                # Alasan suppress/announce
    send_telegram: bool = False     # Apakah perlu kirim Telegram juga


# ─── Mood Tracker ─────────────────────────────────────────────────────────────

class OperatorMoodTracker:
    """
    Lacak tingkat stress operator berdasarkan volume alert kritis.
    Digunakan oleh JARVIS untuk menyesuaikan gaya komunikasi.
    """

    def __init__(self):
        self._critical_alerts: List[float] = []  # Timestamps alert kritis
        self._window = 3600  # 1 jam lookback

    def record_critical_alert(self) -> None:
        now = time.time()
        self._critical_alerts.append(now)
        # Bersihkan yang sudah di luar window
        self._critical_alerts = [t for t in self._critical_alerts if now - t <= self._window]

    def get_stress_level(self) -> str:
        """Return CALM | BUSY | STRESSED | OVERWHELMED"""
        count = len(self._critical_alerts)
        if count >= MAX_STRESS_LEVEL * 2: return "OVERWHELMED"
        if count >= MAX_STRESS_LEVEL:     return "STRESSED"
        if count >= 2:                    return "BUSY"
        return "CALM"

    def get_mood_prefix(self) -> str:
        """Frasa pembuka yang disesuaikan mood operator."""
        mood = self.get_stress_level()
        prefixes = {
            "CALM":        ["Halo! ", "Baik, ", "Siap, "],
            "BUSY":        ["Perhatian: ", "Update: ", ""],
            "STRESSED":    ["Langsung saja: ", "Singkat: ", "Prioritas: "],
            "OVERWHELMED": ["⚠️ PENTING: ", "🔴 SEGERA: ", "Fokus: "],
        }
        import random
        return random.choice(prefixes.get(mood, [""]))

    def get_response_style(self) -> Dict[str, Any]:
        """Return parameter gaya respons berdasarkan mood."""
        mood = self.get_stress_level()
        styles = {
            "CALM":        {"max_words": 200, "use_emoji": True,  "brevity": "NORMAL"},
            "BUSY":        {"max_words": 100, "use_emoji": True,  "brevity": "SHORT"},
            "STRESSED":    {"max_words": 60,  "use_emoji": False, "brevity": "VERY_SHORT"},
            "OVERWHELMED": {"max_words": 30,  "use_emoji": False, "brevity": "MINIMAL"},
        }
        return styles.get(mood, styles["CALM"])


# ─── Alert Dedup Engine ───────────────────────────────────────────────────────

class AlertDedupEngine:
    """
    Smart alert deduplication dan eskalasi progressif untuk JARVIS.
    
    Cegah alert fatigue dengan:
    1. Dedup window — alert sama silent selama N menit
    2. Eskalasi progressif — pesan makin urgent jika tidak ditangani
    3. Mood tracking — JARVIS tahu kapan operator sedang stres
    """

    def __init__(self):
        self._records: Dict[str, AlertRecord] = {}
        self._mood = OperatorMoodTracker()

    def _make_key(self, device: str, alert_type: str) -> str:
        """Buat unique key untuk deduplication."""
        raw = f"{device.upper().strip()}:{alert_type.upper().strip()}"
        return hashlib.md5(raw.encode()).hexdigest()[:12]

    def _get_escalation_message(self, record: AlertRecord, level: int) -> str:
        """Buat pesan eskalasi yang progressif."""
        duration_min = int((time.time() - record.first_seen) / 60)
        device = record.device

        if level == 1:
            msgs = [
                f"{device} masih bermasalah setelah {duration_min} menit.",
                f"Reminder: {device} belum resolved ({duration_min} menit).",
                f"Update: masalah di {device} masih berlangsung.",
            ]
        elif level == 2:
            msgs = [
                f"⚠️ {device} belum tertangani selama {duration_min} menit! Perlu tindakan?",
                f"⚠️ Perhatian! {device} masih bermasalah — sudah {duration_min} menit.",
            ]
        elif level >= 3:
            msgs = [
                f"🔴 ESKALASI! {device} offline {duration_min} menit tanpa penanganan. Butuh L2!",
                f"🔴 KRITIS: {device} sudah {duration_min} menit bermasalah. Eskalasi diperlukan.",
            ]
        else:
            return ""

        import random
        return random.choice(msgs)

    def should_announce(
        self,
        device: str,
        alert_type: str,
        severity: str = "MEDIUM",
        force: bool = False,
    ) -> AlertDecision:
        """
        Tentukan apakah alert harus dibunyikan.

        Args:
            device: Nama device yang bermasalah
            alert_type: Tipe alert (e.g., "PRINTER_OFFLINE", "CPU_HIGH")
            severity: CRITICAL | HIGH | MEDIUM | LOW
            force: Paksa announce (untuk alert baru yang benar-benar fresh)

        Returns:
            AlertDecision dengan instruksi untuk ProactiveAnnouncer
        """
        key = self._make_key(device, alert_type)
        now = time.time()

        # Alert baru — belum pernah ada
        if key not in self._records or force:
            record = AlertRecord(
                alert_key=key,
                device=device,
                alert_type=alert_type,
                severity=severity.upper(),
            )
            self._records[key] = record
            if severity.upper() in ["CRITICAL", "HIGH"]:
                self._mood.record_critical_alert()
            return AlertDecision(should_announce=True, reason="Alert baru")

        record = self._records[key]

        # Sudah di-acknowledge operator → suppress
        if record.is_acknowledged:
            return AlertDecision(should_announce=False, reason="Sudah di-acknowledge oleh operator")

        elapsed_min = (now - record.last_announced) / 60
        total_min   = (now - record.first_seen) / 60

        # Cek apakah sudah melewati threshold eskalasi
        for i, threshold_min in enumerate(ESCALATION_THRESHOLDS):
            if total_min >= threshold_min and record.escalation_level <= i:
                record.escalation_level = i + 1
                record.last_announced = now
                record.announce_count += 1
                self._records[key] = record

                msg = self._get_escalation_message(record, record.escalation_level)
                send_tg = record.escalation_level >= 3  # Level 3+ → kirim Telegram

                return AlertDecision(
                    should_announce=True,
                    escalation_level=record.escalation_level,
                    message_override=msg,
                    reason=f"Eskalasi level {record.escalation_level} setelah {threshold_min} menit",
                    send_telegram=send_tg,
                )

        # Masih dalam dedup window — suppress
        elapsed_since_last = now - record.last_announced
        if elapsed_since_last < DEDUP_WINDOW_SECONDS:
            remaining = int((DEDUP_WINDOW_SECONDS - elapsed_since_last) / 60)
            return AlertDecision(
                should_announce=False,
                reason=f"Dedup window aktif — {remaining} menit lagi",
            )

        # Update dan announce
        record.last_announced = now
        record.announce_count += 1
        self._records[key] = record
        return AlertDecision(should_announce=True, reason="Window expired — announce ulang")

    def acknowledge(self, device: str, alert_type: str) -> bool:
        """Tandai alert sebagai sudah ditangani operator."""
        key = self._make_key(device, alert_type)
        if key in self._records:
            self._records[key].is_acknowledged = True
            logger.info("[AlertDedup] Acknowledged: %s:%s", device, alert_type)
            return True
        return False

    def clear_resolved(self, device: str, alert_type: str) -> bool:
        """Hapus record saat insiden resolved — siap untuk alert baru."""
        key = self._make_key(device, alert_type)
        if key in self._records:
            del self._records[key]
            return True
        return False

    def get_active_alerts_summary(self) -> str:
        """Ringkasan semua alert aktif untuk status briefing."""
        if not self._records:
            return "✅ Tidak ada alert aktif dalam dedup registry."

        now = time.time()
        lines = [f"🔔 ACTIVE ALERT REGISTRY ({len(self._records)} alert):"]
        for rec in sorted(self._records.values(), key=lambda r: r.first_seen, reverse=True)[:5]:
            age_min = int((now - rec.first_seen) / 60)
            ack = "✅ ACK" if rec.is_acknowledged else f"⏱️ {age_min}m"
            lines.append(f"  • {rec.device} [{rec.alert_type}] L{rec.escalation_level} | {ack} | {rec.announce_count}x announced")

        lines.append(f"\n👤 Operator mood: {self._mood.get_stress_level()}")
        return "\n".join(lines)

    @property
    def mood_tracker(self) -> OperatorMoodTracker:
        """Expose mood tracker untuk adaptive communication."""
        return self._mood


# ─── Singleton ────────────────────────────────────────────────────────────────
_instance: Optional[AlertDedupEngine] = None

def get_alert_dedup_engine() -> AlertDedupEngine:
    global _instance
    if _instance is None:
        _instance = AlertDedupEngine()
    return _instance
