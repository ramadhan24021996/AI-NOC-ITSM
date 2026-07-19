import asyncio
import json
import time
import psycopg2
import os
from datetime import datetime

DB = {
    "host": "postgres",
    "port": 5432,
    "database": "osi_system",
    "user": "postgres",
    "password": "SecurePassword_123!"
}

async def main():
    from nats.aio.client import Client as NATS
    nc = NATS()
    await nc.connect(f"nats://{os.environ.get('OSI_SECURITY_KEY', 'UWaVSW9Jz-Yl9wumi7SdHV0o9HSVZCWDlHclqWLUBkE=')}@nats:4222")
    print("[+] Connected to NATS.")

    # 1. Inject Telemetry Event
    event_id = f"E2E-TEST-{int(time.time())}"
    payload = {
        "event_id": event_id,
        "source": "E2E_AUDITOR",
        "agent_id": "SERVER-001",
        "metric": "CPU_USAGE",
        "value": 99.9,
        "severity": "CRITICAL",
        "timestamp": datetime.now().isoformat(),
        "details": "Simulated E2E Critical CPU Spike"
    }

    print(f"[+] Publishing Event {event_id} to 'telemetry.raw' (Simulating Ingestion)...")
    await nc.publish("telemetry.raw", json.dumps(payload).encode())
    await nc.flush()

    print("[*] Waiting 10 seconds for AI Core (RAG, DAG, Multi-Agent) to process the incident...")
    for i in range(10):
        print(f"    ... {10-i}s remaining")
        await asyncio.sleep(1)

    print("\n[+] Querying PostgreSQL Database for Results...")
    try:
        conn = psycopg2.connect(**DB)
        cur = conn.cursor()

        # 2. Check Incident Table
        print("\n--- INCIDENT VERIFICATION ---")
        cur.execute("SELECT incident_id, device_name, flag, evidence, confidence, rag_status FROM incidents ORDER BY timestamp DESC LIMIT 1")
        incident = cur.fetchone()
        
        if incident:
            print("✅ Incident Successfully Created by AI:")
            print(f"   - ID         : {incident[0]}")
            print(f"   - Device     : {incident[1]}")
            print(f"   - Flag       : {incident[2]}")
            print(f"   - Evidence   : {incident[3]}")
            print(f"   - Confidence : {incident[4]}%")
            print(f"   - RAG Status : {incident[5]}")
        else:
            print("❌ No Incident found. AI Pipeline might have dropped or failed to process the event.")

        # 3. Check Audit Logs
        print("\n--- AUDIT TRAIL VERIFICATION ---")
        cur.execute("SELECT audit_id, action_executed FROM ai_audit_trail WHERE event_id = %s ORDER BY created_at DESC LIMIT 3", (event_id,))
        logs = cur.fetchall()
        
        if logs:
            print(f"✅ Found {len(logs)} Audit Trail entries:")
            for log in logs:
                print(f"   - [Audit ID: {log[0]}] Action: {log[1]}")
        else:
            print("❌ No Audit Logs found for this event.")

        cur.close()
        conn.close()
    except Exception as e:
        print(f"❌ Database error: {e}")
        
    await nc.close()
    print("\n[+] E2E Business Flow Test Complete.")

if __name__ == "__main__":
    asyncio.run(main())
