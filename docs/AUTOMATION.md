# Automation

## Background Daemons
Located in `SERVER/python_ai_core/daemons.py` and Go scheduling loops:
- **Every 5s:** Timeline KPI, Agent heartbeats.
- **Every 30s:** Enterprise watch officer.
- **Every 1m:** Predictive failure analysis.
- **Every 5m:** World model updates, incident retries.
- **Every 6-24h:** Benchmarks, curiosity, architecture audits, drift detection.

## Workflows
- **Auto-Resolution:** verified successful actions auto-resolve the incident and push to the learning queue.
