import os
import psycopg2
import random

def seed_database():
    db_host = os.getenv("DB_HOST", "postgres")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "osi_system")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")

    print(f"Connecting to database {db_name} at {db_host}:{db_port}...")
    try:
        conn = psycopg2.connect(
            host=db_host,
            port=db_port,
            database=db_name,
            user=db_user,
            password=db_password
        )
        conn.autocommit = True
        cur = conn.cursor()

        # Check if table exists
        cur.execute("SELECT EXISTS (SELECT FROM pg_tables WHERE tablename = 'knowledge_vectors');")
        if not cur.fetchone()[0]:
            print("knowledge_vectors table does not exist. Please restart Go backend first.")
            return

        # Check if already seeded
        cur.execute("SELECT COUNT(*) FROM knowledge_vectors;")
        count = cur.fetchone()[0]
        if count > 0:
            print(f"Table already has {count} records. Truncating to re-seed...")
            cur.execute("TRUNCATE TABLE knowledge_vectors;")

        # Define high-quality knowledge items
        knowledge_items = [
            {
                "id": "KB-SOP-001",
                "title": "CPU Usage Critical on Windows Agent",
                "symptoms": "CPU utilization reaches >95% sustained for more than 5 minutes. User experiences lagging UI, compilation processes timed out, and process watchdog alerts.",
                "root_cause": "High CPU utilization is usually caused by run-away processes (e.g. wmiprvse.exe, msmpeng.exe, or developer builds) or background scheduled tasks run during working hours.",
                "resolution": "Identify the high-CPU process via Deep Diagnostics. Stop the offending process or service. If it is wmiprvse, restart the Winmgmt service using the Windows Service control API.",
                "confidence": 0.95,
                "tags": ["cpu", "windows", "sop", "perf"]
            },
            {
                "id": "KB-SOP-002",
                "title": "Memory Leak in Client Application",
                "symptoms": "Available RAM drops below 5% (RAM Usage >95%). Pages are swapped to disk, causing excessive disk active time and high response times.",
                "root_cause": "A user-space or background monitoring application has a memory leak, steadily consuming resources without releasing them.",
                "resolution": "Open Deep Diagnostics -> Processes to identify the process with high memory usage. Send a CMD restart or taskkill command for that process, or initiate a soft reboot if critical system process.",
                "confidence": 0.90,
                "tags": ["ram", "leak", "sop", "windows"]
            },
            {
                "id": "KB-SOP-003",
                "title": "Disk Space Running Out (Drive C:)",
                "symptoms": "Free space on the primary system drive (C:) is less than 500MB. Windows becomes unstable, Windows Update fails, and logs cannot be written.",
                "root_cause": "Accumulation of temporary files in %TEMP%, C:\\Windows\\Temp, or large user download folders and crash dumps.",
                "resolution": "Execute disk cleanup command via Remote command tool: 'cleanmgr /sagerun:1' or manually purge temp folders and IIS logs. Delete older crash logs.",
                "confidence": 0.88,
                "tags": ["disk", "cleanup", "storage", "sop"]
            },
            {
                "id": "KB-GLD-001",
                "title": "NATS JetStream Deserialization Error",
                "symptoms": "Python AI Core console log shows Deserialization error when parsing incoming telemetry stream messages. Messages are sent to Dead Letter Queue (DLQ).",
                "root_cause": "Schema mismatch between Go JSON marshaler (encoding numbers as float64) and Python JSON decoder expecting structured integer timestamps or different dictionary keys.",
                "resolution": "Ensure Go Struct tag maps to json:\"timestamp\" matching Python's ISO string parser. Add safe default fallback keys in python_ai_core/ai_supervisor.py.",
                "confidence": 0.98,
                "tags": ["nats", "json", "deserialization", "golden"]
            },
            {
                "id": "KB-GLD-002",
                "title": "Printer Offline or Queue Stalled",
                "symptoms": "Multiple documents in printer queue stay in 'Spooling' or 'Printing' state indefinitely. Printer status card in dashboard shows OFFLINE.",
                "root_cause": "The printer spooler service on the host computer is hung or the network connection to the network printer IP is disconnected.",
                "resolution": "Restart the Print Spooler service on the hosting Windows device using PowerShell command: 'Restart-Service -Name Spooler -Force'. Confirm network ping to printer IP.",
                "confidence": 0.96,
                "tags": ["printer", "spooler", "windows", "golden"]
            },
            {
                "id": "KB-HIST-001",
                "title": "VPN Disconnect on PC-MKT-NUC",
                "symptoms": "Windows agent drops off from main NOC dashboard (ONLINE -> OFFLINE). Gateway IP is reachable but DNS resolution to internal servers fail.",
                "root_cause": "FortiClient/Cisco VPN client disconnected due to network jitter or session expiration, and did not auto-reconnect.",
                "resolution": "Initiate automated PowerShell command via relay to trigger connection script or launch local reconnect task: 'rasdial \"WorkVPN\" username password'.",
                "confidence": 0.85,
                "tags": ["vpn", "network", "disconnect", "history"]
            },
            {
                "id": "KB-HIST-002",
                "title": "Nats connection timeout in python_ai_core",
                "symptoms": "python-ai-core container crashes or enters restart loop with ConnectionRefusedError to 127.0.0.1:4222.",
                "root_cause": "NATS connection address in python script was hardcoded to localhost instead of nats container name.",
                "resolution": "Update NATS connection string to use environment variable NATS_URL, default value nats://nats:4222.",
                "confidence": 0.99,
                "tags": ["nats", "python", "config", "history"]
            },
            {
                "id": "KB-SOP-004",
                "title": "Nginx Port Conflicts with Portainer",
                "symptoms": "Cannot start Nginx or Portainer container due to 'bind: address already in use' error on port 9443.",
                "root_cause": "Both Nginx (OSI portal) and Portainer HTTPS services default to binding on host port 9443.",
                "resolution": "Map Portainer's HTTPS port to 9444 instead of 9443 in docker-compose.yml. Leave Nginx on port 9443.",
                "confidence": 0.97,
                "tags": ["nginx", "portainer", "port-conflict", "sop"]
            }
        ]

        print("Inserting records...")
        for item in knowledge_items:
            cur.execute("""
                INSERT INTO knowledge_vectors (incident_id, title, symptoms, root_cause, resolution, confidence, tags)
                VALUES (%s, %s, %s, %s, %s, %s, %s);
            """, (
                item["id"],
                item["title"],
                item["symptoms"],
                item["root_cause"],
                item["resolution"],
                item["confidence"],
                item["tags"]
            ))
        
        print("Successfully seeded 8 knowledge items into knowledge_vectors table.")
        cur.close()
        conn.close()

    except Exception as e:
        print(f"Error seeding database: {e}")

if __name__ == "__main__":
    seed_database()
