"""
SERVER.integration - REST Handler Base
Base class for translating REST HTTP JSON requests into DTO Contracts.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

class RESTHandlerBase(ABC):
    """Abstract REST HTTP handler base class."""
    @abstractmethod
    def handle_http_post(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 7.4
# ══════════════════════════════════════════════════════════════════════════════
import logging, uuid
from typing import Dict, Any
from datetime import datetime, timezone

_restlog = logging.getLogger("integration.rest")

class StandardRESTHandler(RESTHandlerBase):
    """
    Concrete REST HTTP handler — validates headers, maps DTO, formats response.
    Routes POST requests through the UnifiedGateway.
    """
    REQUIRED_HEADERS = ["Content-Type"]

    def handle_http_post(self, payload: Dict[str, Any], headers: Dict[str, str]) -> Dict[str, Any]:
        # 1. Validate required headers
        for h in self.REQUIRED_HEADERS:
            if h not in headers and h.lower() not in {k.lower() for k in headers}:
                _restlog.warning("[RESTHandler] Missing required header: %s", h)

        # 2. Enrich payload with request metadata
        enriched = {
            **payload,
            "request_id": headers.get("X-Request-ID", str(uuid.uuid4())),
            "user_id":    headers.get("X-User-ID", "anonymous"),
            "user_role":  headers.get("X-User-Role", "operator"),
            "trace_id":   headers.get("X-Trace-ID", str(uuid.uuid4())),
            "headers":    headers,
        }

        _restlog.info("[RESTHandler] POST received — user=%s keys=%s",
                      enriched["user_id"], list(payload.keys()))

        # 3. Route to UnifiedGateway
        try:
            from SERVER.integration.gateway.unified_gateway import DefaultUnifiedGateway
            gw = DefaultUnifiedGateway()
            result = gw.handle_request(enriched)
            return {
                "status": "ok",
                "request_id": enriched["request_id"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "data": result,
            }
        except Exception as e:
            _restlog.error("[RESTHandler] Routing failed: %s", e, exc_info=True)
            return {
                "status": "error",
                "request_id": enriched["request_id"],
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "error": str(e),
            }
