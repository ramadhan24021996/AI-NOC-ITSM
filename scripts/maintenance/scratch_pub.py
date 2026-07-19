import asyncio
from nats.aio.client import Client as NATS
import json

async def run():
    nc = NATS()
    await nc.connect("nats://localhost:4222")
    payload = {
        "title": "BGP Session Down",
        "symptoms": "BGP neighbor 192.168.1.1 is Idle, prefixes withdrawn, latency increased",
        "description": "Router PE-1 lost BGP connection to branch site",
        "metadata": {"requires_hitl": False, "integrity_score": 0.95},
        "site_id": "idm"
    }
    await nc.publish("telemetry.site.idm.critical", json.dumps(payload).encode())
    await nc.flush()
    await nc.close()

if __name__ == '__main__':
    asyncio.run(run())
