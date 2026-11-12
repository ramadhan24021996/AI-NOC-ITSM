import asyncio
import os
import nats
import json
import time
import sys

async def main():
    nats_token = os.environ.get("NATS_TOKEN", os.environ.get("OSI_SECURITY_KEY", ""))
    nats_host = os.environ.get("NATS_HOST", "127.0.0.1")
    nats_port = os.environ.get("NATS_PORT", "4222")
    nats_url = f"nats://{nats_token}@{nats_host}:{nats_port}" if nats_token else f"nats://{nats_host}:{nats_port}"
    nc = await nats.connect(nats_url)
    print("Connected to NATS.")

    incident_id = 194
    if len(sys.argv) > 1:
        try:
            incident_id = int(sys.argv[1])
        except Exception:
            _ = None

    try:
        payload = {
            "incident_id": incident_id,
            "force_reanalyze": True,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        
        print(f"Publishing to incident.reanalyze for ID {incident_id}...")
        await nc.publish("incident.reanalyze", json.dumps(payload).encode())
        await nc.flush()
        print("Published.")
        
        await asyncio.sleep(0.5)
    finally:
        await nc.close()

if __name__ == '__main__':
    asyncio.run(main())
