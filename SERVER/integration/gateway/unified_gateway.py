"""
SERVER.integration - Unified Gateway
Unified API gateway interface for DTO translation, Auth hooks, and Request routing.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from SERVER.contracts.schemas import IncidentQueryContract, IncidentResponseContract

class UnifiedGateway(ABC):
    """Abstract Unified API Gateway interface."""
    @abstractmethod
    def handle_request(self, raw_request: Dict[str, Any]) -> Dict[str, Any]:
        pass

    @abstractmethod
    def translate_to_contract(self, raw_request: Dict[str, Any]) -> IncidentQueryContract:
        pass

    @abstractmethod
    def translate_from_contract(self, response_contract: IncidentResponseContract) -> Dict[str, Any]:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 7.1
# ══════════════════════════════════════════════════════════════════════════════
import logging, uuid
from typing import Dict, Any

_gwlog = logging.getLogger("integration.gateway")

class DefaultUnifiedGateway(UnifiedGateway):
    """
    Concrete Unified API Gateway.
    Handles DTO translation (raw dict → IncidentQueryContract),
    extracts auth headers, and routes requests to the AI pipeline.
    """

    def handle_request(self, raw_request: Dict[str, Any]) -> Dict[str, Any]:
        _gwlog.info("[UnifiedGateway] Incoming request — keys=%s", list(raw_request.keys()))
        try:
            contract = self.translate_to_contract(raw_request)
            from SERVER.contracts.schemas import IncidentResponseContract
            # Route to AI pipeline if available
            try:
                from SERVER.python_ai_core.supervisor.jarvis_supervisor import JarvisSupervisor
                supervisor = JarvisSupervisor()
                response = supervisor.process(contract)
            except ImportError:
                _gwlog.warning("[UnifiedGateway] JarvisSupervisor not available — returning stub response")
                response = IncidentResponseContract(
                    query_id=contract.query_id,
                    status="STUB", answer="Gateway processed — AI pipeline not connected",
                    confidence=0.0, trace_id=contract.trace_id
                ) if hasattr(IncidentResponseContract, '__init__') else None

            if response:
                return self.translate_from_contract(response)
            return {"status": "processed", "query_id": contract.query_id}
        except Exception as e:
            _gwlog.error("[UnifiedGateway] handle_request failed: %s", e, exc_info=True)
            return {"status": "error", "detail": str(e)}

    def translate_to_contract(self, raw_request: Dict[str, Any]) -> "IncidentQueryContract":
        from SERVER.contracts.schemas import IncidentQueryContract
        headers = raw_request.get("headers", {})
        return IncidentQueryContract(
            query_id         = raw_request.get("query_id", str(uuid.uuid4())),
            user_id          = headers.get("X-User-ID", raw_request.get("user_id", "anonymous")),
            user_role        = headers.get("X-User-Role", raw_request.get("user_role", "operator")),
            query_text       = raw_request.get("query", raw_request.get("message", "")),
            site_location    = raw_request.get("site_location"),
            telemetry_context= raw_request.get("telemetry", {}),
            request_id       = raw_request.get("request_id", str(uuid.uuid4())),
            conversation_id  = raw_request.get("conversation_id", ""),
            trace_id         = raw_request.get("trace_id", str(uuid.uuid4())),
            session_id       = raw_request.get("session_id", ""),
        )

    def translate_from_contract(self, response_contract) -> Dict[str, Any]:
        if hasattr(response_contract, "__dict__"):
            return {k: v for k, v in response_contract.__dict__.items()}
        return {"response": str(response_contract)}
