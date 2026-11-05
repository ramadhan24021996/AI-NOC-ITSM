"""
AI Execution Engine (L4_Executor)
[K-09 / Rule #6 WS-6 FIX]
Status SUCCESS is ONLY valid when:
  (a) execution_evidence (ACK with exit_code=0) is present, AND
  (b) post_remediation_evidence (live telemetry, T_post >= T_exec) is captured.

Until per-device NATS dispatch with signed ACK (WS-3/WS-6) is wired in,
this module MUST return SIMULATED.  Dashboard must display the SIMULATED
label so operators are never misled about what actually ran on a device.
"""

import logging
import time
import importlib
from typing import Dict, List, Any, Optional

secret_manager_engine = None
for _mod_name in ("python_ai_core.security.secret_manager", "SERVER.python_ai_core.security.secret_manager", "security.secret_manager"):
    try:
        _mod = importlib.import_module(_mod_name)
        secret_manager_engine = getattr(_mod, "secret_manager_engine", None)
        if secret_manager_engine is not None:
            break
    except Exception:
        continue

observability_stack_engine = None
for _mod_name in ("python_ai_core.telemetry.observability_stack", "SERVER.python_ai_core.telemetry.observability_stack", "telemetry.observability_stack"):
    try:
        _mod = importlib.import_module(_mod_name)
        observability_stack_engine = getattr(_mod, "observability_stack_engine", None)
        if observability_stack_engine is not None:
            break
    except Exception:
        continue

logger = logging.getLogger("AI_EXECUTOR")

class AIExecutionEngine:
    def __init__(self):
        logger.info("[AI_EXECUTOR] Execution Engine initialized. Mode: SIMULATED (WS-6 real dispatch not yet wired).")

    def compile_execution_plan(self, action: str) -> List[Dict[str, Any]]:
        """Translates high-level action into concrete steps (planning only, not execution)."""
        return [
            {"step": 1, "name": "Dependency & Agent Heartbeat Check", "module": "DependencyChecker", "timeout_sec": 5},
            {"step": 2, "name": f"Dry Run Simulation of {action}", "module": "DryRunGate", "timeout_sec": 10},
            {"step": 3, "name": f"Dispatch Action Core ({action})", "module": "StepExecutor", "timeout_sec": 30},
            {"step": 4, "name": "Verify Metric Stabilization & Health", "module": "HealthMonitor", "timeout_sec": 15}
        ]

    def execute_plan(
        self,
        incident_id: str,
        plan_id: str,
        action: str,
        requires_hitl: bool = False,
        hitl_approved: bool = True
    ) -> Dict[str, Any]:
        """
        [K-09 / Rule #6] Returns SIMULATED until real NATS dispatch + ACK is implemented.

        Real execution path (WS-6) must:
          1. Dispatch signed command to device via NATS (WS-3).
          2. Wait for ACK containing execution_evidence (exit_code, before, after).
          3. Only then call the verifier with post_remediation_evidence.
          4. Bind evidence to this exact incident_id and target_asset.

        If NATS is not available or ACK times out → return TIMEOUT, never SUCCESS.
        """
        logger.info(f"[AI_EXECUTOR] Plan {plan_id} for incident {incident_id}: action={action} — SIMULATED mode")

        if requires_hitl and not hitl_approved:
            logger.warning(f"[AI_EXECUTOR] Execution blocked for plan {plan_id}: Awaiting HITL Approval.")
            return {
                "execution_id": f"exec_{plan_id}_{int(time.time())}",
                "incident_id": incident_id,
                "status": "AWAITING_HITL_APPROVAL",
                "message": "Action requires human approval before execution.",
                "execution_evidence": None,
                "post_remediation_evidence": None,
            }

        compiled_steps = self.compile_execution_plan(action)

        # [K-09] Status SIMULATED — no real command was sent to the device.
        # Dashboard MUST show this label.  This result must NOT be treated as
        # proof of remediation by the verifier or rule engine.
        result = {
            "execution_id": f"exec_{plan_id}_{int(time.time())}",
            "incident_id": incident_id,
            "plan_id": plan_id,
            "action_executed": action,
            "status": "SIMULATED",
            "status_note": (
                "Real dispatch requires WS-6 (NATS signed command) and WS-3 (per-device key). "
                "No command was sent to any device. Evidence fields are null."
            ),
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "compiled_steps_total": len(compiled_steps),
            # [Rule #6] Both fields MUST be non-null for RESOLVED to be valid.
            "execution_evidence": None,
            "post_remediation_evidence": None,
            "handoff_target": "L4_Verifier",
        }

        logger.warning(
            f"[AI_EXECUTOR] Plan {plan_id} returned SIMULATED. "
            "Incident stays IN_PROGRESS until real ACK + post-remediation evidence are received."
        )
        return result

# Global instance
ai_execution_engine = AIExecutionEngine()

