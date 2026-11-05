"""
SERVER.tools.dispatcher — Tool Dispatcher
==========================================
Tahap 2.4 — Tool Execution Layer

ToolDispatcher adalah SATU-SATUNYA entry point ke seluruh tool execution system.
Tidak ada driver yang boleh dipanggil langsung oleh LLM, Jarvis, atau Orchestrator.

ALUR KEAMANAN (wajib dilalui setiap ToolRequest):
═══════════════════════════════════════════════════════════════════════════════
  [ToolRequest] → ToolDispatcher
                      │
                      ▼
                 [1] RiskClassifier          ← Hitung risk score & blast radius
                      │
                      ▼
                 [2] ToolPolicyEngine        ← Terapkan RBAC, maintenance lock,
                      │                         business hours, critical gate
                      ▼
                 [3] ApprovalManager         ← HITL: auto-approve atau queue
                      │
                      ▼
                 [4] SandboxExecutor         ← Dry-run validasi sebelum eksekusi
                      │ (jika force_sandbox / pending approval)
                      │
                      ▼
                 [5] Driver                  ← SSH / Docker / MikroTik / REST
                      │
                      ▼
                 [6] ToolAuditLogger         ← Immutable audit trail (selalu)
═══════════════════════════════════════════════════════════════════════════════

ATURAN KERAS yang tidak boleh dilanggar:
  1. LLM tidak boleh memanggil driver secara langsung.
  2. Jarvis tidak boleh memanggil driver secara langsung.
  3. Orchestrator hanya boleh memanggil ToolDispatcher.dispatch().
  4. Setiap aksi SELALU dicatat di ToolAuditLogger, bahkan yang ditolak.
  5. CRITICAL risk dan AI auto-exec pada driver berbahaya SELALU HITL.
"""
import logging
import uuid
import time
from typing import Dict, Any, Optional, Tuple

from SERVER.tools.interfaces import (
    ToolRequest, ToolResult, ToolStatus, ApprovalStatus, RiskLevel,
    PolicyDecision, RiskAssessment,
)
from SERVER.tools.risk import RiskClassifier
from SERVER.tools.policy import ToolPolicyEngine
from SERVER.tools.approval import ApprovalManager
from SERVER.tools.sandbox import SandboxExecutor
from SERVER.tools.audit import ToolAuditLogger
from SERVER.tools.drivers import DRIVER_REGISTRY

logger = logging.getLogger("tools.dispatcher")


