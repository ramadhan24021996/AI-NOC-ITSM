import os
import datetime

DOCS_DIR = "/home/it-itsm/AI/incident-analysis/ENTERPRISE_DOCS"

folders = [
    "architecture",
    "flowchart",
    "diagrams",
    "assets"
]

files = {
    "README.md": "# Enterprise AIOps Documentation\n\nWelcome to the official documentation for the NOC IT AI v3.0 Platform.",
    "EXECUTIVE_SUMMARY.md": "# Executive Summary\n\nThe NOC IT AI Platform is a deterministic, evidence-based Enterprise Diagnostic Engine designed to provide 0% hallucination root cause analysis, automated remediation, and zero-trust observability. It features a Multi-LLM architecture (Gemini, DeepSeek, Grok) and OpenTelemetry end-to-end tracing.",
    "SYSTEM_OVERVIEW.md": "# System Overview\n\n## Core Architecture\n- **Go Ingestion Server**: High-throughput telemetry ingestion.\n- **Python AI Core**: Multi-agent cognitive engine.\n- **NATS JetStream**: Real-time event bus.\n- **PostgreSQL + pgvector**: RAG knowledge base and event storage.\n- **Redis**: Caching and WebSocket presence.\n- **Agent**: Windows C# and Linux Go based agents.",
    "FULL_ARCHITECTURE.md": "# Full Architecture\n\nDetailed breakdown of all OSI layers, Nginx reverse proxy, WAF middleware, RBAC, and internal Docker networks.",
    "ARCHITECTURE_DECISION_RECORD.md": "# Architecture Decision Record (ADR)\n\n1. **Shift to Deterministic Causal DAG**: Replaced LLM guessing with strict physical dependency graphs.\n2. **Multi-LLM Strategy**: Segregated tasks to Gemini (Orchestration), DeepSeek (Code), and Grok (Real-time).",
    "COMPONENT_INVENTORY.md": "# Component Inventory\n\n- osi-frontend\n- osi-backend (postgres, redis, nats)\n- osi-ingestion-server\n- osi-python-ai-core\n- osi-agent-dist\n- osi-secure-relay\n- osi-telegram-bot",
    "AGENT_DOCUMENTATION.md": "# Agent Documentation\n\n## Windows Agent\n- **Role**: Telemetry gathering, Chaos Injection, Watchdog.\n- **Ports**: 18800 (TCP), 18802 (WS).",
    "SERVER_DOCUMENTATION.md": "# Server Documentation\n\n## Go Dashboard Server\nREST API and WebSocket server for real-time NOC UI.",
    "DASHBOARD_DOCUMENTATION.md": "# Dashboard Documentation\n\nReal-time monitoring, Incident Triage, AI Decision Logs, and Evidence Explorer.",
    "CHAT_SYSTEM_DOCUMENTATION.md": "# Chat System\n\nOpen Support Chat with 3-way synchronization (Telegram, NOC Dashboard, PC Client).",
    "TELEMETRY_DOCUMENTATION.md": "# Telemetry\n\nOpenTelemetry standard with `trace_id` and `span_id`.",
    "NETDATA_DOCUMENTATION.md": "# Netdata Integration\n\nExternal monitoring for server host metrics.",
    "AI_ENGINE_DOCUMENTATION.md": "# AI Engine\n\nMulti-Agent Consensus, Causal DAG, Anti-Hallucination Guard, and Policy Engine.",
    "RAG_DOCUMENTATION.md": "# RAG (Retrieval-Augmented Generation)\n\nUses `pgvector` for similarity search on historical incidents and Playbook logs.",
    "RCA_ENGINE_DOCUMENTATION.md": "# RCA Engine\n\nRoot Cause Analysis based on Evidence Score threshold (>40%).",
    "INCIDENT_ENGINE_DOCUMENTATION.md": "# Incident Engine\n\nLifecycle from Anomaly Detection -> Normalization -> Analysis -> Approval -> Remediation.",
    "WATCHDOG_DOCUMENTATION.md": "# Watchdog\n\nLocal agent service for process and resource monitoring.",
    "POLICY_ENGINE_DOCUMENTATION.md": "# Policy Engine\n\nBlast radius assessment and action safety verification.",
    "SECURITY_DOCUMENTATION.md": "# Security\n\nJWT, HMAC-SHA256, Zero-Trust Ingestion, WAF, Rate Limiting.",
    "DATABASE_DOCUMENTATION.md": "# Database\n\nPostgreSQL Schema: incidents, fleet_devices, ai_decision_logs, playbook_executions.",
    "API_DOCUMENTATION.md": "# API Documentation\n\nREST endpoints for incidents, fleet, rbac, and telemetry.",
    "EVENT_PIPELINE.md": "# Event Pipeline\n\nAgent -> NATS -> Ingestion -> Validation -> AI -> Dashboard.",
    "OBSERVABILITY.md": "# Observability\n\nTrace ID mapping from Edge (Browser/Agent) to Core (Postgres/Dashboard).",
    "DEPLOYMENT.md": "# Deployment\n\nDocker Compose based deployment with `osi-frontend` and `osi-backend` networks.",
    "RBAC.md": "# RBAC\n\nSuperadmin, NOC Engineer, L3 Support, Auditor.",
    "TELEGRAM.md": "# Telegram Integration\n\n3-way syncing, HitL (Human-in-the-Loop) approval via Telegram Inline Keyboards.",
    "PERFORMANCE.md": "# Performance\n\nP99 Latency tracking and NATS JetStream throughput.",
    "BACKUP_AND_RECOVERY.md": "# Backup & Recovery\n\nDatabase dump strategies and Rollback UI.",
    "KNOWN_LIMITATION.md": "# Known Limitations\n\nRequires continuous Agent network connectivity.",
    "CHANGELOG.md": "# Changelog\n\n- v3.0: Deterministic AI, Native Chaos Controller, Multi-LLM.",
    "AUDIT_CHECKLIST.md": "# Audit Checklist\n\n- [ ] Telemetry validation\n- [ ] Zero-trust API",
    "TROUBLESHOOTING.md": "# Troubleshooting\n\nCommon issues and DLQ (Dead Letter Queue) replays."
}

flowcharts = [
    "architecture.mmd", "telemetry.mmd", "incident.mmd", "ai_reasoning.mmd", 
    "watchdog.mmd", "browser_agent.mmd", "dashboard.mmd", "live_chat.mmd", 
    "authentication.mmd", "rca_engine.mmd", "event_pipeline.mmd", 
    "deployment.mmd", "recovery.mmd", "topology.mmd"
]

def main():
    os.makedirs(DOCS_DIR, exist_ok=True)
    
    for folder in folders:
        os.makedirs(os.path.join(DOCS_DIR, folder), exist_ok=True)
        
    for filename, content in files.items():
        filepath = os.path.join(DOCS_DIR, filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                f.write(content + "\n\n*Generated on: " + str(datetime.datetime.now()) + "*\n")
                
    for filename in flowcharts:
        filepath = os.path.join(DOCS_DIR, "flowchart", filename)
        if not os.path.exists(filepath):
            with open(filepath, 'w') as f:
                f.write(f"```mermaid\ngraph TD;\n    A-->B;\n```\n")

if __name__ == "__main__":
    main()
