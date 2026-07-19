#!/usr/bin/env python3
"""
End-to-end validation: Publish to remediation.execute → dashboard server subscriber
→ execution_ledger populated.
"""
import asyncio
import json
import time
import psycopg2

DB = {
    "host": "postgres",
    "port": 5432,
    "database": "osi_system",
    "user": "postgres",
    "password": "postgres"
}

async def main():
    from nats.aio.client import Client as NATS
    nc = NATS()
    await nc.connect("nats://nats:4222")
    print("[+] NATS connected.")

    # Count ledger before
    conn = psycopg2.connect(**DB)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM execution_ledger")
    before = cur.fetchone()[0]
    print(f"[i] execution_ledger rows before: {before}")

    # Get a real incident with known device
    cur.execute("""
        SELECT incident_id, device_name 
        FROM incidents 
        WHERE device_name IS NOT NULL AND device_name != ''
        LIMIT 1
    """)
    row = cur.fetchone()
    if not row:
        print("[-] No incidents found with device_name — abort.")
        await nc.close(); conn.close(); return

    incident_id, device_name = row
    print(f"[i] Using incident_id={incident_id} device_name={device_name}")

    exec_id = f"e2e-ledger-test-{int(time.time())}"
    payload = {
        "event_id": f"evt-{exec_id}",
        "incident_id": incident_id,
        "action": "RESTART_SPOOLER",
        "details": "RESTART_SPOOLER",
        "risk_level": "LOW",
        "execution_id": exec_id,
        "params": {}
    }

    print(f"[+] Publishing to remediation.execute with exec_id={exec_id}")
    await nc.publish("remediation.execute", json.dumps(payload).encode())
    await nc.flush()

    print("[*] Waiting 5s for dashboard server subscriber to process...")
    await asyncio.sleep(5)

    # Check ledger
    cur.execute("SELECT execution_id, dispatch_state, agent_ack_state, final_state FROM execution_ledger WHERE execution_id = %s", (exec_id,))
    ledger_row = cur.fetchone()
    if ledger_row:
        print(f"[+] LEDGER HIT: {ledger_row}")
        print("[✓] Execution ledger populated by NATS subscriber — SUCCESS")
    else:
        print("[~] Ledger entry NOT found. Checking if incident device resolves in fleet_devices...")
        cur.execute("SELECT pc_name, ip_address FROM fleet_devices WHERE pc_name = %s LIMIT 1", (device_name,))
        fdev = cur.fetchone()
        if fdev:
            print(f"[i] fleet_devices match found: {fdev} — check dashboard_server logs for TCP dial errors")
        else:
            print(f"[!] Device '{device_name}' not found in fleet_devices — this is why ledger is empty (device lookup failure)")
        
        # Still verify the NATS subscriber is running (by checking exec_ledger total)
        cur.execute("SELECT COUNT(*) FROM execution_ledger")
        after = cur.fetchone()[0]
        print(f"[i] execution_ledger rows after: {after} (before: {before})")

    # Idempotency check: publish same exec_id again
    print("[+] Re-publishing same execution_id to test idempotency...")
    await nc.publish("remediation.execute", json.dumps(payload).encode())
    await nc.flush()
    await asyncio.sleep(3)
    cur.execute("SELECT COUNT(*) FROM execution_ledger WHERE execution_id = %s", (exec_id,))
    idem_count = cur.fetchone()[0]
    if idem_count <= 1:
        print(f"[✓] Idempotency OK: {idem_count} record(s) — no duplicate execution")
    else:
        print(f"[!] Idempotency FAILED: {idem_count} records for same execution_id")

    await nc.close()
    conn.close()
    print("\n[+] Test complete.")

if __name__ == "__main__":
    asyncio.run(main())
