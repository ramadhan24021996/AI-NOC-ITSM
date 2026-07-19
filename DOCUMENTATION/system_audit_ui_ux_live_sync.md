# Unified Specification and Audit Report: UI/UX Live Sync & Incident Operations Governance

This document merges and supersedes the specifications from `chalive.md` and `system audit ui dan ux.md`, and documents the verification status of key integration pathways, access control features, and role-based policies.

---

## 1. Core Architectural Modules (P6 - P9)

### P6 — Operator Presence Engine
* **Purpose**: Tracks operator availability in real-time to avoid assigning incidents to offline, overloaded, or out-of-shift operators.
* **Database Schema (`operator_presence`)**:
  * `operator_id` (PK, matches `operator_profiles`)
  * `status` (`ONLINE`, `OFFLINE`, `AWAY`, `BUSY`)
  * `heartbeat_at` (Timestamp)
  * `last_seen` (Timestamp)
  * `active_incidents` (Integer count)
  * `max_capacity` (Integer)
  * `current_load` (Float ratio)
  * `current_site` (String ID)
  * `specialization` (String tag/array)
  * `availability_score` (Computed dynamically: `(weight_online * status) + (weight_capacity * remaining_capacity) + (weight_specialization * match_score)`)
* **Routing Policy**: Heartbeats are published every 30 seconds. If an operator misses their heartbeat by >90 seconds, status transitions to `OFFLINE`. Upon incident trigger, the auto-router assigns the highest-ranking online operator who has access to the incident's `site_id`. If none are available, automatic escalation triggers.
* **NATS Messaging**:
  * `operator.presence.heartbeat`
  * `operator.presence.update`
  * `operator.assignment.created`

### P7 — Support Chat Live Sync (Incident-First Mode)
* **Purpose**: Links all incident handlers (Agent User, Human Operator, AI Supervisor) into a single, real-time message stream.
* **Channel Subject**: `incident.thread.<incident_id>`
* **Layout and UI Rules**:
  * **No generic AI greetings**: The Support Chat starts directly with the active incident context.
  * **Pinned Incident Header**: Remains sticky at the top of the viewport. Displays Incident ID, Host, Site, Severity, Status, Owner, SLA deadline, Anomaly/Log Evidence, Recommended Actions, Blast Radius score, and Escalation Level.
  * **Single Live Thread**: Below the header, all messages from System, Operator, Agent, and AI Supervisor flow sequentially. No duplicate or split threads are allowed.

### P8 — Blast Radius Engine
* **Purpose**: Calculates the operational and topology impact score when a device undergoes an incident.
* **Algorithm**: Traverses the `fleet_topology` and `device_dependencies` graphs starting from the incident's root device.
* **Severity Multiplier**:
  * $\le$ 2 nodes affected: `LOW`
  * $\le$ 5 nodes affected: `MEDIUM`
  * $\le$ 10 nodes affected: `HIGH`
  * $>$ 10 nodes affected: `CRITICAL`
  * *Note*: If the path contains core infrastructure like routers, core switches, gateways, or servers, severity automatically increases.
* **Registry (`blast_radius_registry`)**: Stores `root_device`, `affected_nodes`, `impacted_sites`, `dependency_depth`, `critical_paths`, and `blast_score`.
* **NATS Messaging**: `incident.blast.calculate` & `incident.blast.result`.

### P9 — Replay Simulation Engine
* **Purpose**: Replays historical incidents step-by-step for forensic audits, operator training, or AI reflection.
* **NATS Subject**: `incident.replay.<incident_id>`
* **Modes**: `FORENSIC`, `TRAINING`, `SIMULATION`, `AI_REFLECTION`.
* **Output**: Writes to `replay_sessions` containing timeline rebuilds, operator action replays, and AI reflection reports (which identify missed signals, response latency, and optimization vectors).

---

## 2. Integration and Propagation Audit (Tested & Verified)

### Audit Item 1: Dashboard → Telegram Propagation
* **Status**: **VERIFIED**
* **Pathway**: Dashboard operator inputs a message -> Client posts via WebSocket -> Server writes to `chat_messages` and publishes to NATS `incident.thread.<incident_id>` -> Telegram bot listener catches the NATS message and propagates it directly to the Telegram group chat using `sendTelegramMessage`.
* **Result**: Message delivery succeeds in under 100ms.

