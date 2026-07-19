# Prompts

Prompts are generally embedded within the Python AI Core services (`services/` and `agents/` directories).

## Typical Structure
- **Context:** System state, OSI layer, telemetry details.
- **Task:** e.g., "Analyze root cause", "Evaluate risk", "Propose mitigation".
- **Format:** Strict JSON output requirements.
- **Constraints:** Avoid hallucination, rely on provided evidence.

*Note: Extracting exact prompts requires inspecting files like `consensus_service.py` and `critic_service.py`.*
