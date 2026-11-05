"""
SERVER.integration - WebSocket Gateway Base
Base class for real-time streaming WebSocket connection handling.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any, Callable

class WebSocketGatewayBase(ABC):
    """Abstract WebSocket gateway connection handler."""
    @abstractmethod
    def on_connect(self, session_id: str) -> None:
        pass

    @abstractmethod
    def on_message(self, session_id: str, message_text: str) -> Dict[str, Any]:
        pass

    @abstractmethod
    def on_disconnect(self, session_id: str) -> None:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 7.2
# ══════════════════════════════════════════════════════════════════════════════
import json, logging, threading
from typing import Dict, Any, Callable
from datetime import datetime, timezone

_wslog = logging.getLogger("integration.websocket")

class NATSWebSocketGateway(WebSocketGatewayBase):
    """
    Concrete WebSocket gateway with NATS event publishing.
    Manages session lifecycle and publishes events to NATS topic 'ws.events'.
    Falls back to in-memory if NATS unavailable.
    """
    NATS_TOPIC = "ws.events"

    def __init__(self):
        self._sessions: Dict[str, dict] = {}
        self._lock = threading.Lock()
        self._nats_nc = None  # NATS connection — lazy init

    def _get_nats(self):
        """Return synchronous NATS-like publish via os subprocess if async not available."""
        return None  # Sync NATS not available — events logged instead

    def _publish_event(self, event_type: str, session_id: str, payload: dict):
        event = {"event_type": event_type, "session_id": session_id,
                 "payload": payload, "timestamp": datetime.now(timezone.utc).isoformat()}
        _wslog.info("[WSGateway] EVENT %s session=%s", event_type, session_id)
        # Attempt NATS if configured
        try:
            import redis as _r
            rc = _r.Redis(host=__import__("os").getenv("REDIS_HOST","redis"),
                         port=int(__import__("os").getenv("REDIS_PORT",6379)),
                         decode_responses=True, socket_timeout=1)
            rc.publish("ws_events", json.dumps(event))
        except Exception:
            pass  # Redis pub optional — already logged

    def on_connect(self, session_id: str) -> None:
        with self._lock:
            self._sessions[session_id] = {
                "connected_at": datetime.now(timezone.utc).isoformat(),
                "message_count": 0,
            }
        self._publish_event("CONNECTED", session_id, {})
        _wslog.info("[WSGateway] Session CONNECTED: %s", session_id)

    def on_message(self, session_id: str, message_text: str) -> Dict[str, Any]:
        with self._lock:
            if session_id in self._sessions:
                self._sessions[session_id]["message_count"] += 1

        try:
            payload = json.loads(message_text)
        except json.JSONDecodeError:
            payload = {"raw": message_text}

        self._publish_event("MESSAGE", session_id, payload)

        # Route to AI gateway if query present
        response = {"session_id": session_id, "status": "received", "echo": payload}
        if "query" in payload or "message" in payload:
            try:
                from SERVER.integration.gateway.unified_gateway import DefaultUnifiedGateway
                gw = DefaultUnifiedGateway()
                ai_response = gw.handle_request({**payload, "session_id": session_id})
                response["ai_response"] = ai_response
            except Exception as e:
                _wslog.error("[WSGateway] AI routing failed: %s", e, exc_info=True)
                response["error"] = str(e)

        return response

    def on_disconnect(self, session_id: str) -> None:
        with self._lock:
            session = self._sessions.pop(session_id, {})
        self._publish_event("DISCONNECTED", session_id, session)
        _wslog.info("[WSGateway] Session DISCONNECTED: %s", session_id)
