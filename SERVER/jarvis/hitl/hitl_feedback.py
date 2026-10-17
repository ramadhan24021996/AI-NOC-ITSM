"""
SERVER.jarvis.hitl.hitl_feedback — JARVIS HITL Feedback Loop
=============================================================
P4 Implementation: Human-in-the-Loop feedback loop yang:
  1. Menerima dan menyimpan aksi yang menunggu approval (HITL Queue)
  2. Menerima keputusan approve/reject dari operator via JARVIS
  3. Me-relay keputusan ke ExcecutionEngine atau membatalkan aksi
  4. Mengirim notifikasi ke operator saat ada aksi yang tertahan

Flow:
  AISafetyLayer → HITL_QUEUED
  → JarvisHITLFeedback.enqueue(action)
  → Operator: "Jarvis, approve INC-001"
  → JarvisHITLFeedback.process_decision(incident_id, "APPROVE", operator)
  → ExecutionEngine.execute(action)
"""
import logging
import time
import uuid
from enum import Enum
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("jarvis.hitl.feedback")


class HITLDecision(str, Enum):
    APPROVE  = "APPROVE"
    REJECT   = "REJECT"
    ESCALATE = "ESCALATE"
    DEFER    = "DEFER"
    OVERRIDE = "OVERRIDE"


@dataclass
class HITLQueueItem:
    """Satu aksi yang menunggu approval manusia."""
    queue_id: str
    incident_id: str
    device: str
    candidate_action: str
    risk_level: str
    risk_score: float
    blast_radius: int
    policy_effect: str
    llm_confidence: float
    created_at: float = field(default_factory=time.time)
    status: str = "PENDING"          # PENDING | APPROVED | REJECTED | ESCALATED | EXPIRED
    decided_by: Optional[str] = None
    decided_at: Optional[float] = None
    decision_note: str = ""
    notify_channels: List[str] = field(default_factory=lambda: ["jarvis", "telegram"])


@dataclass
class HITLDecisionResult:
    """Hasil keputusan HITL."""
    queue_id: str
    incident_id: str
    decision: HITLDecision
    executed: bool = False
    message: str = ""
    next_action: str = ""      # EXECUTE | CANCEL | ESCALATE_L2 | ESCALATE_L3


