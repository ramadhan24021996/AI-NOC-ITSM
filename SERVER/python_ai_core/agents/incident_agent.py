import json
import logging
from datetime import datetime
from schemas import IncidentSchema

logger = logging.getLogger("INCIDENT_AGENT")

class IncidentAgent:
    def __init__(self, nc=None):
        self.nc = nc

    async def start(self):
        if not self.nc:
            return
        async def handler(msg):
            try:
                payload = json.loads(msg.data.decode())
                logger.info(f"Incident Agent analyzing: {payload}")
                
                severity = payload.get("metadata", {}).get("severity", "LOW")
                description = payload.get("description", "No description")
                raw_inc_id = payload.get("incident_id")
                incident_id = str(raw_inc_id) if raw_inc_id is not None else ""
                
                incident = IncidentSchema(
                    incident_id=incident_id if incident_id and incident_id != "None" else "0",
                    severity=severity,
                    symptom=description,
                    root_cause=f"Identified anomalous event: {description}",
                    timeline=[f"Telemetry anomaly flagged at {datetime.utcnow().isoformat()}"],
                    confidence=0.85,
                    risk_level="low",
                    recommended_action="Diagnose system processes",
                    requires_human_approval=False
                )
                
                response_payload = incident.dict()
                await msg.respond(json.dumps(response_payload).encode())
            except Exception as e:
                logger.error(f"Error in IncidentAgent handler: {e}")
                await msg.respond(json.dumps({"error": str(e)}).encode())

        await self.nc.subscribe("agent.incident.analyze", cb=handler)
        logger.info("Incident Agent listening on 'agent.incident.analyze'")
