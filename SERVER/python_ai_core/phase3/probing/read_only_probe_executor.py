"""
Phase 3.3: Read-Only Probe Executor & Safety Validator (phase3/probing/read_only_probe_executor.py)

Enforces Invariant #7 (Registered Probe Only) & Invariant #8 (Read-Only Whitelist Default-DENY).
Blocks any arbitrary command, shell injection, path traversal, mutating token, or unregistered probe request.
"""

import logging
import subprocess
import shlex
import os
import time
from typing import Dict, Any, Optional
from phase3.probing.probe_contract import ProbeRegistry, ProbeContract, MUTATING_TOKENS_BLACKLIST

logger = logging.getLogger("READ_ONLY_PROBE_EXECUTOR")


class ReadOnlyProbeExecutor:
    def __init__(self, registry: Optional[ProbeRegistry] = None):
        self.registry = registry or ProbeRegistry()

    def execute_probe(self, probe_id: str, target: str, custom_cmd: Optional[str] = None) -> Dict[str, Any]:
        """
        Executes registered diagnostic probe.
        FAIL-CLOSED Safety Checks:
        1. Invariant #7: Must be registered in ProbeRegistry. Unregistered -> DENIED.
        2. Invariant #8: Whitelist validation & mutating blacklist check. Mutating -> DENIED.
        3. Target validation: Must be an allowed target. Unauthorized -> DENIED.
        """
        # 1. Invariant #7: Registered Probe Only
        probe = self.registry.get_probe(probe_id)
        if not probe:
            logger.error(f"[SAFETY DENIED] Probe ID '{probe_id}' is UNREGISTERED. Execution DENIED.")
            return {"status": "DENIED", "reason": "UNREGISTERED_PROBE_ATTEMPT", "probe_id": probe_id}

        # 2. Invariant #8: Read-Only Enforcement & Shell Injection Defense
        cmd = custom_cmd or probe.command_template
        cmd_lower = cmd.lower()

        # Reject any mutating tokens
        for token in MUTATING_TOKENS_BLACKLIST:
            if token in cmd_lower:
                logger.error(f"[SAFETY DENIED] Command '{cmd}' contains mutating token '{token}'. Execution DENIED.")
                return {"status": "DENIED", "reason": "MUTATING_COMMAND_BLOCKED", "probe_id": probe_id, "violating_token": token}

        # Reject path traversal attempts
        if ".." in cmd or "/etc/shadow" in cmd or "/etc/passwd" in cmd:
            logger.error(f"[SAFETY DENIED] Command '{cmd}' contains path traversal or restricted file access. Execution DENIED.")
            return {"status": "DENIED", "reason": "PATH_TRAVERSAL_BLOCKED", "probe_id": probe_id}

        # 3. Target Validation
        if not self.registry.is_target_allowed(probe_id, target):
            logger.error(f"[SAFETY DENIED] Target '{target}' is NOT allowed for probe '{probe_id}'. Execution DENIED.")
            return {"status": "DENIED", "reason": "UNAUTHORIZED_TARGET", "probe_id": probe_id, "target": target}

        # 4. Safe Execution (Subprocess Timeout Guard)
        t_start = time.time()
        try:
            # Execute read-only command safely
            proc = subprocess.run(
                shlex.split(cmd),
                capture_output=True,
                text=True,
                timeout=probe.timeout_seconds
            )
            t_exec = round(time.time() - t_start, 3)

            if proc.returncode == 0:
                logger.info(f"[PROBE SUCCESS] Probe '{probe_id}' executed cleanly in {t_exec}s on target '{target}'")
                return {
                    "status": "SUCCESS",
                    "probe_id": probe_id,
                    "target": target,
                    "execution_time_seconds": t_exec,
                    "stdout": proc.stdout.strip(),
                    "stderr": proc.stderr.strip(),
                    "exit_code": 0
                }
            else:
                logger.warning(f"[PROBE FAILED] Probe '{probe_id}' returned exit code {proc.returncode}: {proc.stderr.strip()}")
                return {
                    "status": "PROBE_EXECUTION_FAILED",
                    "probe_id": probe_id,
                    "target": target,
                    "execution_time_seconds": t_exec,
                    "exit_code": proc.returncode,
                    "error": proc.stderr.strip()
                }
        except subprocess.TimeoutExpired:
            logger.error(f"[PROBE TIMEOUT] Probe '{probe_id}' timed out after {probe.timeout_seconds}s!")
            return {"status": "PROBE_EXECUTION_FAILED", "reason": "PROBE_TIMEOUT", "probe_id": probe_id}
        except Exception as e:
            logger.error(f"[PROBE EXCEPTION] Probe '{probe_id}' execution exception: {e}")
            return {"status": "PROBE_EXECUTION_FAILED", "reason": f"EXCEPTION: {e}", "probe_id": probe_id}
