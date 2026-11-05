"""
SERVER.tools.approval — Approval Manager (HITL)
================================================
Tahap 2.4 — Tool Execution Layer (Lapisan Keamanan 3/4)

Posisi dalam alur keamanan:
  ToolDispatcher → [ApprovalManager] → PolicyEngine → RiskClassifier → Driver

ApprovalManager mengelola Human-In-The-Loop (HITL):
  - AUTO_APPROVED: confidence >= 92% AND risk LOW AND policy pass
  - PENDING: menunggu persetujuan operator via Dashboard AI NOC
  - REJECTED: operator menolak atau timeout habis
  - FORCE_HITL: selalu butuh manusia (CRITICAL severity, HIGH risk, etc.)

ApprovalManager TIDAK berkomunikasi langsung dengan Dashboard.
Dashboard membaca approval queue melalui event bus (NATS JetStream).
"""
import logging
import uuid
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from SERVER.tools.interfaces import (
    ApprovalStatus, ToolRequest, RiskAssessment, PolicyDecision
)

logger = logging.getLogger("tools.approval.manager")

# ── Auto-Approval Thresholds ───────────────────────────────────────────────────
AUTO_APPROVE_MIN_CONFIDENCE = 0.92   # >= 92% confidence
AUTO_APPROVE_MAX_RISK_SCORE = 35     # Risk score <= 35 (LOW range)

# ── Approval Timeout ───────────────────────────────────────────────────────────
APPROVAL_TIMEOUT_SECONDS = 300       # 5 menit — setelah itu dianggap REJECTED



class ApprovalRecord:
    """Catatan approval yang tersimpan dalam approval queue."""

    def __init__(
        self,
        request_id: str,
        tool_id: str,
        incident_id: str,
        risk_level: str,
        risk_score: int,
        policy_reason: str,
        requestor_role: str,
        params_summary: str,
    ):
        self.approval_id = f"APR-{uuid.uuid4().hex[:8].upper()}"
        self.request_id = request_id
        self.tool_id = tool_id
        self.incident_id = incident_id
        self.risk_level = risk_level
        self.risk_score = risk_score
        self.policy_reason = policy_reason
        self.requestor_role = requestor_role
        self.params_summary = params_summary
        self.status = ApprovalStatus.PENDING
        self.created_at = datetime.now(timezone.utc)
        self.expires_at = self.created_at + timedelta(seconds=APPROVAL_TIMEOUT_SECONDS)
        self.approved_by: Optional[str] = None
        self.rejection_reason: Optional[str] = None

    def is_expired(self) -> bool:
        return datetime.now(timezone.utc) > self.expires_at

    def approve(self, approved_by: str = "operator") -> None:
        self.status = ApprovalStatus.APPROVED
        self.approved_by = approved_by

    def reject(self, reason: str = "Operator rejected") -> None:
        self.status = ApprovalStatus.REJECTED
        self.rejection_reason = reason

    def to_dict(self) -> Dict[str, Any]:
        return {
            "approval_id": self.approval_id,
            "request_id": self.request_id,
            "tool_id": self.tool_id,
            "incident_id": self.incident_id,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "policy_reason": self.policy_reason,
            "requestor_role": self.requestor_role,
            "params_summary": self.params_summary,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "expires_at": self.expires_at.isoformat(),
            "approved_by": self.approved_by,
            "rejection_reason": self.rejection_reason,
        }


