import asyncio
import json
import logging
import os
import sys
import nats

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from planning.goal_engine import GoalEngine
from planning.decision_engine import DecisionEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("PLANNING_SERVICE")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")

async def daemon():
    nc = await nats.connect(NATS_URL)
    logger.info(f"Connected to NATS at {NATS_URL}.")

    goal_engine = GoalEngine()
    decision_engine = DecisionEngine()

    async def request_handler(msg):
        subject = msg.subject
        reply = msg.reply
        try:
            data = json.loads(msg.data.decode())
            action = data.get("action")
            confidence = data.get("confidence")
            risk = data.get("risk")
            severity = data.get("severity")
            policy_effect = data.get("policy_effect")
            force_hitl = data.get("force_hitl", False)

            goal_alignment = goal_engine.evaluate_alignment(action, confidence, risk)
            
            decision_res = decision_engine.decide(
                action=action,
                confidence=confidence,
                risk=risk,
                severity=severity,
                policy_effect=policy_effect,
                goal_alignment=goal_alignment,
                force_hitl=force_hitl
            )
            
            response = {"status": "success", "decision": decision_res, "goal_alignment": goal_alignment}
        except Exception as e:
            logger.error(f"Error processing planning request: {e}")
            response = {"status": "error", "error": str(e)}

        await nc.publish(reply, json.dumps(response).encode())

    await nc.subscribe("ai.engine.planning", queue="planning-service-group", cb=request_handler)
    logger.info("Planning Service is active and listening on 'ai.engine.planning' (group: planning-service-group).")

    while True:
        await asyncio.sleep(3600)

async def main():
    await daemon()

if __name__ == '__main__':
    asyncio.run(main())
