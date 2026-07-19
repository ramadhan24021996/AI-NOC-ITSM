# FULL SYSTEM DISCOVERY + ARCHITECTURE AUDIT
Version: 2.0
Mode: Discovery First
Target: Unknown Existing System

ROLE:
You are a senior distributed systems auditor, infrastructure architect, AIOps analyst, and runtime flow investigator.
SYSTEM_DISCOVERY_AUDIT.md
├── ROLE
├── OBJECTIVE
├── DISCOVERY PHASE
├── CLIENT AUDIT
├── SERVER AUDIT
├── DASHBOARD AUDIT
├── FLOW TRACE
├── FUNCTION STATUS
├── GAP ANALYSIS
├── FINAL REPORT

IMPORTANT:

Do NOT assume the system architecture.
Do NOT assume modules exist.
Do NOT assume intended design.

First discover what actually exists.

Your task is to inspect the full codebase and map the real working system.

Goal:
Determine:

1. What systems exist
2. What each system does
3. What is working
4. What is incomplete
5. What is dead/unconnected
6. What is missing
7. How data flows across the entire system

Trace actual runtime paths.

==================================================
PHASE 1 — GLOBAL SYSTEM DISCOVERY
==================================================

Scan entire codebase:

- all folders
- all source files
- all configs
- all env files
- all docker files
- all migrations
- all scripts
- all service files
- all cron jobs
- all websocket handlers
- all API routes
- all database models

Build:

1. System inventory
2. Module inventory
3. Service inventory
4. Runtime dependency graph

Identify:

- entrypoints
- daemons
- background workers
- scheduled jobs
- APIs
- websocket services
- event handlers
- notification systems
- AI modules
- agent modules

Return:

{
 "systems_found": [],
 "entrypoints": [],
 "background_services": [],
 "api_routes": [],
 "workers": [],
 "unknown_modules": []
}

==================================================
PHASE 2 — PC CLIENT AUDIT (TARGET 05 READY DISTRIBUTION)
==================================================

Audit all PC client agents.

Identify:

- what agents exist
- how many
- what each collects
- how each sends data
- what services run locally

Trace:

PC CLIENT
↓
Telemetry Collector
↓
Normalizer
↓
Sender

Find:

- heartbeat
- event logs
- tasklist
- netstat
- service collector
- cpu collector
- ram collector
- disk collector
- process watcher
- popup notification
- auto-refresh service
- IP refresh updater

Map:

1. Actual client architecture
2. Data collected
3. Missing telemetry
4. Distribution readiness

Output:

{
 "pc_client_modules": [],
 "telemetry_sources": [],
 "communication_methods": [],
 "heartbeat_present": true/false,
 "distribution_ready": true/false,
 "missing_components": []
}

==================================================
PHASE 3 — SERVER CORE AUDIT
==================================================

Audit all server systems.

Discover:

- API receiver
- orchestrator
- AI engine
- log storage
- action engine
- policy engine
- workflow engine
- event queue
- database layer
- notification layer

Trace:

Incoming Data
↓
Receiver
↓
Processor
↓
Storage
↓
Analysis
↓
Action
↓
Verification

Find actual:

- Gin/Fiber/Echo routes
- GORM models
- database relations
- queues
- workers
- background jobs
- AI calls
- Telegram integration
- Websocket emitters

Output:

{
 "server_modules": [],
 "database_models": [],
 "orchestrators_found": [],
 "action_engines": [],
 "ai_modules": [],
 "verification_layers": [],
 "missing_core_systems": []
}

==================================================
PHASE 4 — DASHBOARD AUDIT
==================================================

Audit dashboard system.

Discover:

What exists inside dashboard:

- incident panel
- client online/offline
- telemetry graph
- logs viewer
- service control
- AI analysis view
- alert timeline
- ticketing
- notification center
- system health map
- agent deployment status

Check:

1. Which pages work
2. Which pages partially work
3. Which pages are placeholders
4. Which APIs are connected
5. Which widgets are dead

Output:

{
 "dashboard_pages": [],
 "working_pages": [],
 "broken_pages": [],
 "placeholder_pages": [],
 "connected_widgets": [],
 "dead_widgets": [],
 "missing_dashboard_features": []
}

==================================================
PHASE 5 — FULL DATA FLOW DISCOVERY
==================================================

Build actual runtime flow.

Trace every path.

Example:

PC Client
↓
Send telemetry
↓
Server receiver
↓
Database
↓
AI analyzer
↓
Policy
↓
Action
↓
Verify
↓
Dashboard
↓
Telegram

Find:

- where data starts
- where data transforms
- where data stops
- where data breaks
- where data loops
- where data is unused

Generate:

1. Full system flow
2. Module-to-module flow
3. Client-to-server flow
4. Server-to-dashboard flow
5. AI-to-action flow

Output:

{
 "full_runtime_flow": [],
 "broken_flow_nodes": [],
 "unused_paths": [],
 "dead_modules": [],
 "missing_links": []
}

==================================================
PHASE 6 — FUNCTIONAL STATUS AUDIT
==================================================

For each discovered system:

Mark:

WORKING
PARTIAL
BROKEN
NOT CONNECTED
NOT USED

Do NOT guess.

Verify actual calls.

Output:

{
 "working_systems": [],
 "partial_systems": [],
 "broken_systems": [],
 "dead_systems": [],
 "unused_systems": []
}

==================================================
PHASE 7 — MISSING COMPONENT ANALYSIS
==================================================

After discovery:

Determine what SHOULD exist but does not.

Examples:

- Correlation Engine
- Historical Recall
- Dependency Mapping
- Policy Engine
- Verification Loop
- Rollback Engine
- Queue System
- Alert Prioritization
- Root Cause Confidence Layer
- Incident Timeline Engine

Output:

{
 "critical_missing": [],
 "recommended_next_build": [],
 "high_priority_additions": []
}

==================================================
PHASE 8 — FINAL ARCHITECTURE MAP
==================================================

Build:

A. Current real architecture

B. Missing architecture

C. Recommended final architecture

D. Production readiness score

Return:

{
 "architecture_score": 0-100,
 "stability_score": 0-100,
 "automation_score": 0-100,
 "ai_maturity_score": 0-100,
 "dashboard_score": 0-100,
 "client_score": 0-100,
 "server_score": 0-100,
 "production_readiness": "low|medium|high|production",
 "current_architecture": {},
 "recommended_architecture": {},
 "critical_bottlenecks": [],
 "immediate_priorities": []
}

STRICT RULES:

- Do not trust filenames.
- Trace actual runtime.
- Trace actual imports.
- Trace actual API usage.
- Trace actual database writes.
- Trace actual websocket events.
- Trace actual AI inputs.
- Trace actual action outputs.
- Trace actual dashboard bindings.

System must be proven by execution path, not naming.

