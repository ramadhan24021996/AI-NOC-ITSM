"""
SERVER.tools.drivers.docker_driver — Docker Driver
====================================================
Tahap 2.4 — Tool Execution Layer

Operasi yang didukung: restart, stop, start, inspect, logs, exec
Operasi DIBLOKIR: rm (container delete) tanpa HITL, system prune
"""
import logging
import time
import uuid
from typing import Dict, Any
from SERVER.tools.interfaces import ToolResult, ToolStatus, RiskLevel

logger = logging.getLogger("tools.drivers.docker")

DOCKER_ALLOWED_OPS = {"restart", "stop", "start", "inspect", "logs", "exec", "ps", "stats"}
DOCKER_HITL_REQUIRED_OPS = {"rm", "rmi", "prune", "kill", "pause"}


class DockerDriver:
    """
    Mengeksekusi operasi Docker Container.
    Implementasi saat ini adalah simulasi (tanpa Docker socket nyata).
    Integrasi Docker API nyata dilakukan di Tahap 2.6.
    """

    @property
    def driver_type(self) -> str:
        return "docker"

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return bool(params.get("operation")) and bool(params.get("container"))

    def execute(self, params: Dict[str, Any], dry_run: bool = False) -> ToolResult:
        request_id = params.get("_request_id", str(uuid.uuid4())[:8])
        operation = params.get("operation", "").lower()
        container = params.get("container", "unknown")

        if operation in DOCKER_HITL_REQUIRED_OPS:
            return ToolResult(
                request_id=request_id,
                tool_id="docker_driver",
                status=ToolStatus.DENIED,
                error=f"Docker operation '{operation}' requires HITL approval. "
                      f"Route through ToolDispatcher with operator approval.",
                executed_by="docker_driver",
            )

        if operation not in DOCKER_ALLOWED_OPS:
            return ToolResult(
                request_id=request_id,
                tool_id="docker_driver",
                status=ToolStatus.DENIED,
                error=f"Docker operation '{operation}' is not in allowed operations list.",
                executed_by="docker_driver",
            )

        if dry_run:
            return ToolResult(
                request_id=request_id,
                tool_id="docker_driver",
                status=ToolStatus.SANDBOXED,
                output=f"[DRY-RUN] docker {operation} {container} — syntax valid, not executed.",
                executed_by="docker_driver",
                is_dry_run=True,
            )

        t0 = time.monotonic()
        simulated_output = (
            f"[DOCKER_SIMULATED] docker {operation} {container}\n"
            f"Container '{container}': {operation} OK\n"
        )
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(f"[DockerDriver] {operation} {container} | simulation OK")

        return ToolResult(
            request_id=request_id,
            tool_id="docker_driver",
            status=ToolStatus.SUCCESS,
            output=simulated_output,
            executed_by="docker_driver",
            duration_ms=duration_ms,
        )