class ToolDispatcher:
    """
    Satu-satunya entry point ke Tool Execution System.
    Mengorkestrasikan 4 lapisan keamanan sebelum driver dieksekusi.
    """

    def __init__(self, maintenance_mode: bool = False):
        self._risk_classifier = RiskClassifier()
        self._policy_engine = ToolPolicyEngine(maintenance_mode=maintenance_mode)
        self._approval_manager = ApprovalManager()
        self._sandbox_executor = SandboxExecutor()
        self._audit_logger = ToolAuditLogger()

    # ── Public API ─────────────────────────────────────────────────────────────

    def dispatch(self, request: ToolRequest) -> ToolResult:
        """
        Entry point utama. Menjalankan seluruh pipeline keamanan.

        Args:
            request: ToolRequest dari Orchestrator/Integration layer.

        Returns:
            ToolResult: Hasil akhir eksekusi atau penolakan.
        """
        t0 = time.monotonic()
        logger.info(
            f"[ToolDispatcher] DISPATCH | request_id={request.request_id} | "
            f"tool={request.tool_id} | role={request.requestor_role} | "
            f"incident={request.incident_id}"
        )

        # Resolve driver type dari tool_id (format: "<driver_type>:<action>")
        driver_type = self._resolve_driver_type(request.tool_id)
        if driver_type not in DRIVER_REGISTRY:
            result = ToolResult(
                request_id=request.request_id,
                tool_id=request.tool_id,
                status=ToolStatus.FAILED,
                error=f"No registered driver for tool_id='{request.tool_id}' "
                      f"(resolved driver_type='{driver_type}').",
                executed_by="tool_dispatcher",
            )
            self._audit_logger.log(request, result, ApprovalStatus.REJECTED)
            return result

        # ── Layer 1: Risk Classification ────────────────────────────────────
        risk = self._risk_classifier.classify(request, driver_type)

        # ── Layer 2: Policy Evaluation ───────────────────────────────────────
        policy = self._policy_engine.evaluate(request, driver_type, risk.risk_level)

        # ── Layer 3: Approval (HITL) Decision ────────────────────────────────
        approval_status = self._approval_manager.evaluate(request, risk, policy)

        # Policy denied → tidak perlu sandbox atau driver
        if not policy.allowed:
            result = ToolResult(
                request_id=request.request_id,
                tool_id=request.tool_id,
                status=ToolStatus.DENIED,
                error=f"Policy denied: {policy.reason}",
                approval_status=approval_status,
                risk_level=risk.risk_level,
                risk_score=risk.risk_score,
                executed_by="tool_dispatcher",
                duration_ms=int((time.monotonic() - t0) * 1000),
            )
            self._audit_logger.log(request, result, approval_status)
            return result

        # Pending approval → jalankan sandbox saja (tidak eksekusi nyata)
        if approval_status in (ApprovalStatus.PENDING, ApprovalStatus.FORCE_HITL):
            sandbox_result = self._sandbox_executor.execute_dry_run(request, driver_type)
            sandbox_result.approval_status = approval_status
            sandbox_result.risk_level = risk.risk_level
            sandbox_result.risk_score = risk.risk_score
            sandbox_result.status = ToolStatus.PENDING_APPROVAL
            sandbox_result.duration_ms = int((time.monotonic() - t0) * 1000)
            self._audit_logger.log(request, sandbox_result, approval_status)
            return sandbox_result

        # Policy force_sandbox → jalankan sandbox, kembalikan hasil sandbox
        if policy.force_sandbox:
            sandbox_result = self._sandbox_executor.execute_dry_run(request, driver_type)
            sandbox_result.approval_status = approval_status
            sandbox_result.risk_level = risk.risk_level
            sandbox_result.risk_score = risk.risk_score
            sandbox_result.duration_ms = int((time.monotonic() - t0) * 1000)
            self._audit_logger.log(request, sandbox_result, approval_status)
            return sandbox_result

        # ── Layer 4: Sandbox Pre-validation (selalu, sebelum eksekusi nyata) ─
        sandbox_pre = self._sandbox_executor.execute_dry_run(request, driver_type)
        if sandbox_pre.status == ToolStatus.DENIED:
            # Driver guardrail menolak bahkan di dry-run → batalkan eksekusi
            sandbox_pre.approval_status = approval_status
            sandbox_pre.duration_ms = int((time.monotonic() - t0) * 1000)
            self._audit_logger.log(request, sandbox_pre, approval_status)
            logger.warning(
                f"[ToolDispatcher] Sandbox pre-validation DENIED | tool={request.tool_id}"
            )
            return sandbox_pre

        # ── Layer 5: Driver Execution ─────────────────────────────────────────
        driver = DRIVER_REGISTRY[driver_type]()
        params = dict(request.params or {})
        params["_request_id"] = request.request_id

        try:
            result = driver.execute(params, dry_run=False)
        except Exception as exc:
            logger.error(f"[ToolDispatcher] Driver {driver_type} exception: {exc}")
            result = ToolResult(
                request_id=request.request_id,
                tool_id=request.tool_id,
                status=ToolStatus.FAILED,
                error=f"Driver exception: {exc}",
                executed_by=driver_type,
            )

        result.approval_status = approval_status
        result.risk_level = risk.risk_level
        result.risk_score = risk.risk_score
        result.duration_ms = int((time.monotonic() - t0) * 1000)

        # ── Layer 6: Audit Trail (ALWAYS logged) ─────────────────────────────
        audit_id = self._audit_logger.log(request, result, approval_status)
        result.audit_id = audit_id

        logger.info(
            f"[ToolDispatcher] COMPLETE | request_id={request.request_id} | "
            f"status={result.status.value} | risk={risk.risk_level.value}({risk.risk_score}) | "
            f"duration={result.duration_ms}ms | audit_id={audit_id}"
        )
        return result

    # ── Maintenance Mode Control ───────────────────────────────────────────────

    def set_maintenance_mode(self, enabled: bool) -> None:
        """Mengaktifkan/menonaktifkan maintenance mode pada PolicyEngine."""
        self._policy_engine.set_maintenance_mode(enabled)

    # ── Approval Queue API (untuk Dashboard) ──────────────────────────────────

    def approve_pending(self, approval_id: str, approved_by: str = "operator") -> bool:
        """Dashboard memanggil ini saat operator menyetujui approval."""
        return self._approval_manager.approve(approval_id, approved_by)

    def reject_pending(self, approval_id: str, reason: str = "Operator rejected") -> bool:
        """Dashboard memanggil ini saat operator menolak approval."""
        return self._approval_manager.reject(approval_id, reason)

    def get_pending_approvals(self):
        """Dashboard polling untuk menampilkan approval queue."""
        return self._approval_manager.get_pending()

    def get_audit_trail(self, limit: int = 50):
        """Dashboard membaca audit trail terbaru."""
        return self._audit_logger.get_recent(limit)

    # ── Internal Helpers ──────────────────────────────────────────────────────

    @staticmethod
    def _resolve_driver_type(tool_id: str) -> str:
        """
        Mengekstrak driver_type dari tool_id.
        Format: "<driver_type>:<action>" atau "<driver_type>"
        Contoh: "ssh:restart_service" → "ssh"
                "docker:restart" → "docker"
                "mikrotik" → "mikrotik"
        """
        return tool_id.split(":")[0].lower()
