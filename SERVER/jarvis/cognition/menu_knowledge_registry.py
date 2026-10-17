"""
menu_knowledge_registry.py
===========================
Registri Pengetahuan Terstruktur untuk 26 Menu Panel NOC & Sub-Modulnya.
Memungkinkan Jarvis Voice & Chat Assistant menjawab pertanyaan penjelas fungsi,
mengetahui kueri data live, serta mengeksekusi aksi operasional secara presisi.
"""

from typing import Dict, Any, List, Optional

MENU_KNOWLEDGE_REGISTRY: Dict[str, Dict[str, Any]] = {
    # ── KATEGORI 1: DASHBOARD & OVERVIEW ───────────────────────────────────
    "jarvis_voice_overview": {
        "panel_id": "jarvis_voice_overview",
        "category": "Dashboard & Overview",
        "title": "JARVIS Voice Overview",
        "description": "Panel kontrol utama subsistem suara dan AI Assistant Jarvis. Menampilkan visualisasi 3D Mesh Avatar (WaltHead.obj), spektrum frekuensi audio, status pengenal suara (Faster-Whisper STT), sintesis suara (Kokoro-TTS), dan wake-word detector.",
        "submodules": ["3D Avatar Visualizer", "Audio Spectrum Analyzer", "STT Provider Engine", "TTS Voice Synthesizer", "OpenWakeWord Detector"],
        "kpis": ["STT Latency (ms)", "TTS Latency (ms)", "Wake-Word Detection Confidence (%)", "Active Voice Persona"],
        "available_actions": [
            {"action_code": "TEST_AUDIO_SYNTHESIS", "description": "Uji coba sintesis suara Jarvis", "requires_hitl": False},
            {"action_code": "CHANGE_VOICE_PERSONA", "description": "Ganti karakter/persona suara Jarvis", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/jarvis/health"
    },
    "overview": {
        "panel_id": "overview",
        "category": "Dashboard & Overview",
        "title": "System Overview Dashboard",
        "description": "Dashboard eksekutif yang menyajikan kuis dan indikator kesehatan sistem secara keseluruhan, ketersediaan SLA 99.9%, statistik insiden aktif, rasio remedi otomatis, dan total perangkat fleet terhubung.",
        "submodules": ["Executive SLA Gauge", "Active Incident Summary Card", "Self-Healing Efficiency Metric", "Fleet Health Score Card"],
        "kpis": ["SLA Availability (%)", "Total Open Incidents", "Self-Healing Success Rate (%)", "Online Host Percentage"],
        "available_actions": [
            {"action_code": "REFRESH_OVERVIEW_METRICS", "description": "Muat ulang metrik overview real-time", "requires_hitl": False},
            {"action_code": "EXPORT_OVERVIEW_REPORT", "description": "Ekspor laporan ringkasan sistem ke PDF/JSON", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/overview/metrics"
    },
    "exec_timeline": {
        "panel_id": "exec_timeline",
        "category": "Dashboard & Overview",
        "title": "Execution Timeline",
        "description": "Visualisasi garis waktu (Gantt Chart) dari seluruh tindakan pemulihan (remediation actions) yang dieksekusi oleh AI Agent secara kronologis beserta timestamp dan status hasilnya.",
        "submodules": ["Remediation Gantt Chart", "Execution Log Streamer", "Action Duration Tracker", "Failure Reason Inspector"],
        "kpis": ["Total Executions (24h)", "Successful Remediations", "Failed Remediations", "Average Execution Time (sec)"],
        "available_actions": [
            {"action_code": "FILTER_TIMELINE_BY_STATUS", "description": "Filter timeline berdasarkan status FAILED/SUCCESS", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/execution/timeline"
    },
    "storage": {
        "panel_id": "storage",
        "category": "Dashboard & Overview",
        "title": "Storage & Memory Statistics",
        "description": "Monitoring kapasitas penyimpanan disk database PostgreSQL, ukuran indeks PGVector GraphRAG L1-L7, memori cache Redis, dan log storage terdistribusi.",
        "submodules": ["PostgreSQL Storage Monitor", "PGVector Index Inspector", "Redis Vector Cache Stats", "Log Retention Manager"],
        "kpis": ["Postgres DB Size (GB)", "PGVector Index Size (MB)", "Redis Cache Hit Ratio (%)", "Free Disk Space (%)"],
        "available_actions": [
            {"action_code": "PURGE_DISTRIBUTED_CACHE", "description": "Bersihkan cache log terdistribusi", "requires_hitl": True},
            {"action_code": "OPTIMIZE_VECTOR_INDEX", "description": "Optimalkan indeks vector PGVector", "requires_hitl": True}
        ],
        "live_query_endpoint": "/api/storage/stats"
    },

    # ── KATEGORI 2: FLEET & INFRASTRUCTURE HEALTH ──────────────────────────
    "monitoring": {
        "panel_id": "monitoring",
        "category": "Fleet & Infrastructure Health",
        "title": "Live Telemetry Monitoring",
        "description": "Monitoring stream telemetri real-time untuk CPU utilisation, RAM consumption, Network I/O throughput, dan Disk I/O dari seluruh endpoint agent yang terhubung.",
        "submodules": ["Realtime CPU Sparkline", "RAM Consumption Gauge", "Network Throughput Monitor", "Disk I/O Latency Graph"],
        "kpis": ["Cluster Avg CPU (%)", "Cluster Avg RAM (%)", "Total Network Bandwidth (Mbps)", "Max Disk IOPS"],
        "available_actions": [
            {"action_code": "SET_TELEMETRY_POLLING_RATE", "description": "Ubah interval polling telemetri live", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/metrics/live"
    },
    "fleet": {
        "panel_id": "fleet",
        "category": "Fleet & Infrastructure Health",
        "title": "Fleet Management",
        "description": "Manajemen inventaris perangkat (PC dan Server), pendaftaran agen baru, pengelompokan host (Host Groups), pemetaan IP Address, dan trigger aksi remote.",
        "submodules": ["Device Inventory Grid", "Agent Registration Wizard", "Host Group Classifier", "Remote Action Dispatcher"],
        "kpis": ["Total Registered Devices", "Online Devices", "Offline Devices", "Pending Registrations"],
        "available_actions": [
            {"action_code": "ADD_FLEET_DEVICE", "description": "Daftarkan perangkat baru ke fleet", "requires_hitl": False},
            {"action_code": "DELETE_FLEET_DEVICE", "description": "Hapus perangkat dari inventaris fleet", "requires_hitl": True},
            {"action_code": "REBOOT_REMOTE_DEVICE", "description": "Restart perangkat remote", "requires_hitl": True}
        ],
        "live_query_endpoint": "/api/fleet"
    },
    "server": {
        "panel_id": "server",
        "category": "Fleet & Infrastructure Health",
        "title": "Server Infrastructure Health",
        "description": "Monitoring khusus server-server infrastruktur inti (Ingestion Server, AI Core, NATS JetStream Broker, Postgres DB, Redis Server, Nginx HA Proxy).",
        "submodules": ["Ingestion Server Status", "NATS Broker Health", "Database Replica Status", "Nginx Proxy Load Balancer"],
        "kpis": ["Ingestion Port 18800 Throughput", "NATS JetStream Status", "Postgres Connection Pool", "Redis Memory Usage"],
        "available_actions": [
            {"action_code": "RESTART_INTERNAL_SERVICE", "description": "Restart service server internal", "requires_hitl": True}
        ],
        "live_query_endpoint": "/api/health/services"
    },
    "fleet_config": {
        "panel_id": "fleet_config",
        "category": "Fleet & Infrastructure Health",
        "title": "Fleet Global Configuration",
        "description": "Pengaturan konfigurasi global agent edge, ambang batas alarm (CPU/RAM threshold), frekuensi heartbeat, dan opsi auto-update binary OTA.",
        "submodules": ["Alarm Threshold Configurator", "Heartbeat Interval Settings", "OTA Auto-Update Policy", "Log Level Controller"],
        "kpis": ["CPU Alarm Threshold (%)", "RAM Alarm Threshold (%)", "Heartbeat Timeout (s)", "OTA Release Version"],
        "available_actions": [
            {"action_code": "UPDATE_FLEET_THRESHOLD", "description": "Ubah ambang batas alarm CPU/RAM global", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/fleet/config"
    },
    "pchealth": {
        "panel_id": "pchealth",
        "category": "Fleet & Infrastructure Health",
        "title": "PC Health & Deep Diagnostics",
        "description": "Diagnostik mendalam PC klien: daftar proses aktif, utilitas RAM/CPU per-proses, status port USB (terdeteksi/terkunci), diagnosa koneksi Wi-Fi (RSSI), dan EventLog error Windows.",
        "submodules": ["Process Tree Explorer", "USB Port Lock Controller", "Wi-Fi RSSI Diagnostics", "Windows EventLog Analyzer"],
        "kpis": ["Active Process Count", "Top RAM Consumer", "USB Lock Status", "Wi-Fi Signal Strength (dBm)"],
        "available_actions": [
            {"action_code": "KILL_PROCESS", "description": "Hentikan proses abnormal di PC remote", "requires_hitl": True},
            {"action_code": "TOGGLE_USB_LOCK", "description": "Kunci atau buka port USB di PC remote", "requires_hitl": True}
        ],
        "live_query_endpoint": "/api/fleet/pchealth"
    },
    "printer": {
        "panel_id": "printer",
        "category": "Fleet & Infrastructure Health",
        "title": "Printer Status & Spooler Management",
        "description": "Monitoring status spooler printer lokal dan jaringan, jumlah antrean cetak (print queue), deteksi kertas habis atau jammed, serta aksi restart spooler.",
        "submodules": ["Print Queue Monitor", "Spooler Service Watchdog", "Printer Connectivity Checker", "Paper Jam Alert Panel"],
        "kpis": ["Active Print Queues", "Stopped Spooler Count", "Paper Jam Alerts", "Offline Printers"],
        "available_actions": [
            {"action_code": "RESTART_PRINT_SPOOLER", "description": "Restart service print spooler di target host", "requires_hitl": False},
            {"action_code": "CLEAR_PRINT_QUEUE", "description": "Bersihkan antrean cetak yang stuck", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/fleet/printer"
    },
    "agent_health": {
        "panel_id": "agent_health",
        "category": "Fleet & Infrastructure Health",
        "title": "AI Agent Health & RTT",
        "description": "Monitoring status kesehatan dan latensi Round Trip Time (RTT) koneksi dari setiap instance agen edge (Linux & Windows Daemon).",
        "submodules": ["RTT Latency Monitor", "Agent Heartbeat Tracker", "Package Drop Rate Checker", "OTA Binary Manager"],
        "kpis": ["Average Agent RTT (ms)", "Healthy Agents (%)", "Unresponsive Agents", "Agent Version Distribution"],
        "available_actions": [
            {"action_code": "TRIGGER_OTA_UPDATE", "description": "Trigger update binary OTA ke seluruh agent", "requires_hitl": True}
        ],
        "live_query_endpoint": "/api/agent/rtt"
    },

    # ── KATEGORI 3: INCIDENT & RCA ENGINE ──────────────────────────────────
    "incident": {
        "panel_id": "incident",
        "category": "Incident & RCA Engine",
        "title": "Incident Triage",
        "description": "Triase dan manajemen insiden real-time. Mengategorikan insiden berdasarkan severity (CRITICAL, WARNING, INFO), penugasan operator, dan pembaruan lifecycle insiden.",
        "submodules": ["Incident Severity Grid", "Operator Assignment Board", "Lifecycle State Machine", "SLA Breach Countdown"],
        "kpis": ["Critical Incidents", "Warning Incidents", "Unassigned Incidents", "Avg Time to Resolve (min)"],
        "available_actions": [
            {"action_code": "UPDATE_INCIDENT_STATUS", "description": "Ubah status insiden (OPEN -> IN_PROGRESS -> RESOLVED)", "requires_hitl": False},
            {"action_code": "ASSIGN_INCIDENT_OPERATOR", "description": "Tugaskan insiden ke tim/operator NOC", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/incidents"
    },
    "rca": {
        "panel_id": "rca",
        "category": "Incident & RCA Engine",
        "title": "Ground Truth & Root Cause Analysis",
        "description": "Analisis Akar Masalah berbasis AI. Menampilkan hipotesis utama insiden, bukti telemetri (causal evidence), perbandingan counterfactual, rekomendasi SOP, dan confidence score.",
        "submodules": ["Causal Evidence Graph", "Counterfactual Comparator", "SOP Recommendation Engine", "Confidence Score Badge"],
        "kpis": ["RCA Accuracy (%)", "Primary Hypothesis Confidence (%)", "Causal Nodes Identified", "Recommended SOPs"],
        "available_actions": [
            {"action_code": "TRIGGER_RCA_ANALYSIS", "description": "Jalankan engine analisis RCA untuk insiden tertentu", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/rca/analysis"
    },
    "event_correlation": {
        "panel_id": "event_correlation",
        "category": "Incident & RCA Engine",
        "title": "Event Correlation Engine",
        "description": "Korelasi event dari berbagai sumber log (Syslog, Windows EventLog, Network drops) untuk mengelompokkan alert storm paralel yang berasal dari masalah awal yang sama.",
        "submodules": ["Alert Storm Suppressor", "Cross-System Log Correlator", "Correlation Cluster Map", "Root Cause Event Deduplicator"],
        "kpis": ["Suppressed Alert Count", "Correlation Efficiency (%)", "Active Clusters", "Log Ingestion Rate"],
        "available_actions": [
            {"action_code": "MERGE_CORRELATED_EVENTS", "description": "Gabungkan event ter-korelasi menjadi satu insiden", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/events/correlation"
    },
    "unified_dag": {
        "panel_id": "unified_dag",
        "category": "Incident & RCA Engine",
        "title": "Unified Graphs (DAG)",
        "description": "Visualisasi Graf Terarah (Directed Acyclic Graph / DAG) ketergantungan antar sistem, aplikasi, dan infrastruktur untuk melacak rute propagasi dampak insiden (blast radius).",
        "submodules": ["Dependency Graph Renderer", "Blast Radius Evaluator", "Critical Path Highlighter", "Node Failure Simulator"],
        "kpis": ["Total Graph Nodes", "Total Graph Edges", "Affected Services Count", "Max Blast Radius Score"],
        "available_actions": [
            {"action_code": "HIGHLIGHT_BLAST_RADIUS", "description": "Sorot rute dampak kegagalan pada graf ketergantungan", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/rca/dag"
    },

    # ── KATEGORI 4: AI LIFECYCLE & TRAINING ────────────────────────────────
    "ai": {
        "panel_id": "ai",
        "category": "AI Lifecycle & Training",
        "title": "AI Panel Overview",
        "description": "Summary performa AI OS: akurasi rekomendasi RCA, rasio sukses remedi otomatis, penggunaan token LLM, dan efisiensi Semantic Vector Cache.",
        "submodules": ["AI Performance Radar", "Token Cost Meter", "Semantic Cache Efficiency Gauge", "Consensus Score Inspector"],
        "kpis": ["RCA Recommendation Accuracy (%)", "Auto-Remediation Rate (%)", "Semantic Cache Hit Rate (%)", "Total Token Usage"],
        "available_actions": [
            {"action_code": "RESET_AI_CACHE_STATS", "description": "Bersihkan statistik performa cache AI", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/ai/overview"
    },
    "ai_lifecycle_topology": {
        "panel_id": "ai_lifecycle_topology",
        "category": "AI Lifecycle & Training",
        "title": "AI Lifecycle Topology",
        "description": "Visualisasi aliran ekosistem AI dari pengumpulan data telemetri, Intent Classification, Agentic RAG, Planner-Critic Consensus, hingga Governance Guard.",
        "submodules": ["Live Data Pipeline Flow", "NLU Intent Pipeline Node", "Agentic RAG Node", "Governance Guard Node"],
        "kpis": ["Pipeline Throughput (req/s)", "Avg Pipeline Latency (ms)", "Active Agent Workers", "Consensus Pass Rate (%)"],
        "available_actions": [
            {"action_code": "RELOAD_PIPELINE_TOPOLOGY", "description": "Muat ulang topologi node alur kerja AI", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/ai/lifecycle"
    },
    "models": {
        "panel_id": "models",
        "category": "AI Lifecycle & Training",
        "title": "Model Configuration & Router",
        "description": "Pengaturan LLM Provider (Google Gemini 1.5 Pro/Flash, OpenAI GPT-4o, Groq Llama-3, DeepSeek), ambang batas suhu (temperature), max token, dan aturan fallback router.",
        "submodules": ["LLM Provider Selector", "Temperature Slider", "Fallback Router Manager", "Token Rate Limit Configurator"],
        "kpis": ["Active Primary LLM", "Active Fallback LLM", "LLM Temperature Setting", "API Response Time (ms)"],
        "available_actions": [
            {"action_code": "SET_PRIMARY_LLM_MODEL", "description": "Ganti model LLM utama yang digunakan sistem", "requires_hitl": False},
            {"action_code": "UPDATE_LLM_TEMPERATURE", "description": "Ubah batas suhu (temperature) kreativitas LLM", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/ai/models"
    },
    "training": {
        "panel_id": "training",
        "category": "AI Lifecycle & Training",
        "title": "Training Feedback & DPO Pipeline",
        "description": "Antarmuka umpan balik operator NOC (Thumb up/down, koreksi jawaban). Data dikumpulkan untuk sintesis DPO dataset dan fine-tuning model via LoRA pipeline.",
        "submodules": ["Operator Feedback Curation", "DPO Dataset Synthesizer", "LoRA Fine-Tuning Pipeline", "Model Quality Evaluator"],
        "kpis": ["Collected DPO Samples", "Operator Satisfaction (%)", "LoRA Fine-Tuning Status", "Evaluation Benchmark Score"],
        "available_actions": [
            {"action_code": "TRIGGER_DPO_SYNTHESIS", "description": "Jalankan pipeline sintesis DPO dataset", "requires_hitl": True}
        ],
        "live_query_endpoint": "/api/ai/feedback/stats"
    },
    "ai_decision_logs": {
        "panel_id": "ai_decision_logs",
        "category": "AI Lifecycle & Training",
        "title": "AI Decision Logs",
        "description": "Log audit transparan mengenai pertimbangan AI sebelum mengambil keputusan, mencakup prompt context, Planner output, Critic validation score, dan skema verifikasi.",
        "submodules": ["Prompt Inspector", "Planner Reasoning Output", "Critic Consensus Score", "Safety Validation Verification"],
        "kpis": ["Total Logged Decisions", "Planner-Critic Match Rate (%)", "Rejected Decisions Count", "Avg Reasoning Time (ms)"],
        "available_actions": [
            {"action_code": "FILTER_DECISION_LOGS", "description": "Filter log keputusan AI berdasarkan ID insiden", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/ai_decision_logs"
    },
    "playbooks": {
        "panel_id": "playbooks",
        "category": "AI Lifecycle & Training",
        "title": "Playbook Studio & SOP Manager",
        "description": "Editor visual dan manager SOP (Standard Operating Procedure). Memungkinkan penyusunan skrip mitigasi otomatis, pengujian canary deployment, dan pemicu insiden.",
        "submodules": ["Visual SOP Editor", "Automated Remediation Script Studio", "Canary Deployment Simulator", "Trigger Rule Manager"],
        "kpis": ["Active SOP Count", "Automated Playbooks", "Avg SOP Confidence", "Canary Deploy Pass Rate (%)"],
        "available_actions": [
            {"action_code": "RUN_SOP_CANARY_TEST", "description": "Jalankan pengujian canary deployment untuk SOP tertentu", "requires_hitl": True}
        ],
        "live_query_endpoint": "/api/sops"
    },

    # ── KATEGORI 5: SECURITY, POLICY & GOVERNANCE ──────────────────────────
    "gov": {
        "panel_id": "gov",
        "category": "Security, Policy & Governance",
        "title": "AI Governance Center & HITL Queue",
        "description": "Pusat kendali aturan keamanan AI. Menegakkan 5 Golden Rules (mencegah komando berbahaya seperti rm -rf /) dan mengelola antrean persetujuan Human-in-the-Loop (HITL).",
        "submodules": ["5 Golden Rules Engine", "HITL Approval Queue Board", "Action Permissibility Matrix", "Policy Violation Inspector"],
        "kpis": ["Pending HITL Approvals", "Enforced Golden Rules", "Blocked Dangerous Commands", "SLA Approval Rate (%)"],
        "available_actions": [
            {"action_code": "APPROVE_HITL_ITEM", "description": "Setujui aksi pemulihan insiden di HITL queue", "requires_hitl": True},
            {"action_code": "REJECT_HITL_ITEM", "description": "Tolak persetujuan aksi pemulihan di HITL queue", "requires_hitl": True}
        ],
        "live_query_endpoint": "/api/governance/rules"
    },
    "rbac": {
        "panel_id": "rbac",
        "category": "Security, Policy & Governance",
        "title": "RBAC Policies & User Management",
        "description": "Manajemen Hak Akses Berbasis Peran (RBAC) terintegrasi dengan Active Directory/LDAP. Mendukung hirarki role: superadmin, admin, noc_engineering, operator, dan viewer.",
        "submodules": ["Role Hierarchy Matrix", "User Assignment Table", "LDAP Sync Connector", "Permission Granularity Panel"],
        "kpis": ["Active Users Count", "Assigned Superadmins", "Assigned Operators", "LDAP Sync Status"],
        "available_actions": [
            {"action_code": "UPDATE_USER_ROLE", "description": "Ubah peran/role hak akses pengguna", "requires_hitl": True}
        ],
        "live_query_endpoint": "/api/rbac/roles"
    },
    "security_policies": {
        "panel_id": "security_policies",
        "category": "Security, Policy & Governance",
        "title": "Security Policies & PII Redactor",
        "description": "Aturan enkripsi payload agent HMAC-HS256, kebijakan redaksi otomatis data sensitif/PII (PII Redactor), dan pembatasan rate limit IP.",
        "submodules": ["HMAC Token Validator", "PII Redaction Rules Engine", "IP Rate Limiter Configurator", "Security Audit Log Stream"],
        "kpis": ["PII Redaction Status", "HMAC Verification Rate (%)", "Blocked IP Addresses", "WAF Block Count"],
        "available_actions": [
            {"action_code": "TOGGLE_PII_REDACTION", "description": "Aktifkan atau nonaktifkan mode PII Redactor", "requires_hitl": True}
        ],
        "live_query_endpoint": "/api/security/policies"
    },
    "evidence": {
        "panel_id": "evidence",
        "category": "Security, Policy & Governance",
        "title": "Evidence Explorer & Digital Forensics",
        "description": "Penjelajah bukti audit digital insiden. Menyimpan snapshot memori, log sistem, dan telemetry dump saat insiden terjadi untuk kepatuhan audit forensik IT.",
        "submodules": ["Forensic Snapshot Viewer", "Memory Dump Analyzer", "Log Hash Integrity Checker", "Audit Evidence Exporter"],
        "kpis": ["Stored Evidence Bundles", "Tamper-Proof Audit Hashes", "Investigated Incidents", "Storage Usage (GB)"],
        "available_actions": [
            {"action_code": "GENERATE_EVIDENCE_BUNDLE", "description": "Buatkan paket bukti forensik digital untuk insiden", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/evidence/explorer"
    },
    "kgraph": {
        "panel_id": "kgraph",
        "category": "Security, Policy & Governance",
        "title": "Knowledge Graph & GraphRAG L1-L7",
        "description": "Visualisasi Graf Pengetahuan AI (GraphRAG L1-L7) berbasis PGVector & PostgreSQL yang merepresentasikan entitas IT, insiden historis, dan relasi penyebaran masalah.",
        "submodules": ["GraphRAG Layer L1-L7 Explorer", "PGVector Embedding Inspector", "Entity Contradiction Detector", "Knowledge Fabric Renderer"],
        "kpis": ["Total Graph Entities", "Total Graph Relationships", "Vector Embeddings Count", "Conflict Detections"],
        "available_actions": [
            {"action_code": "REINDEX_KNOWLEDGE_GRAPH", "description": "Re-index vector embeddings pada Knowledge Graph", "requires_hitl": True}
        ],
        "live_query_endpoint": "/api/cognitive_memory/graph"
    },
    "knowledge_center": {
        "panel_id": "knowledge_center",
        "category": "Security, Policy & Governance",
        "title": "Knowledge Center (RAG & SOP 2.0)",
        "description": "Pusat pencarian RAG dokumen vendor, runbook KEDB, dan sinkronisasi otomatis Markdown Vault Obsidian untuk pembaruan panduan penanganan masalah.",
        "submodules": ["Agentic RAG Search Bar", "Obsidian Vault Synchronizer", "KEDB Runbook Matcher", "Vendor Manual Store"],
        "kpis": ["Indexed RAG Documents", "Obsidian Sync Status", "KEDB Match Rate (%)", "Last Sync Timestamp"],
        "available_actions": [
            {"action_code": "SYNC_OBSIDIAN_VAULT", "description": "Jalankan sinkronisasi Obsidian SOP Vault sekarang", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/knowledge/rag/status"
    },

    # ── KATEGORI 6: TELEMETRY & STREAM LOGS ────────────────────────────────
    "smart_stream": {
        "panel_id": "smart_stream",
        "category": "Telemetry & Stream Logs",
        "title": "Smart Stream Logs & AI Filter",
        "description": "Viewer log real-time dengan kemampuan AI Noise Reduction & Deduplication. Menyaring ribuan baris log mentah menjadi sinyal insiden berharga.",
        "submodules": ["AI Log Noise Reducer", "Realtime Log Stream Viewer", "Log Keyword Filter Panel", "Log Severity Highlighter"],
        "kpis": ["Incoming Log Rate (logs/s)", "Deduplication Ratio (%)", "Filtered Signal Count", "Active Log Filters"],
        "available_actions": [
            {"action_code": "SET_SMART_LOG_FILTER", "description": "Terapkan filter log kata kunci pada smart stream", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/logs/smart"
    },
    "chat": {
        "panel_id": "chat",
        "category": "Telemetry & Stream Logs",
        "title": "Live Chat & Operator Hub",
        "description": "Hub komunikasi real-time antar Operator NOC dan AI Assistant via WebSocket & Redis Pub/Sub. Mendukung kolaborasi tim dan pesan broadcast.",
        "submodules": ["NOC Operator Chat Room", "Redis Pub/Sub Connector", "Broadcast Message Sender", "Chat Session History"],
        "kpis": ["Connected Operators", "Active Chat Sessions", "Messages Sent Today", "Redis Sub Status"],
        "available_actions": [
            {"action_code": "BROADCAST_OPERATOR_MESSAGE", "description": "Kirim pesan broadcast ke semua operator NOC", "requires_hitl": False}
        ],
        "live_query_endpoint": "/api/dashboard_chat/sessions"
    },
    "nats_subjects": {
        "panel_id": "nats_subjects",
        "category": "Telemetry & Stream Logs",
        "title": "NATS Subjects Telemetry",
        "description": "Inspector lalu lintas message broker NATS JetStream. Menampilkan subject rate, consumer ack status, lag pesan, dan kesehatan kluster NATS.",
        "submodules": ["NATS Subject Stream Rate", "Consumer Ack Lag Inspector", "JetStream Stream Purger", "Cluster Connection Health"],
        "kpis": ["Active NATS Subjects", "Total Messages In/Out Rate", "Max Consumer Lag", "JetStream Storage (MB)"],
        "available_actions": [
            {"action_code": "PURGE_NATS_SUBJECT_STREAM", "description": "Bersihkan antrean pesan di subject NATS tertentu", "requires_hitl": True}
        ],
        "live_query_endpoint": "/api/nats/subjects"
    }
}


def get_menu_info(panel_id: str) -> Optional[Dict[str, Any]]:
    """Mengambil informasi detail registri pengetahuan untuk panel menu tertentu."""
    return MENU_KNOWLEDGE_REGISTRY.get(panel_id)


import re

def search_menu_by_query(query: str) -> Optional[str]:
    """Mencari ID panel menu berdasarkan kata kunci pertanyaan pengguna."""
    q = query.lower()
    q_normalized = re.sub(r'[^a-z0-9]', '', q)
    
    # Priority 1: Match panel_id or title normalized
    for panel_id, info in MENU_KNOWLEDGE_REGISTRY.items():
        panel_norm = re.sub(r'[^a-z0-9]', '', panel_id)
        title_norm = re.sub(r'[^a-z0-9]', '', info["title"].lower())
        if panel_norm in q_normalized or title_norm in q_normalized:
            return panel_id

    # Priority 2: Match submodules
    for panel_id, info in MENU_KNOWLEDGE_REGISTRY.items():
        for sub in info.get("submodules", []):
            sub_norm = re.sub(r'[^a-z0-9]', '', sub.lower())
            if sub_norm in q_normalized:
                return panel_id

    return None


