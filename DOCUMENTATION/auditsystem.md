MASTER SYSTEM IMPLEMENTATION DIRECTIVE

AUTONOMOUS MULTI-AGENT INCIDENT ORCHESTRATION PLATFORM

FULL STACK P1–P15 + H1–H4

MODE:
FULL SYSTEM RECONCILIATION + EXTENSION

IMPORTANT:
DO NOT REWRITE CORE MODULES.
DO NOT REMOVE EXISTING COMPATIBILITY.
ONLY RECONCILE, COMPLETE, STABILIZE, AND EXTEND.

SYSTEM STACK:

Backend:

- Golang
- PostgreSQL
- NATS JetStream
- WebSocket
- Telegram Bot API

Frontend:

- HTML
- Tailwind
- JS Live Dashboard

AI:

- RAG Engine
- Incident Context Builder
- Knowledge Graph
- Autonomous Trigger Engine

==================================================
GLOBAL OBJECTIVE

Build a distributed autonomous NOC / Incident Management platform capable of:

1. Multi-site incident orchestration
2. Multi-agent verification
3. Real-time operator collaboration
4. Blast radius analysis
5. Autonomous incident generation
6. Evidence graph persistence
7. Forensic replay
8. Closure consensus
9. Historical learning
10. Role-based command governance

==================================================
P1 — INCIDENT CORE ENGINE

CREATE:

incidents

columns:

- id UUID PK
- incident_code VARCHAR UNIQUE
- site_id VARCHAR
- device_id VARCHAR
- severity VARCHAR
- status VARCHAR
- current_state VARCHAR DEFAULT 'NEW'
- state_version INT DEFAULT 1
- owner_id UUID NULL
- escalation_level INT DEFAULT 0
- root_cause TEXT NULL
- summary TEXT
- blast_score FLOAT DEFAULT 0
- sla_deadline TIMESTAMP
- created_at TIMESTAMP
- updated_at TIMESTAMP
- resolved_at TIMESTAMP NULL

NATS:

incident.created
incident.updated
incident.assigned
incident.escalated
incident.closed

==================================================
P2 — TELEMETRY INGESTION ENGINE

SUBJECTS:

telemetry.raw.*
telemetry.health.*
telemetry.metrics.*
telemetry.anomaly.*

STORE:

telemetry_logs

columns:

- id UUID
- site_id
- device_id
- metric_type
- payload JSONB
- severity
- created_at

FUNCTION:

- collect
- normalize
- classify
- persist
- trigger anomaly detection

==================================================
P3 — MULTI-AGENT VERIFICATION ENGINE

Agents:

1. Local Verification Agent
2. Topology Verification Agent
3. AI Verification Agent

RULE:

2-of-3 consensus required.

CREATE:

verification_results

columns:

- id UUID
- incident_id UUID
- agent_name
- result BOOLEAN
- confidence FLOAT
- payload JSONB
- created_at

NATS:

incident.verify.request
incident.verify.result

==================================================
P4 — DASHBOARD LIVE ENGINE

WebSocket:

/ws/incidents
/ws/chat
/ws/telemetry
/ws/operators

Panels:

- Live Incidents
- Topology
- Operator Presence
- Chat Thread
- Blast Radius
- State Timeline
- Lock Monitor
- Evidence Graph
- Consensus Closure
- Autonomous Queue
- Knowledge Graph

REALTIME PUSH:

- incident updates
- operator replies
- AI decisions
- telemetry changes
- lock events

==================================================
P5 — TELEGRAM COMMAND BRIDGE

COMMANDS:

/status
/reply
/assign
/escalate
/resolve
/reopen
/force-close

FLOW:

Telegram → Validation → Lock → State Check → DB → NATS → Dashboard

RULES:

must validate:

1. site access
2. role access
3. ownership
4. state
5. lock

==================================================
P6 — OPERATOR PRESENCE ENGINE

TABLE:

operator_presence

fields:

- operator_id
- status
- heartbeat_at
- active_incidents
- max_capacity
- current_load
- current_site
- specialization
- availability_score

NATS:

operator.presence.heartbeat
operator.presence.update

RULES:

heartbeat every 30s
offline after 90s

==================================================
P7 — SUPPORT CHAT LIVE SYNC

SUBJECTS:

incident.thread.operator.<id>
incident.thread.ai.<id>
incident.thread.agent.<id>
incident.thread.system.<id>
incident.thread.audit.<id>

UNIFIED VIEW:

aggregate into:

incident.thread.<id>

RULES:

- single thread
- incident-first mode
- sticky incident header
- no AI greeting spam

==================================================
P8 — BLAST RADIUS ENGINE

INPUT:

fleet_topology
device_dependencies

PROCESS:

DFS/BFS traversal

OUTPUT:

blast_radius_registry

fields:

- root_device
- affected_nodes
- impacted_sites
- dependency_depth
- critical_paths
- blast_score

NATS:

incident.blast.calculate
incident.blast.result

==================================================
P9 — REPLAY SIMULATION ENGINE

