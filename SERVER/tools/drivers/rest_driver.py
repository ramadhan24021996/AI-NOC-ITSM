"""
SERVER.tools.drivers.rest_driver — REST API Driver
===================================================
Tahap 2.4 — Tool Execution Layer

Driver untuk REST API calls (Netdata, Zabbix, ServiceNow, internal services).
GET requests dapat auto-approved. POST/PUT/DELETE memerlukan policy check.
"""
import logging
import time
import uuid
from typing import Dict, Any
from SERVER.tools.interfaces import ToolResult, ToolStatus

logger = logging.getLogger("tools.drivers.rest")

SAFE_METHODS = {"GET", "HEAD", "OPTIONS"}
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


class RESTDriver:
    """
    Mengeksekusi REST API calls ke layanan eksternal atau internal.
    Implementasi saat ini adalah simulasi.
    """

    @property
    def driver_type(self) -> str:
        return "rest"

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return bool(params.get("url")) and bool(params.get("method"))

    def execute(self, params: Dict[str, Any], dry_run: bool = False) -> ToolResult:
        request_id = params.get("_request_id", str(uuid.uuid4())[:8])
        url = params.get("url", "")
        method = params.get("method", "GET").upper()
        body = params.get("body", {})

        if dry_run:
            return ToolResult(
                request_id=request_id,
                tool_id="rest_driver",
                status=ToolStatus.SANDBOXED,
                output=f"[DRY-RUN] {method} {url} — request validated, not sent.",
                executed_by="rest_driver",
                is_dry_run=True,
            )

        t0 = time.monotonic()
        simulated_response = {
            "status_code": 200,
            "body": {"result": "simulated", "url": url, "method": method},
        }
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(f"[RESTDriver] {method} {url[:80]} | simulation OK")

        return ToolResult(
            request_id=request_id,
            tool_id="rest_driver",
            status=ToolStatus.SUCCESS,
            output=str(simulated_response),
            executed_by="rest_driver",
            duration_ms=duration_ms,
        )