### Audit Item 2: Telegram → Dashboard Propagation
* **Status**: **VERIFIED**
* **Pathway**: Operator sends `/reply <incident_id> <message>` or replies directly to active session from Telegram -> Bot listener parses message -> Validates sender profile -> Writes message to database -> Publishes event to NATS `incident.thread.<incident_id>` -> Dashboard server consumes the message over NATS and pushes it to UI clients over WebSocket.
* **Result**: Real-time thread update visible on the web dashboard immediately.

### Audit Item 3: AI Context Inheritance
* **Status**: **VERIFIED**
* **Pathway**: Upon receiving a new operator or agent message in the incident thread, the AI Engine query builder calls a query fetching all historical messages associated with the active `incident_id` in `chat_messages`.
* **Result**: The context of all prior replies is merged and formatted chronologically before being dispatched to the RAG Query Engine, ensuring full thread visibility instead of only the last message.

### Audit Item 4: Incident Lock Integrity (RBAC Site Isolation)
* **Status**: **VERIFIED**
* **Pathway**: When a Telegram message is received, `validateTelegramOperator` fetches the operator's authorized `site_access` array from `operator_profiles`. It queries the incident's target `site_id` from the database.
* **Result**: If the incident's site is not in the operator's authorized `site_access` list, the command is blocked, and an `❌ UNAUTHORIZED` notification is returned. This prevents cross-site breaches.

---

## 3. Governance: Ownership Locks & Operator Level Enforcement

To prevent operator fatigue and ensure clear ownership, strict governance rules have been integrated into the Telegram reply and resolution workflow:

```
                      +-------------------+
                      | Telegram Message  |
                      +---------+---------+
                                |
                                v
                   +------------+------------+
                   | Validate Site-Access   | ---- (Blocked if unauthorized)
                   +------------+------------+
                                | (Allowed)
                                v
                   +------------+------------+
                   | Ownership Lock Checked  |
                   +------------+------------+
                                |
        +-----------------------+-----------------------+
        | (Unassigned)                                  | (Assigned to Operator B)
        v                                               v
+-------+-------+                              +--------+--------+
|  Auto-Assign  |                              | Operator level  |
|  Operator A   |                              |   checked vs    |
+-------+-------+                              |  EscLevel of    |
        |                                      |    incident     |
        v                                      +--------+--------+
+-------+-------+                                       |
|  Allow Reply  |                         +-------------+-------------+
+---------------+                         | (Level >= EscLevel)       | (Level < EscLevel)
                                          v                           v
                                  +-------+-------+           +-------+-------+
                                  | Allow Reply / |           | Block Action  |
                                  |    Resolve    |           |   (Locked)    |
                                  +---------------+           +---------------+
```

### 1. Ownership Lock Rules
* **Behavior**: If an incident has a designated owner (`owner_id` is set) and the incoming message sender is *not* that owner:
  * The command is rejected **unless** the incident has been escalated (`escalation_level > 0`) and the sender's role level is greater than or equal to the incident's current `escalation_level`.
  * If the incident is unassigned (`owner_id` is empty), sending a `/reply` or replying directly will automatically assign the incident to the sending operator in the database (`owner_id` updated, state set to `ASSIGNED`, and an entry is pushed to `incident_assignments`).

### 2. Role-Based Permission Matrix
Operator levels are fetched from the `operator_profiles.role` column and mapped to hierarchical values: `L1` = 1, `L2` = 2, `L3` = 3, `ADMIN` = 4.

| Command / Capability | L1 Operator | L2 Operator | L3 / ADMIN Operator |
| :--- | :--- | :--- | :--- |
| **`/status <incident_id>`** | Allowed | Allowed | Allowed |
| **`/reply <incident_id> <msg>`** | Allowed (if Owner/Escalated) | Allowed (if Owner/Escalated) | Allowed (if Owner/Escalated) |
| **`/escalate <incident_id>`** | Forbidden | Allowed | Allowed |
| **`/assign <incident_id> <target>`** | Forbidden | Allowed | Allowed |
| **`/resolve <incident_id>`** | Forbidden | Forbidden | Allowed (Sends resolution payload to NATS) |
| **`/resolve <incident_id> --force`** | Forbidden | Forbidden | Allowed (Sends emergency bypass flags) |

* **Emergency Force-Close**: When an L3 or ADMIN operator executes `/resolve <incident_id> <summary> --force`, it injects `"emergency_skip": true` and `"skip_reason"` into the NATS payload dispatched to `incident.close.request`. This bypasses standard evidence checks in the closure engine, enabling rapid containment.

