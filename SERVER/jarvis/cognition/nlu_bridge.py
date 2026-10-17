"""
SERVER.jarvis.cognition.nlu_bridge — JARVIS NLU Bridge
=======================================================
P11 Implementation: Menghubungkan NLUEngine (python_ai_core/core/nlu_engine.py)
ke JARVIS Presentation Runtime.

NLUEngine capabilities yang dibridgekan:
  - Intent classification (NOC-specific categories)
  - Named Entity Recognition (device, IP, site)
  - Urgency detection (EMERGENCY / HIGH / NORMAL)
  - Sentiment analysis (FRUSTRATED / NEUTRAL / POSITIVE)
  - Sub-query decomposition ("cek status dan restart jika offline")
  - Symptom clustering (ping timeout, disk full, CPU spike, dll.)

Hasilnya digunakan oleh IntentRouter untuk enrichment.
"""
import logging
import sys
import os
from typing import Dict, Any, Optional

logger = logging.getLogger("jarvis.cognition.nlu_bridge")


class JarvisNLUBridge:
    """
    P11 — JARVIS NLU Bridge.
    Wraps NLUEngine dari python_ai_core agar bisa digunakan di JARVIS domain
    tanpa melanggar ADR-005 (tidak import langsung DB/Repo, hanya shared service).

    Jika NLUEngine tidak tersedia (import error), fallback ke basic analysis.
    """

    def __init__(self):
        self._nlu: Optional[Any] = None
        self._available = False
        self._try_init()

    def _try_init(self) -> None:
        """Try to import NLUEngine dengan graceful fallback."""
        try:
            from SERVER.python_ai_core.core.nlu_engine import NLUEngine  # type: ignore
            self._nlu = NLUEngine()
            self._available = True
            logger.info("[NLUBridge] NLUEngine connected successfully.")
        except Exception as e:
            logger.warning(f"[NLUBridge] NLUEngine not available: {e}. Using fallback.")
            self._available = False

    def analyze(self, query_text: str) -> Dict[str, Any]:
        """
        Analisis lengkap teks query menggunakan NLUEngine.

        Returns:
            Dict berisi:
              - intent: string NOC intent
              - confidence: float [0.0, 1.0]
              - entities: dict (device, ip, site, dll.)
              - urgency: EMERGENCY | HIGH | NORMAL
              - sentiment: FRUSTRATED | NEUTRAL | POSITIVE
              - sub_queries: dict jika multi-step command
              - symptoms: list symptom yang terdeteksi
              - language: "id" atau "en"
        """
        if self._available and self._nlu:
            try:
                payload = self._nlu.understand(query_text)
                return {
                    "intent": payload.intent,
                    "confidence": payload.confidence,
                    "entities": payload.entities,
                    "urgency": payload.urgency,
                    "sentiment": payload.sentiment,
                    "sub_queries": payload.sub_queries,
                    "language": payload.language,
                    "symptoms": list(payload.entities.get("symptoms", [])),
                    "source": "NLUEngine",
                }
            except Exception as e:
                logger.warning(f"[NLUBridge] NLUEngine.understand failed: {e}. Using fallback.")

        # Fallback: basic keyword analysis
        return self._fallback_analyze(query_text)

    def _fallback_analyze(self, query_text: str) -> Dict[str, Any]:
        """Fallback NLU analysis saat NLUEngine tidak tersedia."""
        text_lower = query_text.lower()

        # Urgency detection
        emergency_words = ["darurat", "critical", "kritis", "mati total", "emergency", "blackout"]
        high_words = ["segera", "cepat", "urgent", "gangguan", "error", "problem"]
        if any(w in text_lower for w in emergency_words):
            urgency = "EMERGENCY"
        elif any(w in text_lower for w in high_words):
            urgency = "HIGH"
        else:
            urgency = "NORMAL"

        # Sentiment (basic)
        frustrated_words = ["kenapa", "mengapa", "lagi", "terus", "selalu", "susah"]
        if any(w in text_lower for w in frustrated_words):
            sentiment = "FRUSTRATED"
        else:
            sentiment = "NEUTRAL"

        # Language detection (basic)
        indonesia_indicators = ["jarvis", "cek", "lihat", "buka", "restart", "status", "insiden"]
        language = "id" if any(w in text_lower for w in indonesia_indicators) else "en"

        return {
            "intent": "NOC_QUERY",
            "confidence": 0.7,
            "entities": {},
            "urgency": urgency,
            "sentiment": sentiment,
            "sub_queries": {},
            "language": language,
            "symptoms": [],
            "source": "FALLBACK",
        }

    def get_urgency(self, query_text: str) -> str:
        """Quick urgency check tanpa full NLU processing."""
        result = self.analyze(query_text)
        return result.get("urgency", "NORMAL")

    def get_entities(self, query_text: str) -> Dict[str, Any]:
        """Extract entities saja (device, IP, site)."""
        result = self.analyze(query_text)
        return result.get("entities", {})

    def decompose_multi_query(self, query_text: str) -> Dict[str, str]:
        """
        Decompose multi-step command:
        "cek status server-01 dan restart jika offline"
        → {"step_1": "cek status server-01", "step_2": "restart jika offline"}
        """
        result = self.analyze(query_text)
        sub_queries = result.get("sub_queries", {})
        if not sub_queries:
            # Simple decomposition by "dan" / "kemudian" / "lalu"
            for sep in [" dan jika ", " kemudian ", " lalu ", " dan ", " then "]:
                if sep in query_text.lower():
                    parts = query_text.split(sep, 1)
                    return {"step_1": parts[0].strip(), "step_2": parts[1].strip()}
        return sub_queries or {"step_1": query_text}

    @property
    def is_available(self) -> bool:
        return self._available


