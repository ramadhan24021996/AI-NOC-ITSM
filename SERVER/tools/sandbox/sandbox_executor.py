"""
SERVER.tools.sandbox — Sandbox Executor
========================================
Tahap 2.4 — Tool Execution Layer

SandboxExecutor menjalankan semua tool requests dalam mode dry-run terlebih dahulu
sebelum eksekusi nyata diizinkan. Digunakan untuk:
  1. Validasi sintaks dan parameter sebelum kirim ke driver nyata
  2. AI auto-exec: semua aksi ssh/docker/mikrotik harus sandbox dulu
  3. Forced sandbox dari PolicyEngine (force_sandbox = True)
  4. Shadow execution untuk AdversarialCriticEngine
"""
import logging
import uuid
from typing import Dict, Any
from SERVER.tools.interfaces import ToolResult, ToolStatus, ToolRequest
from SERVER.tools.drivers import DRIVER_REGISTRY

logger = logging.getLogger("tools.sandbox.executor")


class SandboxExecutor:
    """
    Menjalankan semua driver dalam dry_run=True mode.
    Menghasilkan ToolResult dengan status SANDBOXED tanpa efek nyata pada sistem.
    """

    def execute_dry_run(
        self,
        request: ToolRequest,
        driver_type: str,
    ) -> ToolResult:
        """
        Menjalankan tool dalam sandbox (dry-run) mode.

        Args:
            request: ToolRequest yang akan disimulasikan.
            driver_type: Jenis driver yang akan digunakan.

        Returns:
            ToolResult dengan status SANDBOXED.
        """
        driver_class = DRIVER_REGISTRY.get(driver_type)
        if not driver_class:
            return ToolResult(
                request_id=request.request_id,
                tool_id=request.tool_id,
                status=ToolStatus.FAILED,
                error=f"No driver registered for type: '{driver_type}'",
                executed_by="sandbox_executor",
                is_dry_run=True,
            )

        driver = driver_class()
        params = dict(request.params or {})
        params["_request_id"] = request.request_id

        logger.info(
            f"[SandboxExecutor] DRY-RUN | tool={request.tool_id} | driver={driver_type} | "
            f"incident={request.incident_id}"
        )

        result = driver.execute(params, dry_run=True)
        result.is_dry_run = True

        if result.status not in (ToolStatus.SANDBOXED, ToolStatus.DENIED):
            result.status = ToolStatus.SANDBOXED

        logger.info(
            f"[SandboxExecutor] Sandbox result: status={result.status.value} | "
            f"output='{result.output[:80]}'"
        )
        return result

    def validate_only(self, request: ToolRequest, driver_type: str) -> bool:
        """
        Validasi parameter tanpa eksekusi apapun.
        Returns True jika parameter valid.
        """
        driver_class = DRIVER_REGISTRY.get(driver_type)
        if not driver_class:
            return False
        driver = driver_class()
        return driver.validate_params(request.params or {})
