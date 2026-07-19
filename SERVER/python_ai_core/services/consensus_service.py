import asyncio
import json
import logging
import os
import sys
import nats

# Add parent directory to sys.path to allow imports of peer modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from consensus_engine import ConsensusEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CONSENSUS_SERVICE")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")

async def main():
    nc = await nats.connect(NATS_URL)
    logger.info(f"Connected to NATS at {NATS_URL}.")

    engine = ConsensusEngine()

    async def request_handler(msg):
        subject = msg.subject
        reply = msg.reply
        try:
            data = json.loads(msg.data.decode())
            logger.info(f"Processing consensus request for site: {data.get('site_id')}")
            
            # invoke engine
            verdict = await engine.get_consensus_verdict(
                incident_details=data.get("incident_details"),
                historical_context=data.get("historical_context", []),
                severity_score=data.get("severity_score", 30),
                pattern=data.get("pattern", "WEIGHTED CONFIDENCE")
            )
            response = {"status": "success", "verdict": verdict}
        except Exception as e:
            logger.error(f"Error processing consensus request: {e}")
            response = {"status": "error", "error": str(e)}

        await nc.publish(reply, json.dumps(response).encode())

    # Subscribe to target subject with queue group
    await nc.subscribe("ai.engine.consensus", queue="consensus-service-group", cb=request_handler)
    logger.info("Consensus Service is active and listening on 'ai.engine.consensus' (group: consensus-service-group).")

    # Keep running
    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
