# PRODUCTION REFACTOR PROMPT (HUMAN-IN-THE-LOOP)
Version: 1.0
Mode: Critical Architecture Upgrade
Priority: Immediate

ROLE:

You are a senior AIOps systems architect and production hardening engineer.

Your task is to refactor and improve the existing system based on the audit findings.

IMPORTANT:

Keep the system HUMAN-IN-THE-LOOP.

The AI must NEVER become fully autonomous.

AI acts as:

- analyzer
- advisor
- controlled executor

Human remains:

- final approver
- escalation handler
- destructive action validator

==================================================
PRIMARY OBJECTIVE
==================================================

Upgrade the current system from:

"AI-assisted infrastructure"

to:

"Production-grade incident intelligence core"

while maintaining:

SAFE HUMAN OVERSIGHT

==================================================
PRIORITY 1 — STRUCTURED AI OUTPUT
==================================================

Current problem:

AI returns raw strings.

This creates fragile parsing.

Refactor all AI outputs into strict JSON schema.

Create:

schemas/

incident_schema.py
action_schema.py
verification_schema.py
confidence_schema.py

Required output:

{
  "incident_id": "",
  "severity": "",
  "symptom": "",
  "root_cause": "",
  "confidence": 0,
  "recommended_action": "",
  "risk_level": "",
  "requires_human_approval": true
}

Requirements:

- Pydantic validation
- reject malformed outputs
- retry invalid schema
- normalize output
- preserve audit trail

Strictly block execution if schema invalid.

==================================================
PRIORITY 2 — CORRELATION ENGINE
==================================================

Current weakness:

AI analyzes symptoms.

Must upgrade to causal analysis.

Build:

core/

timeline_builder.py
correlation_engine.py
anomaly_cluster.py
causal_mapper.py

Requirements:

Merge:

- incoming telemetry
- historical incidents
- service logs
- server logs
- dependency maps

Capabilities:

1. detect earliest anomaly
2. reconstruct timeline
3. ignore downstream failures
4. isolate probable root cause
5. assign confidence

Required output:

{
  "timeline": [],
  "root_event": "",
  "downstream_effects": [],
  "confidence": 0
}

==================================================
PRIORITY 3 — AGENT ISOLATION
==================================================

Current weakness:

Single monolithic supervisor.

Split into isolated agents.

Create:

agents/

incident_agent.py
security_agent.py
recovery_agent.py
verification_agent.py

Use NATS subjects:

agent.incident.analyze
agent.security.validate
agent.recovery.prepare
agent.verify.result

Requirements:

Each agent:

- isolated responsibility
- independent processing
- async communication
- no shared mutable state

Human approval stays outside agent layer.

==================================================
PRIORITY 4 — HUMAN APPROVAL ENGINE
==================================================

CRITICAL

Create explicit HITL gate.

Flow:

AI Decision
↓
Risk Evaluation
↓
Human Approval Required?
↓
YES → wait approval
NO → execute low-risk action

Build:

core/

approval_engine.py
approval_queue.py

Rules:

Low risk:

- restart service
- clear temp
- refresh connection

Require approval:

- reboot machine
- stop database
- firewall changes
- delete files
- kill critical process

Required schema:

{
  "risk_level": "low|medium|high|critical",
  "approval_required": true
}

==================================================
PRIORITY 5 — VERIFICATION LOOP
==================================================

Current weakness:

Action ends without full validation.

Build:

verification/

health_checker.py
service_validator.py
rollback_engine.py

Flow:

Execute
↓
Wait
↓
Health Check
↓
Metrics Check
↓
Log Check
↓
Resolved?

If failed:

Rollback or escalate.

Required output:

{
  "verification_status": "",
  "service_alive": true,
  "port_open": true,
  "cpu_normalized": true,
  "rollback_needed": false
}

==================================================
PRIORITY 6 — DASHBOARD IMPROVEMENTS
==================================================

Add:

1. Incident Timeline View
2. Root Cause Confidence View
3. Human Approval Queue
4. Action Preview
5. Verification Status
6. Rollback History
7. Dependency Map Viewer
8. Historical Similar Incidents
9. Live Agent Health
10. Failed Action Log

Dashboard must clearly show:

- AI suggestion
- confidence
- risk level
- approval waiting
- execution result
- verification result

==================================================
FINAL TARGET FLOW
==================================================

PC CLIENT
↓
Telemetry Collector
↓
Go Ingestion Server
↓
NATS JetStream
↓
Correlation Engine
↓
Historical Recall
↓
Dependency Map
↓
Incident Agent
↓
Security Agent
↓
Recovery Agent
↓
Risk Evaluation
↓
Human Approval Gate
↓
Action Executor
↓
Verification Engine
↓
Rollback Engine
↓
Dashboard
↓
Telegram

==================================================
STRICT RULES
==================================================

- AI must never bypass approval.
- AI cannot execute high-risk actions directly.
- Every action must be logged.
- Every AI output must be schema validated.
- Every remediation must be verified.
- Every failed remediation must trigger rollback or escalation.
- Every incident must preserve full audit trail.

Goal:

Safe.
Traceable.
Production-ready.
Human-governed.