class JarvisHITLFeedback:
    """
    P4 — JARVIS HITL Feedback Loop.

    In-memory queue untuk aksi yang tertahan (persisten bisa ditambahkan
    via database/Redis di production).

    Penggunaan:
        hitl = JarvisHITLFeedback()

        # Safety layer enqueue
        item = hitl.enqueue(
            incident_id="INC-001",
            device="server-01",
            candidate_action="REBOOT_SERVER",
            risk_level="HIGH",
            risk_score=0.82,
            blast_radius=5,
            policy_effect="FORCE_HITL",
            llm_confidence=0.91,
        )
        notification = hitl.format_notification(item)

        # Operator approve via JARVIS
        result = hitl.process_decision(
            incident_id="INC-001",
            decision=HITLDecision.APPROVE,
            operator_id="operator-rama",
            note="Sudah dikonfirmasi dengan manager"
        )
    """

    def __init__(self, execution_callback=None, notify_callback=None):
        """
        Args:
            execution_callback: Callable(action: HITLQueueItem) → bool
                Dipanggil saat action di-APPROVE. Default None (log only).
            notify_callback: Callable(message: str, channels: List[str]) → None
                Dipanggil untuk notifikasi ke operator/telegram. Default None.
        """
        self._queue: Dict[str, HITLQueueItem] = {}  # queue_id → item
        self._incident_map: Dict[str, str] = {}       # incident_id → queue_id
        self._execution_callback = execution_callback
        self._notify_callback = notify_callback
        self._ttl_seconds = 3600  # Expire setelah 1 jam
        logger.info("[HITLFeedback] HITL Feedback Loop initialized.")

    # ── Enqueue ──────────────────────────────────────────────────────────────

    def enqueue(
        self,
        incident_id: str,
        device: str,
        candidate_action: str,
        risk_level: str,
        risk_score: float,
        blast_radius: int,
        policy_effect: str,
        llm_confidence: float,
        notify_channels: Optional[List[str]] = None,
    ) -> HITLQueueItem:
        """Masukkan aksi ke HITL queue dan kirim notifikasi."""
        qid = f"HITL-{incident_id}-{uuid.uuid4().hex[:8].upper()}"
        item = HITLQueueItem(
            queue_id=qid,
            incident_id=incident_id,
            device=device,
            candidate_action=candidate_action,
            risk_level=risk_level,
            risk_score=risk_score,
            blast_radius=blast_radius,
            policy_effect=policy_effect,
            llm_confidence=llm_confidence,
            notify_channels=notify_channels or ["jarvis", "telegram"],
        )
        self._queue[qid] = item
        self._incident_map[incident_id.upper()] = qid
        logger.warning(
            f"[HITLFeedback] 🔴 ENQUEUED: {qid} | Action={candidate_action} "
            f"| Risk={risk_level}({risk_score:.2f}) | Device={device}"
        )
        # Send notification
        notif = self.format_notification(item)
        self._send_notification(notif, item.notify_channels)
        return item

    # ── Process Decision ──────────────────────────────────────────────────────

    def process_decision(
        self,
        incident_id: str,
        decision: HITLDecision,
        operator_id: str = "jarvis_operator",
        note: str = "",
    ) -> HITLDecisionResult:
        """
        Proses keputusan approve/reject dari operator.
        Dipanggil ketika JARVIS menerima perintah:
          "Jarvis, approve INC-001"
          "Jarvis, reject aksi INC-002"
        """
        inc_key = incident_id.upper()
        qid = self._incident_map.get(inc_key)
        if not qid:
            # Try partial match
            for k in self._incident_map:
                if inc_key in k or k in inc_key:
                    qid = self._incident_map[k]
                    break

        if not qid or qid not in self._queue:
            return HITLDecisionResult(
                queue_id="NOTFOUND",
                incident_id=incident_id,
                decision=decision,
                executed=False,
                message=f"❌ Tidak ada aksi HITL untuk insiden {incident_id}. "
                        f"Queue aktif: {self.pending_count()} item.",
                next_action="NONE",
            )

        item = self._queue[qid]

        # Check expired
        if time.time() - item.created_at > self._ttl_seconds:
            item.status = "EXPIRED"
            return HITLDecisionResult(
                queue_id=qid,
                incident_id=incident_id,
                decision=decision,
                executed=False,
                message=f"⚠️ Aksi HITL {qid} sudah expired (>1 jam). Tidak bisa dieksekusi.",
                next_action="RE_ENQUEUE",
            )

        # Process decision
        item.decided_by = operator_id
        item.decided_at = time.time()
        item.decision_note = note

        if decision == HITLDecision.APPROVE or decision == HITLDecision.OVERRIDE:
            item.status = "APPROVED"
            executed = self._execute_action(item)
            result = HITLDecisionResult(
                queue_id=qid,
                incident_id=incident_id,
                decision=decision,
                executed=executed,
                message=(
                    f"✅ APPROVED oleh {operator_id}. "
                    f"Aksi '{item.candidate_action}' pada {item.device} "
                    f"{'berhasil dieksekusi.' if executed else 'dikirim ke ExecutionEngine.'}"
                ),
                next_action="EXECUTE" if executed else "PENDING_EXECUTION",
            )

        elif decision == HITLDecision.REJECT:
            item.status = "REJECTED"
            result = HITLDecisionResult(
                queue_id=qid,
                incident_id=incident_id,
                decision=decision,
                executed=False,
                message=(
                    f"🚫 REJECTED oleh {operator_id}. "
                    f"Aksi '{item.candidate_action}' pada {item.device} DIBATALKAN."
                    + (f" Alasan: {note}" if note else "")
                ),
                next_action="CANCEL",
            )

        elif decision == HITLDecision.ESCALATE:
            item.status = "ESCALATED"
            result = HITLDecisionResult(
                queue_id=qid,
                incident_id=incident_id,
                decision=decision,
                executed=False,
                message=(
                    f"📤 ESCALATED oleh {operator_id} ke L3. "
                    f"Insiden {incident_id} diteruskan ke NOC Manager."
                ),
                next_action="ESCALATE_L3",
            )

        elif decision == HITLDecision.DEFER:
            item.status = "DEFERRED"
            result = HITLDecisionResult(
                queue_id=qid,
                incident_id=incident_id,
                decision=decision,
                executed=False,
                message=f"⏳ DEFERRED oleh {operator_id}. Aksi ditunda ke maintenance window.",
                next_action="SCHEDULE_MAINTENANCE",
            )
        else:
            result = HITLDecisionResult(
                queue_id=qid,
                incident_id=incident_id,
                decision=decision,
                executed=False,
                message=f"Unknown decision: {decision}",
                next_action="NONE",
            )

        logger.info(
            f"[HITLFeedback] Decision: {qid} → {decision.value} "
            f"by {operator_id} | Result: {result.next_action}"
        )
        # Clean up queue after final decisions
        if item.status in ("APPROVED", "REJECTED", "ESCALATED"):
            del self._queue[qid]
            del self._incident_map[inc_key]

        return result

    # ── Notification ──────────────────────────────────────────────────────────

    def format_notification(self, item: HITLQueueItem) -> str:
        """Format notifikasi HITL untuk ditampilkan ke operator via JARVIS/Telegram."""
        wait_icon = {"HIGH": "🔴", "MEDIUM": "🟠", "LOW": "🟡"}.get(item.risk_level, "⚠️")
        return (
            f"{wait_icon} [HITL APPROVAL REQUIRED]\n"
            f"┌─ Queue ID  : {item.queue_id}\n"
            f"├─ Insiden   : {item.incident_id}\n"
            f"├─ Device    : {item.device}\n"
            f"├─ Aksi      : {item.candidate_action}\n"
            f"├─ Risk      : {item.risk_level} (Score: {item.risk_score:.2f})\n"
            f"├─ Blast R.  : {item.blast_radius} node terpengaruh\n"
            f"├─ AI Conf.  : {item.llm_confidence:.0%}\n"
            f"└─ Policy    : {item.policy_effect}\n\n"
            f"Ketik: 'Jarvis, approve {item.incident_id}' atau "
            f"'Jarvis, reject {item.incident_id}'"
        )

    def _send_notification(self, message: str, channels: List[str]) -> None:
        """Kirim notifikasi ke channels yang dikonfigurasi."""
        logger.info(f"[HITLFeedback] NOTIFICATION → channels={channels}")
        if self._notify_callback:
            try:
                self._notify_callback(message, channels)
            except Exception as e:
                logger.warning(f"[HITLFeedback] Notify callback failed: {e}")

    def _execute_action(self, item: HITLQueueItem) -> bool:
        """Panggil execution callback jika tersedia."""
        if self._execution_callback:
            try:
                return bool(self._execution_callback(item))
            except Exception as e:
                logger.error(f"[HITLFeedback] Execution callback error: {e}")
                return False
        logger.info(f"[HITLFeedback] No execution callback — action logged: {item.candidate_action}")
        return True

    # ── Queue Management ──────────────────────────────────────────────────────

    def get_pending_items(self) -> List[HITLQueueItem]:
        """Daftar semua aksi yang menunggu approval."""
        self._cleanup_expired()
        return [item for item in self._queue.values() if item.status == "PENDING"]

    def pending_count(self) -> int:
        self._cleanup_expired()
        return sum(1 for item in self._queue.values() if item.status == "PENDING")

    def _cleanup_expired(self) -> None:
        """Hapus item yang sudah expired dari queue."""
        now = time.time()
        expired = [
            qid for qid, item in self._queue.items()
            if now - item.created_at > self._ttl_seconds
        ]
        for qid in expired:
            item = self._queue.pop(qid, None)
            if item:
                inc_key = item.incident_id.upper()
                self._incident_map.pop(inc_key, None)
                logger.info(f"[HITLFeedback] Expired queue item removed: {qid}")

    def format_queue_summary(self) -> str:
        """Format ringkasan queue untuk JARVIS."""
        pending = self.get_pending_items()
        if not pending:
            return "✅ Tidak ada aksi yang menunggu HITL approval."
        lines = [f"⚠️ {len(pending)} aksi menunggu approval:\n"]
        for item in pending:
            age_min = int((time.time() - item.created_at) / 60)
            lines.append(
                f"  • [{item.risk_level}] {item.incident_id}: "
                f"{item.candidate_action} pada {item.device} "
                f"(menunggu {age_min} menit)"
            )
        return "\n".join(lines)
