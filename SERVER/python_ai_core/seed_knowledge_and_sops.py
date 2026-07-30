import os
import sys
import psycopg2
import math
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("SEED_KNOWLEDGE_SOP")

try:
    from google import genai
except ImportError:
    genai = None

def get_gemini_embedding(text: str, api_key: str):
    """Generate 768-dim L2-normalized embedding using Gemini API or local TF-IDF fallback."""
    if genai and api_key and "your_gemini_api" not in api_key and len(api_key) > 20:
        try:
            client = genai.Client(api_key=api_key)
            emb_res = client.models.embed_content(
                model="gemini-embedding-001",
                contents=text
            )
            if emb_res and emb_res.embeddings:
                raw_vals = list(emb_res.embeddings[0].values)
                sub = raw_vals[:768]
                norm = math.sqrt(sum(x*x for x in sub)) or 1.0
                return [x / norm for x in sub]
        except Exception as e:
            logger.warning(f"Gemini embedding API failed ({e}), generating deterministic fallback vector.")

    # Local TF-IDF Hash Fallback (768-dim)
    import hashlib
    words = text.lower().split()
    vec = [0.0] * 768
    for i, word in enumerate(words):
        h = int(hashlib.md5(word.encode()).hexdigest(), 16)
        idx = h % 768
        val = ((h >> 8) % 1000) / 1000.0 - 0.5
        vec[idx] += val
    norm = math.sqrt(sum(x*x for x in vec)) or 1.0
    return [x / norm for x in vec]

