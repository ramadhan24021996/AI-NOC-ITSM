"""
SERVER.tools.drivers.mikrotik_driver — MikroTik RouterOS Driver
================================================================
Tahap 2.4 — Tool Execution Layer

Driver untuk MikroTik RouterOS API (RouterOS REST API atau Winbox API).
Operasi jaringan yang salah dapat mengisolasi seluruh site — blast radius DATACENTER.
Seluruh operasi yang tidak bersifat read-only WAJIB melewati HITL.
"""
import logging
import time
import uuid
from typing import Dict, Any
from SERVER.tools.interfaces import ToolResult, ToolStatus, RiskLevel

logger = logging.getLogger("tools.drivers.mikrotik")

# Read-only operations — boleh auto-approved jika confidence tinggi
MIKROTIK_READ_OPS = {
    "get_interface_status", "get_routes", "get_neighbors",
    "get_arp_table", "ping", "traceroute", "get_firewall_rules",
    "get_dhcp_leases", "get_health",
}

# Write operations — WAJIB HITL tanpa pengecualian
MIKROTIK_WRITE_OPS = {
    "add_route", "delete_route", "block_ip", "unblock_ip",
    "enable_interface", "disable_interface", "restart_interface",
    "set_bandwidth_limit", "add_firewall_rule", "delete_firewall_rule",
    "factory_reset",
}


class MikrotikDriver:
    """
    Mengeksekusi perintah RouterOS API pada perangkat MikroTik.
    Implementasi saat ini adalah simulasi (tanpa koneksi RouterOS nyata).
    Integrasi RouterOS API nyata dilakukan di Tahap 2.6.
    """

    @property
    def driver_type(self) -> str:
        return "mikrotik"

    def validate_params(self, params: Dict[str, Any]) -> bool:
        return bool(params.get("host")) and bool(params.get("operation"))

    def execute(self, params: Dict[str, Any], dry_run: bool = False) -> ToolResult:
        request_id = params.get("_request_id", str(uuid.uuid4())[:8])
        host = params.get("host", "unknown-router")
        operation = params.get("operation", "").lower()

        # Write ops SELALU butuh HITL — driver menolak jika tidak dry_run
        if operation in MIKROTIK_WRITE_OPS and not dry_run:
            return ToolResult(
                request_id=request_id,
                tool_id="mikrotik_driver",
                status=ToolStatus.DENIED,
                error=(
                    f"MikroTik write operation '{operation}' requires mandatory "
                    f"HITL approval. Network changes can isolate entire sites."
                ),
                executed_by="mikrotik_driver",
                risk_level=RiskLevel.HIGH,
            )

        if dry_run:
            logger.info(f"[MikrotikDriver] DRY-RUN | host={host} | op={operation}")
            return ToolResult(
                request_id=request_id,
                tool_id="mikrotik_driver",
                status=ToolStatus.SANDBOXED,
                output=f"[DRY-RUN] RouterOS '{operation}' on {host} — validated, not applied.",
                executed_by="mikrotik_driver",
                is_dry_run=True,
                risk_level=RiskLevel.HIGH,
            )

        # Read-only simulation
        t0 = time.monotonic()
        simulated = f"[MIKROTIK_SIMULATED] {host}: {operation} → data returned OK\n"
        duration_ms = int((time.monotonic() - t0) * 1000)
        logger.info(f"[MikrotikDriver] READ | host={host} | op={operation}")

        return ToolResult(
            request_id=request_id,
            tool_id="mikrotik_driver",
            status=ToolStatus.SUCCESS,
            output=simulated,
            executed_by="mikrotik_driver",
            duration_ms=duration_ms,
        )
