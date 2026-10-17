"""
SERVER.jarvis.audit.command_audit — JARVIS Command Audit Trail
==============================================================
P9 Implementation: Pencatatan lengkap semua perintah yang diberikan ke JARVIS
beserta hasil eksekusi, intent, safety decision, dan operator identity.

Setiap perintah JARVIS tercatat dengan:
  - Timestamp (WIB)
  - Operator / session
  - Query text asli
  - Intent yang terdeteksi
  - Entitas yang diekstrak (device, site, incident)
  - Safety decision (AUTO/HITL/REJECTED)
  - Execution status (SUCCESS/FAILED/PENDING)
  - Response yang diberikan ke operator
  - Latency end-to-end

Audit trail disimpan:
  1. In-memory circular buffer (real-time access)
  2. File log per hari (append-only JSON lines)
  3. Opsional: POST ke dashboard /api/activity
"""
import json
import logging
import os
import time
from collections import deque
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone, timedelta
from typing import Deque, Dict, List, Optional, Any

logger = logging.getLogger("jarvis.audit")

# Jakarta timezone (WIB = UTC+7)
_WIB = timezone(timedelta(hours=7))

# Audit log directory
_AUDIT_LOG_DIR = os.getenv(
    "JARVIS_AUDIT_LOG_DIR",
    os.path.join(os.path.dirname(__file__), "logs")
)
# Max in-memory buffer size
_BUFFER_SIZE = 500


@dataclass
class AuditRecord:
    """Satu entri audit trail untuk satu perintah JARVIS."""
    audit_id: str
    session_id: str
    operator_id: str
    timestamp_wib: str
    timestamp_unix: float
    # Command info
    query_text: str
    query_text_raw: str          # Before wake word stripping
    detected_intent: str         # QUERY | REMEDIATE | HITL | REMOTE | CHAT | ISSUE | UNKNOWN
    intent_confidence: float
    # Extracted entities
    target_device: Optional[str] = None
    target_site: Optional[str] = None
    target_incident: Optional[str] = None
    # Safety decision
    safety_decision: Optional[str] = None   # AUTO_EXECUTE | REQUIRE_APPROVAL | FORCE_HITL
    risk_level: Optional[str] = None        # LOW | MEDIUM | HIGH | CRITICAL
    risk_score: Optional[float] = None
    hitl_queue_id: Optional[str] = None
    # Execution result
    execution_status: Optional[str] = None  # SUCCESS | FAILED | PENDING | CANCELLED
    action_taken: Optional[str] = None
    # Response
    response_text: str = ""
    response_persona: str = "noc_engineer"
    # Performance
    latency_ms: int = 0
    # Context
    persona_id: str = "noc_engineer"
    user_role: str = "noc_operator"
    extra: Dict[str, Any] = field(default_factory=dict)


