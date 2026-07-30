import asyncio
import json
import logging
import os
import sys
import nats
import psycopg2

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.policy_engine import PolicyEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("POLICY_SERVICE")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")

# Database connection credentials
DB_HOST = os.environ.get("DB_HOST", "postgres")
DB_PORT = os.environ.get("DB_PORT", "5432")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", "postgres")

def get_db_conn():
    try:
        return psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD
        )
    except Exception as e:
        logger.error(f"Failed to connect to database in policy service: {e}")
        return None

async def main():
    nc = await nats.connect(NATS_URL)
    logger.info(f"Connected to NATS at {NATS_URL}.")

    engine = PolicyEngine()

    async def request_handler(msg):
        subject = msg.subject
        reply = msg.reply
        conn = get_db_conn()
        try:
            data = json.loads(msg.data.decode())
            logger.info(f"Processing policy evaluation for incident ID: {data.get('incident_id')}")
            
            # invoke engine
            effect = engine.evaluate_policy(
                conn=conn,
                confidence=data.get("confidence"),
                risk=data.get("risk"),
                severity=data.get("severity"),
                action_type=data.get("action_type", ""),
                incident_id=data.get("incident_id"),
                trust_score=data.get("trust_score"),
                blast_radius=data.get("blast_radius"),
                site_criticality=data.get("site_criticality"),
                agent_name=data.get("agent_name")
            )
            response = {"status": "success", "effect": effect}
        except Exception as e:
            logger.error(f"Error processing policy request: {e}")
            response = {"status": "error", "error": str(e)}
        finally:
            if conn:
                conn.close()

        await nc.publish(reply, json.dumps(response).encode())

    # Subscribe to target subject with queue group
    await nc.subscribe("ai.engine.policy", queue="policy-service-group", cb=request_handler)
    logger.info("Policy Service is active and listening on 'ai.engine.policy' (group: policy-service-group).")

    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
