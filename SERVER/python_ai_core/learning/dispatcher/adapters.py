from typing import Dict, Any
from datetime import datetime

class V5ProtocolAdapter:
    def adapt(self, v5_payload: Dict[str, Any]) -> Dict[str, Any]:
        """ Transforms legacy V5 telemetry to V6 compliant schema """
        return {
            "header": {
                "protocol_version": "v6.1_adapted",
                "message_type": v5_payload.get("type", "TELEMETRY").upper(),
                "message_id": v5_payload.get("token", "legacy-token")
            },
            "routing": {
                "tenant_id": "legacy-tenant",
                "device_id": v5_payload.get("agent", "unknown")
            },
            "trace": {
                "correlation_id": "legacy-" + v5_payload.get("timestamp", "")
            },
            "time": {
                "event_timestamp": v5_payload.get("timestamp", datetime.utcnow().isoformat()),
                "timezone": "UTC"
            },
            "payload": {
                "metric_class": v5_payload.get("event_type", "UNKNOWN"),
                "value": v5_payload.get("data", {}).get("value", 0.0),
                "quality_score": 0.5  # Legacy data gets lower trust
            }
        }\n