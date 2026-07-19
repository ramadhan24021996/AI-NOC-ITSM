import asyncio
import nats
import json
import time
import sys

async def main():
    nc = await nats.connect("nats://UWaVSW9Jz-Yl9wumi7SdHV0o9HSVZCWDlHclqWLUBkE=@127.0.0.1:4222")
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
