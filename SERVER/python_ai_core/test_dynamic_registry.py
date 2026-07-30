import asyncio
import json
import redis
import time
from nats.aio.client import Client as NATS
import sys
import os
sys.path.append("/app")
from adapters.nats_adapter import NATSAdapter

async def run():
    print("Testing Dynamic Agent IP Registry...")
    security_key = os.environ.get("OSI_SECURITY_KEY", "SecurePassword_123!")
    nats_url = os.environ.get("NATS_URL", f"nats://{security_key}@nats:4222")
    adapter = NATSAdapter(nats_url)
    nc = await adapter.connect()

    # 1. Publish Heartbeat with IP
    print("\n1. Publishing Heartbeat for TEST_AGENT with IP 10.99.99.99...")
    heartbeat_payload = {
        "agent": "TEST_AGENT",
        "ip": "10.99.99.99",
        "status": "ONLINE",
        "uptime": 100,
        "queue_depth": 0,
        "cpu": 1.5
    }
    await nc.publish("agent.status.site.global.TEST_AGENT", json.dumps(heartbeat_payload).encode())
    await asyncio.sleep(1) # wait for dashboard_server to process

    # 2. Check Redis
    print("\n2. Checking Redis for dynamic registry key...")
    r = redis.Redis(host='redis', port=6379, password=security_key, decode_responses=True)
    ip_in_redis = r.get("agent_registry:ip:TEST_AGENT")
    print(f"IP found in Redis: {ip_in_redis}")
    
    if ip_in_redis != "10.99.99.99":
        print("❌ FAILED: IP was not saved to Redis.")
        return

    # 3. Publish Remediation Execute
    print("\n3. Publishing Remediation Execute for TEST_AGENT...")
    remediation_payload = {
        "event_id": "test_event",
        "incident_id": 9999,
        "action": "PING",
        "details": "TEST_AGENT", # details is used as pc_name in dashboard_server.go
        "risk_level": "LOW",
        "execution_id": "test_exec_9999",
        "params": {}
    }
    await nc.publish("remediation.execute", json.dumps(remediation_payload).encode())
    
    print("\n✅ Test events sent! Now check the dashboard_server logs for the following:")
    print("   '[EXECUTION RELAY] Using Dynamic Registry IP: 10.99.99.99 for TEST_AGENT'")
    
    await nc.close()

if __name__ == '__main__':
    asyncio.run(run())
