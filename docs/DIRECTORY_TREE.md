# Directory Tree

```
incident-analysis/
├── SERVER/
│   ├── go_core/           # Ingestion Server (Go)
│   │   ├── ingestion/
│   │   ├── ai/
│   │   ├── database/
│   │   ├── security/
│   │   ├── config/
│   │   ├── discovery/
│   │   └── telegram_bot/
│   └── python_ai_core/    # AI Processing Core (Python)
│       ├── agents/
│       ├── cognition/
│       ├── planning/
│       ├── knowledge/
│       ├── evaluation/
│       ├── evolution/
│       ├── learning/
│       ├── verification/
│       ├── governance/
│       ├── cognitive_memory/
│       ├── multi_agent/
│       ├── runtime/
│       ├── core/
│       ├── services/
│       └── api/
├── portal/                # Dashboard Server (Go Gin)
│   ├── dashboard_server.go
│   ├── dashboard/
│   └── frontend/
├── DOCUMENTATION/         # Docs and PRDs
├── docker/                # Configs for Nginx, DB, Redis, NATS
├── docker-compose.yml     # Infrastructure definition
└── .env
```
