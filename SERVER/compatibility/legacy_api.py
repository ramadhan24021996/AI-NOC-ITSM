"""
SERVER.compatibility - Legacy API Adapter Bridge
Provides backward-compatible REST API endpoints translating legacy JSON queries into IncidentQueryContract DTOs.
"""
from typing import Dict, Any
from SERVER.contracts.schemas import IncidentQueryContract, IncidentResponseContract

class LegacyAPIBridge:
    """Translates legacy REST API payloads to IncidentQueryContract DTOs."""

    @staticmethod
    def legacy_request_to_contract(raw_payload: Dict[str, Any]) -> IncidentQueryContract:
        return IncidentQueryContract(
            query_id=str(raw_payload.get("query_id", raw_payload.get("id", "LEGACY-Q1"))),
            user_id=str(raw_payload.get("user_id", raw_payload.get("user", "legacy_user"))),
            user_role=str(raw_payload.get("user_role", raw_payload.get("role", "noc_operator"))),
            query_text=str(raw_payload.get("query", raw_payload.get("prompt", ""))),
            site_location=raw_payload.get("site"),
            telemetry_context=raw_payload.get("context", {}),
        )

    @staticmethod
    def contract_to_legacy_response(response: IncidentResponseContract) -> Dict[str, Any]:
        return {
            "id": response.query_id,
            "answer": response.answer_text,
            "track": response.execution_track.value,
            "confidence": response.evidence_score,
            "citations": response.citations,
            "requires_hitl": response.requires_hitl,
        }
