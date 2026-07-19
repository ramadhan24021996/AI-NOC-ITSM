# Modules

## Go Core (Ingestion)
- **Ingestion Server:** Listens on port 18800. Dedupes and normalizes logs.
- **Telegram Bot:** Polls Telegram for operator approvals.
- **Syslog Receiver:** Accepts syslog format telemetry.

## Python AI Core
- **AI Supervisor:** The main NATS consumer. Orchestrates the AI pipeline.
- **Intent Classifier:** Uses TF-IDF for fast routing.
- **Evidence Fabric:** Validates incoming telemetry.
- **Consensus Engine:** Queries multiple LLMs.
- **Critic Engine:** Challenges the consensus.
- **Policy Engine:** Evaluates actions against rules.
- **RAG Engine:** Semantic search via pgvector.
- **Daemons:** Background tasks for health, KPIs, and drift detection.

## Portal (Dashboard)
- **Dashboard Server:** Serves the frontend and REST APIs.
- **Websocket Hub:** Real-time updates for the NOC UI.
