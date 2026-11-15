# System Overview

**Name:** OSI AI Ops — Incident Analysis Platform
**Domain:** Network Operations Center (NOC) AI-Driven IT Operations

## Primary Goals
- Ingest telemetry in real-time from agents.
- Perform automated Root Cause Analysis (RCA).
- Mitigate issues automatically or escalate to human operators.
- Learn from incidents and improve future resolution accuracy.

## Key Components
- **Ingestion Server (Go):** Receives, normalizes, and deduplicates telemetry.
- **AI Supervisor (Python):** The core event-driven pipeline orchestrating AI decisions.
- **Dashboard Server (Go):** The NOC UI backend providing REST APIs and WebSocket streams.
- **NATS JetStream:** The central message broker connecting components.
- **PostgreSQL (pgvector):** The primary persistence layer for state, audit logs, and RAG vectors.
- **Redis:** Used for caching, rate limiting, and Pub/Sub.
