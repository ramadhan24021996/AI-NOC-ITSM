import json
import logging
from schemas import ActionSchema

logger = logging.getLogger("RECOVERY_AGENT")

class RecoveryAgent:
    def __init__(self, nc=None):
        self.nc = nc

    async def start(self):
        if not self.nc:
            return
        async def handler(msg):
            try:
                payload = json.loads(msg.data.decode())
                logger.info(f"Recovery Agent preparing action for payload: {payload}")
                
                action = payload.get("recommended_action", "SYSTEM_RESTART")
                
                risk_level = "low"
                requires_approval = False
                
                high_risk_actions = ["reboot", "stop", "delete", "kill", "firewall"]
                for act in high_risk_actions:
                    if act in action.lower():
                        risk_level = "high"
                        requires_approval = True
                        break

                action_schema = ActionSchema(
                    action_id=payload.get("action_id", "ACT-001"),
                    action_type="REMEDIATION",
                    recommended_action=action,
                    risk_level=risk_level,
                    requires_human_approval=requires_approval,
                    rollback_command="ROLLBACK_" + action,
                    execution_steps=["Initialize connection", "Dispatch command via agent", "Verify output"]
                )
                
                response_payload = action_schema.dict()
                await msg.respond(json.dumps(response_payload).encode())
            except Exception as e:
                logger.error(f"Error in RecoveryAgent handler: {e}")
                await msg.respond(json.dumps({"error": str(e)}).encode())

        await self.nc.subscribe("agent.recovery.prepare", cb=handler)
        logger.info("Recovery Agent listening on 'agent.recovery.prepare'")
