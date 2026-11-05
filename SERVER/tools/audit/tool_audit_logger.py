"""
SERVER.tools.audit — Tool Audit Logger
=======================================
Tahap 2.4 — Tool Execution Layer (Lapisan Keamanan 4/4)

ToolAuditLogger mencatat SETIAP eksekusi tool ke immutable audit trail.
Tidak ada eksekusi yang lewat tanpa dicatat, termasuk:
  - Permintaan yang DITOLAK (DENIED, REJECTED)
  - Permintaan yang menunggu approval (PENDING)
  - Eksekusi sandbox / dry-run
  - Eksekusi nyata (SUCCESS / FAILED)

Setiap record bersifat append-only dan tidak dapat dimodifikasi.
"""
import logging
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from SERVER.tools.interfaces import ToolRequest, ToolResult, ToolStatus, ApprovalStatus

logger = logging.getLogger("tools.audit.logger")


class AuditEntry:
    """Satu entri audit yang immutable setelah dibuat."""

    def __init__(
        self,
        request: ToolRequest,
        result: ToolResult,
        approval_status: ApprovalStatus,
        approved_by: Optional[str] = None,
    ):
        self.audit_id = f"AUD-{uuid.uuid4().hex[:10].upper()}"
        self.timestamp = datetime.now(timezone.utc).isoformat()
        self.request_id = request.request_id
        self.tool_id = request.tool_id
        self.incident_id = request.incident_id
        self.requestor_role = request.requestor_role
        self.severity = request.severity
        self.confidence = request.confidence
        self.params_summary = "; ".join(
            f"{k}={str(v)[:40]}" for k, v in (request.params or {}).items()
        )
        self.execution_status = result.status.value
        self.approval_status = approval_status.value
        self.approved_by = approved_by
        self.output_snippet = (result.output or "")[:200]
        self.error_snippet = (result.error or "")[:200]
        self.risk_level = result.risk_level.value
        self.risk_score = result.risk_score
        self.is_dry_run = result.is_dry_run
        self.duration_ms = result.duration_ms
        self.executed_by = result.executed_by

    def to_dict(self) -> Dict[str, Any]:
        return {
            "audit_id": self.audit_id,
            "timestamp": self.timestamp,
            "request_id": self.request_id,
            "tool_id": self.tool_id,
            "incident_id": self.incident_id,
            "requestor_role": self.requestor_role,
            "severity": self.severity,
            "confidence": self.confidence,
            "params_summary": self.params_summary,
            "execution_status": self.execution_status,
            "approval_status": self.approval_status,
            "approved_by": self.approved_by,
            "output_snippet": self.output_snippet,
            "error_snippet": self.error_snippet,
            "risk_level": self.risk_level,
            "risk_score": self.risk_score,
            "is_dry_run": self.is_dry_run,
            "duration_ms": self.duration_ms,
            "executed_by": self.executed_by,
        }


class ToolAuditLogger:
    """
    Mencatat semua tool execution events ke immutable audit trail.
    In-memory storage (dapat diperluas ke PostgreSQL/Elasticsearch di Level 3).
    """

    def __init__(self):
        self._entries: List[AuditEntry] = []

    def log(
        self,
        request: ToolRequest,
        result: ToolResult,
        approval_status: ApprovalStatus,
        approved_by: Optional[str] = None,
    ) -> str:
        """
        Mencatat satu eksekusi tool ke audit trail.

        Returns:
            audit_id: ID unik dari entri audit yang dibuat.
        """
        entry = AuditEntry(request, result, approval_status, approved_by)
        self._entries.append(entry)

        log_level = logging.WARNING if result.status in (ToolStatus.DENIED, ToolStatus.FAILED) else logging.INFO
        logger.log(
            log_level,
            f"[AuditLogger] audit_id={entry.audit_id} | tool={entry.tool_id} | "
            f"status={entry.execution_status} | approval={entry.approval_status} | "
            f"risk={entry.risk_level}({entry.risk_score}) | dry_run={entry.is_dry_run} | "
            f"incident={entry.incident_id}"
        )

        return entry.audit_id

    def get_recent(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Mengembalikan N entri audit terbaru (untuk Dashboard)."""
        return [e.to_dict() for e in self._entries[-limit:]]

    def get_by_incident(self, incident_id: str) -> List[Dict[str, Any]]:
        """Mengembalikan semua audit entries untuk satu incident."""
        return [
            e.to_dict() for e in self._entries
            if e.incident_id == incident_id
        ]

    def get_denied_entries(self) -> List[Dict[str, Any]]:
        """Mengembalikan semua permintaan yang ditolak (untuk security monitoring)."""
        return [
            e.to_dict() for e in self._entries
            if e.execution_status in ("DENIED", "REJECTED")
        ]

    @property
    def total_entries(self) -> int:
        return len(self._entries)
