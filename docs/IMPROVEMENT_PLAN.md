# Improvement Plan

## Critical (Next Sprint)
1. **Wire Decision & Goal Engines:** Integrate `decision_engine.py` into `ai_supervisor.py`.
2. **DLQ Processor:** Implement a consumer for `dlq.site.<x>` to handle failed messages.
3. **Site Event Subscribers:** Add listeners for `incident.site.*.create/update/verify`.
4. **Fix Service Validator Mock:** Replace hardcoded `port_open: True` with actual TCP checks.

## High Priority
5. **Causal Reasoning:** Implement real graph traversal in `CausalEngine` instead of dummy strings.
6. **Active Cognition:** Complete the methods in `ActiveCognitiveEngine` for the Early Warning System.
7. **Cognitive Memory:** Implement the 9 stub files to enable cross-session AI memory.

## Medium Priority
8. **Multi-Agent Orchestrator:** Implement the agent registry and routing logic.
9. **Time-Series Data:** Replace hardcoded historical data in the predictive loop with real DB queries.
10. **Testing:** Establish E2E testing and a CI/CD pipeline.
