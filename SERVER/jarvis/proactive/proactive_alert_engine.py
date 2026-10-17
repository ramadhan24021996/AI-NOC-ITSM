"""
SERVER.jarvis.proactive.proactive_alert_engine
================================================
Production-Ready Proactive Telemetry Monitoring Daemon Engine V2.

Mengintegrasikan NOCVoiceIntelligenceEngine (V2) dengan Speak-or-Silent Decision Gate,
Incident Lifecycle State, Narrative Fact Ledger, dan Telemetri Real-Time.
"""
import time
import logging
import threading
from typing import Dict, Any, Optional
from SERVER.jarvis.proactive.noc_voice_intelligence import get_voice_intelligence_engine_v22, NOCVoiceIntelligenceEngineV22
from SERVER.jarvis.proactive.jarvis_proactive_announcer import get_announcer

logger = logging.getLogger("jarvis.proactive.engine")


class ProactiveAlertEngine:
    """
    Background Telemetry Polling Daemon Engine V2.2 (Production Proven Forensic Architecture).
    Memantau telemetri NOC secara berkala dan memicu pengumuman proaktif V2.2.
    """

    def __init__(self, check_interval_seconds: int = 10):
        self.check_interval = check_interval_seconds
        self.voice_intel: NOCVoiceIntelligenceEngineV22 = get_voice_intelligence_engine_v22()
        self.announcer = get_announcer()
        self._running = False
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        """Jalankan pemantauan proaktif di background thread."""
        if self._running:
            return
        self._running = True
        self._thread = threading.Thread(target=self._monitor_loop, daemon=True, name="ProactiveAlertMonitorThreadV22")
        self._thread.start()
        logger.info(f"[ProactiveAlertEngine V2.2] Background monitor started. Interval: {self.check_interval}s")

    def stop(self) -> None:
        """Hentikan pemantauan proaktif."""
        self._running = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=3.0)
        logger.info("[ProactiveAlertEngine V2.2] Background monitor stopped.")

    def _monitor_loop(self) -> None:
        """Loop pemantauan telemetri real-time V2.2."""
        while self._running:
            try:
                alert_payload = self.voice_intel.process_telemetry_tick_v22()
                if alert_payload and alert_payload.get("text"):
                    event_dict = {
                        "event_type": "early_warning",
                        "severity": "CRITICAL" if alert_payload.get("priority_score", 0) >= 80 else "WARNING",
                        "title": f"Update Lifecycle: {alert_payload.get('lifecycle_state')}",
                        "details": alert_payload.get("text"),
                        "device": alert_payload.get("device", "PC-MKT-NUC"),
                    }
                    res = self.announcer.announce(event_dict)
                    if not res.get("skipped"):
                        logger.info(f"[ProactiveAlertEngine V2] 🗣️ ANNOUNCED: {res.get('text')}")
            except Exception as e:
                logger.error(f"[ProactiveAlertEngine V2] Error in monitor loop: {e}")
            
            time.sleep(self.check_interval)


# Singleton Accessor
_engine_instance: Optional[ProactiveAlertEngine] = None

def start_proactive_engine() -> ProactiveAlertEngine:
    global _engine_instance
    if _engine_instance is None:
        _engine_instance = ProactiveAlertEngine(check_interval_seconds=10)
        _engine_instance.start()
    return _engine_instance