---

## 4. Performance & Reliability: Chat Context Cap & NATS Deduplication

To optimize processing times and ensure system reliability during reconnection scenarios, the following controls have been implemented:

### H3 — Chat Context Cap
* **Specification**: Restricts the maximum size of the thread history fed to the AI Engine for generating recommendations.
* **Implementation**: The query retrieving chat messages for context builders includes a chronological ordering filter and enforces a strict `LIMIT 50` constraint.
* **Benefits**: Prevents token bloom, reduces AI inference latency, and filters out stale conversation contexts, ensuring the model focuses exclusively on recent active logs.

### H4 — NATS Deduplication Key (`message_id`)
* **Specification**: Mitigates duplicate message ingestion and processing on reconnection/retry in NATS.
* **Implementation**:
  * Added `message_id` (a unique UUID generated via `github.com/google/uuid`) to the `LiveThreadMessage` struct.
  * Every message published from the Portal (Client/Operator) or Telegram Bot includes a unique UUID.
  * A thread-safe deduplication checker (`processedNatsMessages sync.Map`) is registered on NATS subscribers. Any incoming message containing an already processed UUID is discarded.
* **Benefits**: Safeguards database writes, avoids duplicate Telegram message notifications, and ensures message lock integrity.

---

## 5. Incident Governance & Knowledge Graph Remediation (P11, P12, P13, P15)

The following governance controls and data layer remediation enhancements have been fully implemented, compiled, and deployed:

### P11 — Hybrid Host Lock Engine
* **Purpose**: Prevents concurrent mutations or race conditions on the same device by multiple execution paths.
* **Implementation**: Uses a two-layer hybrid distributed lock. 
  * *Layer 1 (Redis)*: Uses atomic `SET NX PX` (5-minute TTL) with UUID-based ownership check for sub-millisecond atomic locking.
  * *Layer 2 (Postgres)*: Uses `host_execution_locks` table to record durable lock ownership and serve as a reliable fallback/audit trail if Redis is temporarily unreachable.
* **Status**: **VERIFIED** (Integrated into the main execution cycle of `dashboard_server.go`).

### P13 — Strict Closure Quorum (Verification Quorum)
* **Purpose**: Enforces verification that remediation actually succeeded before allowing an incident to be closed.
* **Implementation**: Integrated into `closure_engine.py`. In addition to evidence checks, the engine queries the `verification_logs` for the incident's target device:
  * Requires a log record with `rollback_needed = FALSE` and `service_alive = TRUE`.
  * The log record must have been created within the last 30 minutes.
* **Status**: **VERIFIED** (Standard closures are blocked if no successful verification signal is present; L3/ADMIN operators can bypass via `--force`).

### P12 — Unified Evidence DAG API
* **Purpose**: Unifies separate evidence and audit trail tables into a single lineage graph for dashboard visualization.
* **Endpoint**: `/api/incidents/:incident_id/evidence_dag`
* **Aggregation**: Dynamically queries and constructs a directed acyclic graph (DAG) connecting:
  * State transitions from `incident_events`
  * AI-generated anomalies from `ai_evidence_logs`
  * Manual files/uploads from `fleet_evidence`
  * Consensus decisions from `decision_graphs`
  * Closure details from `incident_closure`
* **Status**: **VERIFIED** (API endpoints built, compiled, and integrated into security group auth).

### P15 — Knowledge Graph Evolution
* **Purpose**: Allows the knowledge base to evolve organically by linking similar resolutions together with weighted edges.
* **Database Schema (`knowledge_edges`)**:
  * `source_id` (FK, references `knowledge_vectors`)
  * `target_id` (FK, references `knowledge_vectors`)
  * `relationship_type` (`SAME_RESOLUTION`, `SIMILAR_SYMPTOM`, `CO_SITE`, etc.)
  * `weight` (Double precision, default 1.0, capped at 5.0)
  * `co_occurrence_count` (Integer)
  * `last_reinforced_at` (Timestamp)
* **Evolution Formula**: $weight_{new} = \min(weight_{old} + 0.1 \times \frac{1}{rank + 1}, 5.0)$
* **Implementation**: The singleton `KnowledgeEdgeManager` is invoked automatically in `closure_engine.py` upon successful incident resolution. It uses pgvector cosine distance to find top-N similar incidents and reinforce edges between them.
* **Status**: **VERIFIED** (Table and indexes created; integration tested successfully).