def seed_all():
    db_host = os.getenv("DB_HOST", "postgres")
    db_port = os.getenv("DB_PORT", "5432")
    db_name = os.getenv("DB_NAME", "osi_system")
    db_user = os.getenv("DB_USER", "postgres")
    db_password = os.getenv("DB_PASSWORD", "postgres")
    api_key = os.getenv("GEMINI_API_KEY", "")

    logger.info(f"Connecting to database {db_name} at {db_host}:{db_port}...")
    conn = psycopg2.connect(
        host=db_host,
        port=db_port,
        database=db_name,
        user=db_user,
        password=db_password
    )
    conn.autocommit = True
    cur = conn.cursor()

    # 1. High Quality Knowledge Items
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
        },
        {
            "id": "KB-SOP-005",
            "title": "PostgreSQL Connection Pool Exhausted Remediation",
            "symptoms": "ERROR: Failed to get connection from pool: connection pool exhausted from Python AI containers.",
            "root_cause": "Idle connections from AI microservices not returned to pool, exceeding max_connections = 100.",
            "resolution": "Configure ThreadedConnectionPool(min=1, max=5), TCP keepalives, and set idle_in_transaction_session_timeout = 300000ms in postgresql.conf.",
            "confidence": 0.99,
            "tags": ["postgresql", "pool", "database", "sop"]
        }
    ]

    logger.info("--- 1. Seeding knowledge_vectors ---")
    for item in knowledge_items:
        text = f"{item['title']} {item['symptoms']} {item['root_cause']} {item['resolution']}"
        vec = get_gemini_embedding(text, api_key)
        vec_str = "[" + ",".join(map(str, vec)) + "]"

        cur.execute("""
            INSERT INTO knowledge_vectors (incident_id, title, symptoms, root_cause, resolution, embedding, confidence, tags, status, created_at)
            VALUES (%s, %s, %s, %s, %s, %s::vector, %s, %s, 'GOLDEN', NOW())
            ON CONFLICT (incident_id) DO UPDATE SET
                title = EXCLUDED.title,
                symptoms = EXCLUDED.symptoms,
                root_cause = EXCLUDED.root_cause,
                resolution = EXCLUDED.resolution,
                embedding = EXCLUDED.embedding,
                confidence = EXCLUDED.confidence,
                tags = EXCLUDED.tags,
                status = 'GOLDEN';
        """, (
            item["id"], item["title"], item["symptoms"], item["root_cause"],
            item["resolution"], vec_str, item["confidence"], item["tags"]
        ))
        logger.info(f"✅ Seeded knowledge_vectors item: {item['id']} ({item['title']})")

    # 2. Seed Governance SOPs
    logger.info("--- 2. Seeding governance_sops ---")
    governance_sops = [
        ("SOP-CPU-01", "SOP Remediasi CPU Tinggi", "Autonomous AI Ops Prosedur pembersihan dan penanganan CPU > 95%", "Remediasi CPU Tinggi", "SOP-CPU-01", "Pemeriksaan Deep Diagnostics -> Taskkill proses abnormal -> Restart Winmgmt", "HIGH_CPU", "ACTIVE", 0.95),
        ("SOP-MEM-01", "SOP Remediasi Memory Leak", "Prosedur penanganan kebocoran RAM pada Windows Agent", "Remediasi RAM", "SOP-MEM-01", "Identifikasi RAM leak -> Soft restart app -> Flush standby list", "RAM_LEAK", "ACTIVE", 0.92),
        ("SOP-DSK-01", "SOP Remediasi Disk Full", "Pembersihan drive C: saat sisa ruang < 500MB", "Remediasi Disk Full", "SOP-DSK-01", "Execution cleanmgr /sagerun:1 -> Purge temp logs", "DISK_FULL", "ACTIVE", 0.90),
        ("SOP-PRT-01", "SOP Restart Print Spooler", "Prosedur auto-restart Spooler service saat printer stall", "Remediasi Printer", "SOP-PRT-01", "Restart-Service -Name Spooler -Force", "PRINTER_STALL", "ACTIVE", 0.96),
        ("SOP-NET-01", "SOP Reconnect VPN Gateway", "Prosedur pemulihan koneksi VPN agent secara otomatis", "Remediation Network VPN", "SOP-NET-01", "Trigger rasdial reconnect script via relay", "VPN_DISCONNECT", "ACTIVE", 0.88),
        ("SOP-DB-01", "SOP PostgreSQL Pool Self-Healing", "Prosedur otomatis penanganan pool exhaustion pada PostgreSQL", "Remediasi Database", "SOP-DB-01", "Terminate idle connections -> Enforce pool max 5 per service", "POOL_EXHAUSTED", "ACTIVE", 0.99)
    ]

    for name, title, description, desc, trigger, remediation, tag, status, conf in governance_sops:
        cur.execute("""
            INSERT INTO governance_sops (name, title, description, "desc", trigger, remediation, status, confidence, created_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON CONFLICT DO NOTHING;
        """, (name, title, description, desc, trigger, remediation, status, conf))
        logger.info(f"✅ Seeded governance_sop: {name}")

    # 3. Seed RAG v2 Document Store (knowledge_v2_documents & knowledge_v2_embeddings)
    logger.info("--- 3. Seeding RAG v2 Document Store ---")
    v2_docs = [
        ("DOC-RAG-001", "COMPUTE", "SOP", "Prosedur Remediation CPU High Utilization", 3, "TEXT", True, "APPROVED", "CRITICAL"),
        ("DOC-RAG-002", "MEMORY", "SOP", "Prosedur Penanganan Memory Leak Client", 3, "TEXT", True, "APPROVED", "HIGH"),
        ("DOC-RAG-003", "STORAGE", "SOP", "Prosedur Disk Cleanup & Log Purge", 2, "TEXT", True, "APPROVED", "MEDIUM"),
        ("DOC-RAG-004", "DATABASE", "SOP", "Prosedur Resiliensi Connection Pool PostgreSQL", 4, "TEXT", True, "APPROVED", "CRITICAL")
    ]

    for doc_id, dom_layer, cat, title, osi_l, mm_type, auto_allow, status, sev in v2_docs:
        cur.execute("""
            INSERT INTO knowledge_v2_documents (doc_id, domain_layer, category, title, osi_layer, multimodal_type, automation_allowed, status, severity, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT (doc_id) DO UPDATE SET
                title = EXCLUDED.title,
                status = EXCLUDED.status,
                updated_at = NOW();
        """, (doc_id, dom_layer, cat, title, osi_l, mm_type, auto_allow, status, sev))

        # Insert vector embedding into knowledge_v2_embeddings
        vec = get_gemini_embedding(f"{title} {cat} {dom_layer}", api_key)
        vec_str = "[" + ",".join(map(str, vec)) + "]"
        cur.execute("""
            INSERT INTO knowledge_v2_embeddings (doc_id, embedding, embedding_model, chunk_text, domain_layer)
            VALUES (%s, %s::vector, 'gemini-embedding-001', %s, %s);
        """, (doc_id, vec_str, f"{title} - {dom_layer} {cat}", dom_layer))
        logger.info(f"✅ Seeded RAG v2 Document & Embedding: {doc_id} ({title})")

    # 4. Seed sop_metadata & validated_knowledge_base
    logger.info("--- 4. Seeding sop_metadata & validated_knowledge_base ---")
    sop_meta = [
        ("SOP-CPU-01", "SOP-CPU-01", 0.95, 12, 0),
        ("SOP-MEM-01", "SOP-MEM-01", 0.92, 8, 0),
        ("SOP-DSK-01", "SOP-DSK-01", 0.90, 15, 0),
        ("SOP-DB-01",  "SOP-DB-01",  0.99, 20, 0)
    ]

    for sid, sname, w, succ, fail in sop_meta:
        cur.execute("""
            INSERT INTO sop_metadata (sop_id, sop_name, initial_weight, total_success, total_failure, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, NOW(), NOW())
            ON CONFLICT DO NOTHING;
        """, (sid, sname, w, succ, fail))

    validated_kb = [
        ("HIGH_CPU", "CPU Usage > 95%", "High CPU utilization process", "TASKKILL process / Restart Winmgmt", "PROD", "Autonomous AI Ops", 0.98),
        ("RAM_LEAK", "RAM Usage > 95%", "Memory leak in user process", "Soft restart app", "PROD", "Autonomous AI Ops", 0.95),
        ("POOL_EXHAUSTED", "Postgres pool exhausted", "Idle connections exceeded pool limit", "Set ThreadedConnectionPool(1,5)", "PROD", "Database Engineering", 0.99)
    ]

    for itype, symp, rc, rem, env, val_by, conf in validated_kb:
        vec = get_gemini_embedding(f"{itype} {symp} {rc} {rem}", api_key)
        vec_str = "[" + ",".join(map(str, vec)) + "]"
        cur.execute("""
            INSERT INTO validated_knowledge_base (issue_type, root_cause, environment, last_validated_by, confidence, embedding_vector, created_at, updated_at)
            VALUES (%s, %s, %s, %s, %s, %s::vector, NOW(), NOW());
        """, (itype, rc, env, val_by, conf, vec_str))

    cur.close()
    conn.close()
    logger.info("🎉 SUCCESS! SOP Registry & RAG Knowledge Base seeding complete!")

if __name__ == "__main__":
    seed_all()
