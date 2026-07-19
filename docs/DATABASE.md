# Database

**Engine:** PostgreSQL 15 + pgvector
**Database:** `osi_system`

## Key Tables
- **incidents**: Main incident records.
- **fleet_incidents**: Device-specific tracking.
- **ai_audit_trail**: Reasoning traces for AI decisions.
- **decision_graphs**: AI decision lineage.
- **knowledge_vectors**: RAG embeddings (pgvector).
- **telemetry_logs**: Time-series telemetry data.
- **approval_queue**: Pending human approvals.
- **chat_messages**: NOC to client chat.
- **rbac_users** & **rbac_policies**: Access control.
- **agent_heartbeats**: Agent tracking.