class JarvisOpeningBridge:
    """
    P12 — JARVIS Opening Bridge.
    Menghubungkan JarvisOpeningEngine ke StartupReporter dan NOCBridge untuk greeting
    yang 100% real-time & context-aware (hari, waktu, shift, status telemetri live).
    """

    def __init__(self, noc_bridge: Optional[Any] = None):
        self._engine: Optional[Any] = None
        self._available = False
        self.noc_bridge = noc_bridge
        self._try_init()

    def _try_init(self) -> None:
        try:
            from SERVER.python_ai_core.core.jarvis_opening_engine import JarvisOpeningEngine  # type: ignore
            self._engine = JarvisOpeningEngine()
            self._available = True
            logger.info("[OpeningBridge] JarvisOpeningEngine connected.")
        except Exception as e:
            logger.warning(f"[OpeningBridge] JarvisOpeningEngine not available: {e}.")

    def generate_greeting_realtime(
        self,
        operator_name: str = "",
        noc_bridge: Optional[Any] = None,
        is_returning_user: bool = False,
    ) -> str:
        """
        Generate REAL-TIME greeting dengan membaca data live dari NOCBridge secara PARALEL.

        Membaca secara otomatis:
          - Health score & active incidents
          - Pending HITL approval count
          - Host CPU/RAM load
          - Offline sites
        """
        bridge = noc_bridge or self.noc_bridge
        has_active_incident = False
        incident_count = 0
        priority_flags = []
        system_busy = False

        if bridge:
            try:
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor(max_workers=4) as executor:
                    fut_health = executor.submit(bridge.get_system_health)
                    fut_queues = executor.submit(bridge.get_system_queues)
                    fut_metrics = executor.submit(bridge.get_host_metrics)
                    fut_sites = executor.submit(bridge.ping_sites)

                    health_resp = fut_health.result()
                    queues_resp = fut_queues.result()
                    metrics_resp = fut_metrics.result()
                    sites_resp = fut_sites.result()

                # Parse responses
                if health_resp.success:
                    status = health_resp.data.get("status", "HEALTHY")
                    if status in ("DEGRADED", "CRITICAL"):
                        has_active_incident = True

                if queues_resp.success:
                    hitl_pending = queues_resp.data.get("hitl_pending", 0)
                    if hitl_pending > 0:
                        has_active_incident = True
                        incident_count += hitl_pending

                if metrics_resp.success:
                    cpu = float(metrics_resp.data.get("cpu_pct", 0))
                    if cpu > 80:
                        system_busy = True

                if sites_resp.success:
                    sites = sites_resp.data if isinstance(sites_resp.data, list) else []
                    offline = [s.get("site_name", s.get("site_id")) for s in sites if not s.get("online", False)]
                    if offline:
                        has_active_incident = True
                        incident_count += len(offline)
                        priority_flags.extend([f"Site {name} OFFLINE" for name in offline[:3]])

            except Exception as e:
                logger.warning(f"[OpeningBridge] Realtime fetch failed: {e}")

        return self.generate_greeting(
            operator_name=operator_name,
            has_active_incident=has_active_incident,
            incident_count=max(incident_count, 1 if has_active_incident else 0),
            priority_flags=priority_flags,
            is_returning_user=is_returning_user,
            system_busy=system_busy,
        )

    def generate_greeting(
        self,
        operator_name: str = "",
        has_active_incident: bool = False,
        incident_count: int = 0,
        priority_flags: Optional[list] = None,
        is_returning_user: bool = False,
        system_busy: bool = False,
    ) -> str:
        """
        Generate context-aware greeting dari JarvisOpeningEngine.
        """
        if self._available and self._engine:
            try:
                context = {
                    "operator_name": operator_name,
                    "active_incidents": [
                        {"device_name": flag, "flag": "OFFLINE"}
                        for flag in (priority_flags or [])
                    ] if priority_flags else (["INC-ACTIVE"] * incident_count if has_active_incident else []),
                    "priority_flags": priority_flags or [],
                    "is_returning_user": is_returning_user,
                    "system_busy": system_busy,
                }
                greeting = self._engine.generate_opening(context)
                return greeting
            except Exception as e:
                logger.warning(f"[OpeningBridge] generate_opening failed: {e}")

        # Fallback greeting
        from datetime import datetime, timezone, timedelta
        wib = timezone(timedelta(hours=7))
        hour = datetime.now(wib).hour
        if 5 <= hour < 12:
            time_str = "pagi"
        elif 12 <= hour < 15:
            time_str = "siang"
        elif 15 <= hour < 18:
            time_str = "sore"
        else:
            time_str = "malam"

        title = f", Pak {operator_name}" if operator_name else ""
        if has_active_incident:
            return (
                f"Selamat {time_str}{title}. "
                f"⚠️ Terdapat {incident_count} insiden/anomali aktif yang perlu perhatian. "
                f"Jarvis siap membantu diagnosa."
            )
        return f"Selamat {time_str}{title}. Semua sistem beroperasi normal. Jarvis siap."

    @property
    def is_available(self) -> bool:
        return self._available