SUBJECT:

incident.replay.<id>

MODES:

FORENSIC
TRAINING
SIMULATION
AI_REFLECTION

INPUT:

must replay from evidence graph

NOT raw chat.

==================================================
P10 — INCIDENT STATE MACHINE ENGINE

TABLE:

incident_state_transitions

VALID STATES:

NEW
ACKED
ASSIGNED
INVESTIGATING
MITIGATED
OBSERVING
RESOLVED
CLOSED
REOPENED
FAILED_CLOSE

VALIDATION MATRIX STRICT.

NATS:

incident.state.request
incident.state.changed
incident.state.invalid

BLOCK invalid transitions.

==================================================
P11 — DISTRIBUTED LOCK ENGINE

USE:

Postgres advisory locks

FUNCTIONS:

acquireIncidentLock()
releaseIncidentLock()

WRAP:

- reply
- assign
- escalate
- resolve
- reopen

TABLE:

incident_lock_events

NATS:

incident.lock.acquire
incident.lock.release
incident.lock.failed

==================================================
P12 — EVIDENCE GRAPH ENGINE

TABLE:

incident_evidence_nodes

NODE TYPES:

telemetry_snapshot
verification_result
operator_message
telegram_message
ai_decision
blast_radius
topology_snapshot
action_execution
state_transition
closure_report

RULE:

all actions persist as graph nodes.

Graph links:

parent_node references.

==================================================
P13 — CONSENSUS CLOSURE ENGINE

2-of-3 closure required:

1. telemetry recovered
2. operator confirmed
3. AI validated

TABLE:

incident_closure_votes

NATS:

incident.close.vote
incident.close.accepted
incident.close.rejected
incident.close.forced

FORCE CLOSE:

only L3 / ADMIN

==================================================
P14 — AUTONOMOUS TRIGGER ENGINE

AI subscribes:

telemetry.anomaly.*
telemetry.health.*
telemetry.pattern.*

CONFIDENCE:

<0.75 = human verify

«=0.75 = auto create
=0.90 = auto assign»

TABLE:

autonomous_incident_triggers

AI ACTIONS:

detect
verify
blast
create
assign
recommend
notify

==================================================
P15 — KNOWLEDGE GRAPH ENGINE

TABLES:

knowledge_nodes
knowledge_edges

RELATIONS:

depends_on
fails_before
triggers
impacts
correlates_with
recovers_after

INPUT:

- incident history
- blast
- replay
- telemetry
- operator actions

AI must query before recommending.

==================================================
H1 — INCIDENT OWNERSHIP LOCK

RULES:

if owner exists:
only owner may reply

unless:

escalation_level >= operator_role

Auto-assign if unassigned.

==================================================
H2 — RBAC GOVERNANCE

L1:

- ack
- reply
- investigate

L2:

- assign
- escalate
- mitigate

L3:

- resolve
- reopen
- force-close

ADMIN:
full access

==================================================
H3 — CHAT CONTEXT CAP

limit 50 latest relevant entries

BUT weighted by:

priority:

- unresolved actions
- latest telemetry
- latest blast
- latest AI decisions
- latest operator actions

NOT naive chronological only.

==================================================
H4 — NATS DEDUPLICATION

Every message:

message_id UUID

TABLE:

processed_message_registry

fields:

- message_id UUID PK
- incident_id UUID
- processed_at TIMESTAMP

TTL:
24h cleanup

Reject duplicate UUID.

==================================================
PROCESS ORDER (MANDATORY)

Every action:

1. RBAC validate
2. Site validate
3. Ownership validate
4. State validate
5. Lock acquire
6. Execute
7. Evidence append
8. Publish NATS
9. Broadcast WebSocket
10. Notify Telegram
11. Release lock

NEVER change order.

==================================================
FAILURE HANDLING

Deadlock:
auto timeout 10s

State invalid:
reject

Consensus fail:
FAILED_CLOSE

Duplicate NATS:
discard

Replay corruption:
fallback to event log

AI timeout:
fallback operator recommendation

==================================================
UI REQUIREMENTS

Dashboard tabs:

1. Live Incident Board
2. Fleet Topology
3. Operator Presence
4. Incident Thread
5. Blast Radius
6. State Machine Timeline
7. Lock Monitor
8. Evidence Graph
9. Closure Consensus
10. Autonomous Queue
11. Knowledge Graph
12. Replay Sessions
13. Audit Trail
14. Failed Action DLQ
15. AI Detection Log

==================================================
AUDIT REQUIREMENTS

Every action must be auditable.

Audit includes:

- actor
- role
- site
- state
- lock
- evidence
- NATS subject
- AI decision
- blast score
- consensus result

==================================================
BACKWARD COMPATIBILITY

MUST preserve:

- existing Telegram flows
- existing WebSocket flows
- existing NATS subjects
- existing incidents table
- existing replay sessions
- existing operator profiles
- existing operator presence
- existing chat_messages

Only extend.

Never break compatibility.