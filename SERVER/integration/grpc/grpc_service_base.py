"""
SERVER.integration - gRPC Service Base
Base class for high-performance internal gRPC communication.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

class gRPCServiceBase(ABC):
    """Abstract gRPC service base handler."""
    @abstractmethod
    def handle_rpc_call(self, method_name: str, request_bytes: bytes) -> bytes:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 7.3
# ══════════════════════════════════════════════════════════════════════════════
import json, logging
from typing import Dict, Any, Callable

_grpclog = logging.getLogger("integration.grpc")

class JSONgRPCServiceBase(gRPCServiceBase):
    """
    JSON-over-gRPC adapter. Routes RPC method calls to registered Python handlers.
    Serializes/deserializes JSON bytes for internal gRPC communication.
    """

    def __init__(self):
        self._methods: Dict[str, Callable] = {}

    def register_method(self, method_name: str, handler: Callable) -> None:
        self._methods[method_name] = handler
        _grpclog.info("[gRPCService] Registered method: %s", method_name)

    def handle_rpc_call(self, method_name: str, request_bytes: bytes) -> bytes:
        try:
            request = json.loads(request_bytes.decode("utf-8"))
        except (json.JSONDecodeError, UnicodeDecodeError) as e:
            _grpclog.error("[gRPCService] Failed to decode request for %s: %s", method_name, e)
            return json.dumps({"error": "Invalid request format", "code": 400}).encode()

        handler = self._methods.get(method_name)
        if not handler:
            _grpclog.warning("[gRPCService] Unknown method: %s", method_name)
            return json.dumps({"error": f"Method '{method_name}' not found", "code": 404}).encode()

        try:
            result = handler(request)
            return json.dumps(result, default=str).encode("utf-8")
        except Exception as e:
            _grpclog.error("[gRPCService] Error in method %s: %s", method_name, e, exc_info=True)
            return json.dumps({"error": str(e), "code": 500}).encode()
