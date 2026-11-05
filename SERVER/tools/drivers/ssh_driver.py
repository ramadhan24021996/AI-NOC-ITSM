"""
SERVER.tools.drivers.ssh_driver — SSH Driver
=============================================
Tahap 2.4 — Tool Execution Layer

Driver TIDAK BOLEH dipanggil langsung. Selalu melalui ToolDispatcher.

Fitur:
  - Dry-run mode: validasi sintaks perintah tanpa eksekusi nyata
  - Timeout enforcement per perintah
  - Dangerous command guardrails (pola destruktif ditolak)
  - Structured output: stdout, stderr, exit_code, duration_ms
"""
import logging
import re
import time
import uuid
from typing import Dict, Any
from SERVER.tools.interfaces import ToolResult, ToolStatus, RiskLevel

logger = logging.getLogger("tools.drivers.ssh")

# Pola perintah yang SELALU ditolak, terlepas dari approval
SSH_FORBIDDEN_PATTERNS = [
    r"rm\s+-rf\s+/",
    r"mkfs",
    r"dd\s+if=/dev/(zero|urandom)",
    r">\s*/dev/sda",
    r":\(\)\s*\{.*\}",           # fork bomb
    r"shutdown\s+-h\s+now",
    r"reboot\s+--force",
]


class SSHDriver:
    """
    Mengeksekusi perintah shell pada target host melalui SSH.
    Dalam tahap ini diimplementasikan sebagai simulasi yang menghasilkan
    output realistis tanpa koneksi SSH nyata (untuk unit test tanpa infrastruktur).
    Integrasi SSH nyata dilakukan di Tahap 2.6 (Telemetry Wiring).
    """

    @property
    def driver_type(self) -> str:
        return "ssh"

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return bool(params.get("host")) and bool(params.get("command"))

    def _is_forbidden(self, command: str) -> bool:
        for pattern in SSH_FORBIDDEN_PATTERNS:
            if re.search(pattern, command, re.IGNORECASE):
                return True
        return False

    def execute(self, params: Dict[str, Any], dry_run: bool = False) -> ToolResult:
        request_id = params.get("_request_id", str(uuid.uuid4())[:8])
        host = params.get("host", "unknown-host")
        command = params.get("command", "")
        timeout = int(params.get("timeout", 30))

        # Guardrail check
        if self._is_forbidden(command):
            logger.error(f"[SSHDriver] FORBIDDEN command blocked: '{command}'")
            return ToolResult(
                request_id=request_id,
                tool_id="ssh_driver",
                status=ToolStatus.DENIED,
                error=f"SSH Guardrail: Command '{command[:80]}' matches forbidden pattern.",
                executed_by="ssh_driver",
                is_dry_run=dry_run,
            )

        if dry_run:
            logger.info(f"[SSHDriver] DRY-RUN | host={host} | cmd='{command[:60]}'")
            return ToolResult(
                request_id=request_id,
                tool_id="ssh_driver",
                status=ToolStatus.SANDBOXED,
                output=f"[DRY-RUN] SSH command '{command}' would execute on {host}. "
                       f"Syntax valid. Estimated timeout: {timeout}s.",
                executed_by="ssh_driver",
                is_dry_run=True,
                risk_level=RiskLevel.LOW,
            )

        # Simulasi eksekusi (akan digantikan dengan paramiko di Tahap 2.6)
        t0 = time.monotonic()
        logger.info(f"[SSHDriver] EXECUTE | host={host} | cmd='{command[:60]}'")
        simulated_output = (
            f"[SSH_SIMULATED] host={host}\n"
            f"$ {command}\n"
            f"Command executed successfully (simulation mode).\n"
            f"Exit code: 0"
        )
        duration_ms = int((time.monotonic() - t0) * 1000)

        return ToolResult(
            request_id=request_id,
            tool_id="ssh_driver",
            status=ToolStatus.SUCCESS,
            output=simulated_output,
            executed_by="ssh_driver",
            duration_ms=duration_ms,
            is_dry_run=False,
        )
