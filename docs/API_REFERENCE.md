# API Reference

*Base URL: Dashboard Server (Port 9000)*

## Auth
- `POST /api/auth/login`: JWT login
- `POST /api/auth/logout`: Invalidate token

## Incidents
- `GET /api/incidents`: List incidents
- `GET /api/incidents/:id`: Single incident details
- `POST /api/rca/reanalyze/:id`: Trigger AI re-analysis
- `GET /api/rca/:id`: RCA and audit trail
- `GET /api/approvals`: Pending HITL approvals
- `POST /api/approvals/:id/approve`: Approve action

## System & Fleet
- `GET /api/system/status`: Component health
- `GET /api/fleet/devices`: Registered devices
- `GET /api/topology`: Network topology
- `GET /api/playbooks`: Governance SOPs

## WebSocket
- `WS /ws/dashboard`: NOC operator real-time stream
