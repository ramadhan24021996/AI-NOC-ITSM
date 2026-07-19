import asyncio
import json
import logging
import os
import sys
import nats

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from critic_engine import AdversarialCriticEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CRITIC_SERVICE")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")

async def main():
    nc = await nats.connect(NATS_URL)
    logger.info(f"Connected to NATS at {NATS_URL}.")

    engine = AdversarialCriticEngine()

    async def request_handler(msg):
        subject = msg.subject
        reply = msg.reply
        try:
            data = json.loads(msg.data.decode())
            logger.info(f"Processing critic evaluation for action: {data.get('action')}")
            
            # invoke engine
            result = await engine.evaluate_action(
                action=data.get("action"),
                severity=data.get("severity"),
                confidence=data.get("confidence"),
                incident_details=data.get("incident_details"),
                embedding=data.get("embedding")
            )
            response = {"status": "success", "result": result}
        except Exception as e:
            logger.error(f"Error processing critic request: {e}")
            response = {"status": "error", "error": str(e)}

        await nc.publish(reply, json.dumps(response).encode())

    # Subscribe to target subject with queue group
    await nc.subscribe("ai.engine.critic", queue="critic-service-group", cb=request_handler)
    logger.info("Critic Service is active and listening on 'ai.engine.critic' (group: critic-service-group).")

    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
