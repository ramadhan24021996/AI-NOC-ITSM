# Data Flow

1. **Telemetry Ingestion:**
   Agent -> POST /ingest -> Ingestion Server -> normalize -> NATS `telemetry.site.<site>.critical`
2. **AI Processing:**
   NATS -> AI Supervisor -> Intent Classification -> Evidence Fabric -> OSI Taxonomy
3. **Inference:**
   Supervisor -> Gemini (Embedding) -> pgvector (Search) -> Consensus (LLM) -> Critic (LLM) -> Policy (Rules)
4. **Decision:**
   - **HITL:** -> Approval Queue -> Telegram/Dashboard -> Manual Approval
   - **Auto:** -> `remediation.execute` -> Dashboard Server -> TCP to Agent
5. **Verification & Loop:**
   Agent ACK -> ActionVerifier (wait 30s) -> SUCCESS/REGRESSION -> TrustEngine Update -> DB Audit Log
