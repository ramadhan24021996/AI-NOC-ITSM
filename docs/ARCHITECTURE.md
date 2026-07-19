# Architecture

## Pattern
**Event-Driven Microservices + AI Cognitive Pipeline**

## High-Level Architecture
1. **Fleet Endpoints:** Windows/Linux agents send telemetry.
2. **Ingestion:** Go server receives, normalizes, scores integrity, and publishes to NATS.
3. **Message Broker:** NATS JetStream handles robust message delivery.
4. **AI Core:** Python-based AI Supervisor consumes events, queries LLM microservices (RAG, Consensus, Critic, Policy), and decides on actions.
5. **Execution:** Actions are either auto-executed via TCP relay to agents or sent to an Approval Queue for HITL.
6. **Dashboard:** Go server provides a UI for NOC operators to monitor, chat, and approve actions.

## Dependency Graph
- Core: `ai_supervisor.py` depends on multiple internal engines (Intent, Fabric, RAG, Consensus).
- Agents: NATS subjects route to specific AI agents (incident, recovery, security, verification).
- Data: All components rely heavily on PostgreSQL and Redis.