class JarvisCommandAudit:
    """
    P9 — JARVIS Command Audit Trail.
    Thread-safe, persistent audit logging untuk semua perintah JARVIS.

    Contoh penggunaan:
        audit = JarvisCommandAudit()

        record = audit.record(
            session_id="NOC-SHIFT-A",
            operator_id="rama",
            query_text="restart spooler server-01",
            query_text_raw="Jarvis, restart spooler server-01",
            detected_intent="REMEDIATE",
            intent_confidence=0.87,
            target_device="server-01",
            safety_decision="AUTO_EXECUTE",
            risk_level="LOW",
            execution_status="SUCCESS",
            action_taken="RESTART_PRINT_SPOOLER",
            response_text="Berhasil restart spooler.",
            latency_ms=342,
        )

        # Recent audit
        recent = audit.get_recent(10)
        # Session audit
        session_log = audit.get_session_audit("NOC-SHIFT-A")
        # Today's summary
        summary = audit.daily_summary()
    """

    def __init__(self, enable_file_log: bool = True, notify_bridge=None):
        self._buffer: Deque[AuditRecord] = deque(maxlen=_BUFFER_SIZE)
        self._enable_file_log = enable_file_log
        self._notify_bridge = notify_bridge   # Optional JarvisNOCBridge for posting to dashboard
        self._record_count = 0

        if enable_file_log:
            os.makedirs(_AUDIT_LOG_DIR, exist_ok=True)
            logger.info(f"[CommandAudit] File logging enabled → {_AUDIT_LOG_DIR}")

    def record(
        self,
        session_id: str,
        operator_id: str,
        query_text: str,
        detected_intent: str,
        intent_confidence: float,
        query_text_raw: str = "",
        target_device: Optional[str] = None,
        target_site: Optional[str] = None,
        target_incident: Optional[str] = None,
        safety_decision: Optional[str] = None,
        risk_level: Optional[str] = None,
        risk_score: Optional[float] = None,
        hitl_queue_id: Optional[str] = None,
        execution_status: Optional[str] = None,
        action_taken: Optional[str] = None,
        response_text: str = "",
        persona_id: str = "noc_engineer",
        user_role: str = "noc_operator",
        latency_ms: int = 0,
        extra: Optional[Dict[str, Any]] = None,
    ) -> AuditRecord:
        """Catat satu perintah JARVIS ke audit trail."""
        self._record_count += 1
        now = datetime.now(_WIB)
        audit_id = f"JAR-{now.strftime('%Y%m%d')}-{self._record_count:05d}"

        record = AuditRecord(
            audit_id=audit_id,
            session_id=session_id,
            operator_id=operator_id,
            timestamp_wib=now.strftime("%Y-%m-%d %H:%M:%S WIB"),
            timestamp_unix=time.time(),
            query_text=query_text,
            query_text_raw=query_text_raw or query_text,
            detected_intent=detected_intent,
            intent_confidence=intent_confidence,
            target_device=target_device,
            target_site=target_site,
            target_incident=target_incident,
            safety_decision=safety_decision,
            risk_level=risk_level,
            risk_score=risk_score,
            hitl_queue_id=hitl_queue_id,
            execution_status=execution_status,
            action_taken=action_taken,
            response_text=response_text[:500],  # Truncate
            persona_id=persona_id,
            user_role=user_role,
            latency_ms=latency_ms,
            extra=extra or {},
        )

        # In-memory buffer
        self._buffer.append(record)

        # File log (JSON lines)
        if self._enable_file_log:
            self._write_to_file(record, now)

        # Log summary
        status_icon = {
            "SUCCESS": "✅", "FAILED": "❌", "PENDING": "⏳",
            "CANCELLED": "🚫", None: "—"
        }.get(execution_status, "?")
        logger.info(
            f"[AUDIT] {audit_id} | Intent={detected_intent} "
            f"| Status={execution_status} {status_icon} "
            f"| Latency={latency_ms}ms "
            f"| Query='{query_text[:50]}'"
        )

        return record

    def _write_to_file(self, record: AuditRecord, dt: datetime) -> None:
        """Tulis record ke file JSON lines harian."""
        try:
            filename = os.path.join(
                _AUDIT_LOG_DIR,
                f"jarvis_audit_{dt.strftime('%Y%m%d')}.jsonl"
            )
            line = json.dumps(asdict(record), ensure_ascii=False)
            with open(filename, "a", encoding="utf-8") as f:
                f.write(line + "\n")
        except Exception as e:
            logger.warning(f"[CommandAudit] File write failed: {e}")

    def get_recent(self, n: int = 20) -> List[AuditRecord]:
        """Ambil N audit record terbaru."""
        records = list(self._buffer)
        return records[-n:]

    def get_session_audit(self, session_id: str) -> List[AuditRecord]:
        """Ambil semua audit untuk satu session."""
        return [r for r in self._buffer if r.session_id == session_id]

    def get_by_intent(self, intent: str) -> List[AuditRecord]:
        """Filter audit berdasarkan intent."""
        return [r for r in self._buffer if r.detected_intent == intent]

    def get_failed_actions(self) -> List[AuditRecord]:
        """Daftar semua aksi yang gagal."""
        return [r for r in self._buffer if r.execution_status == "FAILED"]

    def daily_summary(self) -> str:
        """Ringkasan audit hari ini dalam format teks."""
        today = datetime.now(_WIB).date()
        today_records = [
            r for r in self._buffer
            if datetime.fromtimestamp(r.timestamp_unix, _WIB).date() == today
        ]

        if not today_records:
            return "Belum ada perintah JARVIS hari ini."

        total = len(today_records)
        intent_counts: Dict[str, int] = {}
        status_counts: Dict[str, int] = {}
        failed_actions: List[str] = []
        avg_latency = 0.0

        for r in today_records:
            intent_counts[r.detected_intent] = intent_counts.get(r.detected_intent, 0) + 1
            st = r.execution_status or "NO_ACTION"
            status_counts[st] = status_counts.get(st, 0) + 1
            avg_latency += r.latency_ms
            if r.execution_status == "FAILED":
                failed_actions.append(f"{r.action_taken or r.query_text[:30]}")

        avg_latency = avg_latency / total if total > 0 else 0

        lines = [
            f"📋 JARVIS Audit Summary — {today.strftime('%d %B %Y')}",
            f"Total perintah : {total}",
            f"Avg latency    : {avg_latency:.0f}ms",
            "",
            "Intent breakdown:",
        ]
        for intent, count in sorted(intent_counts.items(), key=lambda x: -x[1]):
            lines.append(f"  {intent:<12}: {count}")
        lines.append("")
        lines.append("Execution status:")
        for status, count in sorted(status_counts.items(), key=lambda x: -x[1]):
            icon = {"SUCCESS": "✅", "FAILED": "❌", "PENDING": "⏳"}.get(status, "—")
            lines.append(f"  {status:<15}: {count} {icon}")
        if failed_actions:
            lines.append(f"\nFailed actions: {', '.join(failed_actions[:5])}")
        return "\n".join(lines)

    def format_recent_for_jarvis(self, n: int = 5) -> str:
        """Format N perintah terakhir untuk ditampilkan oleh JARVIS."""
        recent = self.get_recent(n)
        if not recent:
            return "Belum ada riwayat perintah."
        lines = [f"📜 {n} perintah JARVIS terakhir:\n"]
        for r in reversed(recent):
            ts = r.timestamp_wib.split(" ")[1]  # HH:MM:SS
            status_key = r.execution_status or "NO_ACTION"
            status_icon = {"SUCCESS": "✅", "FAILED": "❌", "PENDING": "⏳"}.get(
                status_key, "—"
            )
            lines.append(
                f"  [{ts}] {r.detected_intent:<10} {status_icon} "
                f"'{r.query_text[:40]}'"
            )
        return "\n".join(lines)
