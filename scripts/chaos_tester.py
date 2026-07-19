#!/usr/bin/env python3
import subprocess
import time
import sys
import os

try:
    import psycopg2
except ImportError:
    print("Warning: psycopg2 is not installed locally on host. Postgres slow & outbox overflow tests will use docker exec.")

def print_header(title):
    print("=" * 60)
    print(f" {title.center(58)} ")
    print("=" * 60)

def run_cmd(cmd):
    try:
        res = subprocess.run(cmd, shell=True, text=True, capture_output=True, check=True)
        return res.stdout.strip()
    except subprocess.CalledProcessError as e:
        print(f"Error executing command: {cmd}\nStderr: {e.stderr}")
        return None

def test_nats_down():
    print_header("SIMULATING NATS DOWN (PAUSING CONTAINER)")
    print("[+] Pausing container 'osi-nats'...")
    run_cmd("docker pause osi-nats")
    print("[!] NATS is paused. Check dashboard connectivity telemetry (NATS status should show offline/disconnected).")
    
    duration = 10
    print(f"[*] Keeping NATS down for {duration} seconds...")
    for i in range(duration, 0, -1):
        print(f"Restoring NATS in {i} seconds...", end="\r")
        time.sleep(1)
    
    print("\n[+] Restoring NATS container...")
    run_cmd("docker unpause osi-nats")
    print("[+] NATS restored successfully.")

def test_redis_split():
    print_header("SIMULATING REDIS SPLIT (PAUSING CONTAINER)")
    print("[+] Pausing container 'osi-redis'...")
    run_cmd("docker pause osi-redis")
    print("[!] Redis is paused. Noise filter and caching features will experience fallback.")
    
    duration = 10
    print(f"[*] Keeping Redis down for {duration} seconds...")
    for i in range(duration, 0, -1):
        print(f"Restoring Redis in {i} seconds...", end="\r")
        time.sleep(1)
    
    print("\n[+] Restoring Redis container...")
    run_cmd("docker unpause osi-redis")
    print("[+] Redis restored successfully.")

def test_postgres_slow():
    print_header("SIMULATING POSTGRESQL SLOW TRANSACTION LOCK")
    print("[+] Injected pg_sleep(10) holding table lock on 'fleet_incidents'...")
    
    sql = "BEGIN; LOCK TABLE fleet_incidents IN ACCESS EXCLUSIVE MODE; SELECT pg_sleep(10); COMMIT;"
    cmd = f'docker exec -i osi-postgres psql -U postgres -d osi_system -c "{sql}"'
    
    print("[*] Running slow transaction query in background...")
    proc = subprocess.Popen(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print("[!] Table locked. Operations updating/inserting incidents will block/wait for 10 seconds.")
    
    # Wait for completion
    stdout, stderr = proc.communicate()
    print("[+] PostgreSQL slowness simulation complete. Lock released.")

def test_duplicate_replay():
    print_header("SIMULATING DUPLICATE JETSTREAM REPLAY (INBOX PATTERN)")
    print("[+] Publishing duplicate events to JetStream 'telemetry.critical'...")
    
    py_code = """
import asyncio
import json
from nats.aio.client import Client as NATS

async def run():
    nc = NATS()
    await nc.connect("nats://nats:4222")
    payload = {
        "event_id": "chaos_test_dup_" + str(int(asyncio.get_event_loop().time())),
        "pc_name": "CHAOS-TEST-HOST",
        "metric_name": "CPU",
        "metric_value": 97.2,
        "severity": "HIGH",
        "description": "Sustained high CPU usage"
    }
    msg_bytes = json.dumps(payload).encode()
    print("[NATS] Publishing first message...")
    await nc.publish("telemetry.critical", msg_bytes)
    print("[NATS] Publishing duplicate message...")
    await nc.publish("telemetry.critical", msg_bytes)
    await nc.close()

asyncio.run(run())
"""
    cmd = f"docker exec -i osi-python-ai-core python -c '{py_code}'"
    run_cmd(cmd)
    print("[!] Double published. Verify python-ai-core logs: it should reject the second message as duplicate via Inbox Pattern.")

def test_agent_timeout():
    print_header("SIMULATING AGENT TIMEOUT (PAUSING AGENT)")
    print("[+] Pausing container 'osi-python-ai-core'...")
    run_cmd("docker pause osi-python-ai-core")
    print("[!] Agent is paused. Monitor Agent Heartbeat on Portal (should change status or show offline).")
    
    duration = 12
    print(f"[*] Keeping agent paused for {duration} seconds...")
    for i in range(duration, 0, -1):
        print(f"Restoring agent in {i} seconds...", end="\r")
        time.sleep(1)
        
    print("\n[+] Restoring agent container...")
    run_cmd("docker unpause osi-python-ai-core")
    print("[+] Agent restored successfully.")

def test_outbox_overflow():
    print_header("SIMULATING OUTBOX BACKLOG OVERFLOW (100 EVENTS)")
    print("[+] Injecting 100 outbox records into 'approval_outbox'...")
    
    sql = "INSERT INTO approval_outbox (event_type, aggregate_id, payload, status, created_at) SELECT 'incident.created', 9999, '{\"test\": \"chaos_overflow\"}', 'PENDING', NOW() FROM generate_series(1, 100);"
    cmd = f'docker exec -i osi-postgres psql -U postgres -d osi_system -c "{sql}"'
    
    run_cmd(cmd)
    print("[+] 100 outbox events injected. Verify dashboard server logs/performance: it should drain the outbox sequentially.")

def main():
    while True:
        print("\n" + "=" * 50)
        print("         OSI CHAOS TESTING CONTROLLER         ")
        print("=" * 50)
        print("1. NATS Down Simulation")
        print("2. Redis Split Simulation")
        print("3. PostgreSQL Slow Transaction Lock")
        print("4. Duplicate JetStream Replay (Inbox Check)")
        print("5. Agent Timeout Simulation")
        print("6. Outbox Backlog Overflow (100 events)")
        print("7. Exit")
        
        try:
            choice = input("\nChoose simulation option (1-7): ").strip()
            if choice == "1":
                test_nats_down()
            elif choice == "2":
                test_redis_split()
            elif choice == "3":
                test_postgres_slow()
            elif choice == "4":
                test_duplicate_replay()
            elif choice == "5":
                test_agent_timeout()
            elif choice == "6":
                test_outbox_overflow()
            elif choice == "7":
                print("Exiting Chaos Tester.")
                break
            else:
                print("Invalid choice. Try again.")
        except KeyboardInterrupt:
            print("\nExiting Chaos Tester.")
            break

if __name__ == "__main__":
    main()