class ApprovalManager:
    """
    Mengelola siklus hidup HITL approval untuk setiap ToolRequest.
    Menyimpan approval queue dalam memori (dapat diperluas ke Redis/DB).
    """

    def __init__(self):
        # In-memory approval queue: {approval_id: ApprovalRecord}
        self._queue: Dict[str, ApprovalRecord] = {}

    def evaluate(
        self,
        request: ToolRequest,
        risk: RiskAssessment,
        policy: PolicyDecision,
    ) -> ApprovalStatus:
        """
        Menentukan apakah request dapat auto-approved atau perlu HITL.

        Logic:
          1. Jika policy tidak mengizinkan → REJECTED langsung.
          2. Jika policy/risk requires_hitl = True → PENDING (dikirim ke queue).
          3. Jika confidence >= 92% AND risk_score <= 35 → AUTO_APPROVED.
          4. Selainnya → PENDING (perlu approval operator).

        Returns:
            ApprovalStatus untuk request ini.
        """
        # 1. Policy deny = langsung REJECTED tanpa queue
        if not policy.allowed:
            logger.warning(
                f"[ApprovalManager] REJECTED by policy | "
                f"tool={request.tool_id} | reason={policy.reason}"
            )
            return ApprovalStatus.REJECTED

        # 2. Evaluasi auto-approve criteria
        confidence = float(request.confidence or 0.0)
        if confidence > 1.0:
            confidence /= 100.0

        can_auto_approve = (
            confidence >= AUTO_APPROVE_MIN_CONFIDENCE
            and risk.risk_score <= AUTO_APPROVE_MAX_RISK_SCORE
            and not policy.requires_hitl
            and not risk.requires_hitl
        )

        if can_auto_approve:
            logger.info(
                f"[ApprovalManager] AUTO_APPROVED | tool={request.tool_id} | "
                f"confidence={confidence:.2f} | risk_score={risk.risk_score}"
            )
            return ApprovalStatus.AUTO_APPROVED

        # 3. Semua kasus lainnya → buat ApprovalRecord dan masukkan ke queue
        params_summary = "; ".join(
            f"{k}={str(v)[:40]}" for k, v in (request.params or {}).items()
        )
        record = ApprovalRecord(
            request_id=request.request_id,
            tool_id=request.tool_id,
            incident_id=request.incident_id,
            risk_level=risk.risk_level.value,
            risk_score=risk.risk_score,
            policy_reason=policy.reason,
            requestor_role=request.requestor_role,
            params_summary=params_summary,
        )
        self._queue[record.approval_id] = record

        status = ApprovalStatus.FORCE_HITL if policy.requires_hitl else ApprovalStatus.PENDING
        logger.info(
            f"[ApprovalManager] {status.value} | tool={request.tool_id} | "
            f"approval_id={record.approval_id} | risk_level={risk.risk_level.value} | "
            f"expires={record.expires_at.isoformat()}"
        )
        return status

    def approve(self, approval_id: str, approved_by: str = "operator") -> bool:
        """Operator menyetujui approval dari Dashboard AI NOC."""
        record = self._queue.get(approval_id)
        if not record:
            logger.error(f"[ApprovalManager] Approval not found: {approval_id}")
            return False
        if record.is_expired():
            logger.warning(f"[ApprovalManager] Approval expired: {approval_id}")
            record.reject("Approval timeout expired")
            return False
        record.approve(approved_by)
        logger.info(f"[ApprovalManager] APPROVED by {approved_by}: {approval_id}")
        return True

    def reject(self, approval_id: str, reason: str = "Operator rejected") -> bool:
        """Operator menolak approval dari Dashboard AI NOC."""
        record = self._queue.get(approval_id)
        if not record:
            logger.error(f"[ApprovalManager] Approval not found: {approval_id}")
            return False
        record.reject(reason)
        logger.info(f"[ApprovalManager] REJECTED: {approval_id} | reason={reason}")
        return True

    def get_pending(self) -> List[Dict[str, Any]]:
        """Mengembalikan semua approval yang masih menunggu (untuk Dashboard polling)."""
        self._cleanup_expired()
        return [
            r.to_dict()
            for r in self._queue.values()
            if r.status in (ApprovalStatus.PENDING, ApprovalStatus.FORCE_HITL)
        ]

    def get_record(self, approval_id: str) -> Optional[Dict[str, Any]]:
        record = self._queue.get(approval_id)
        return record.to_dict() if record else None

    def _cleanup_expired(self) -> None:
        expired = [
            aid for aid, r in self._queue.items()
            if r.is_expired() and r.status == ApprovalStatus.PENDING
        ]
        for aid in expired:
            self._queue[aid].reject("Approval timeout expired")
            logger.info(f"[ApprovalManager] Auto-expired: {aid}")

    @property
    def queue_size(self) -> int:
        return len(self._queue)
