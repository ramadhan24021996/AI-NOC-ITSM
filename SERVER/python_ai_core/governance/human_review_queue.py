"""
Phase 3 Governance Framework: Human Review Queue Module with Strict SLAs.

Enforces Human-in-the-Loop (HITL) review for suspicious/low-confidence incidents.
Prevents unvalidated operator feedback from directly modifying prompts or curriculum.
Includes SLA breach enforcement: CRITICAL (15m), HIGH (1h), MEDIUM (4h).
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("HumanReviewQueue")


class SeverityLevel(str, Enum):
    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"


class ReviewTriggerReason(str, Enum):
    LOW_CONFIDENCE = "CONFIDENCE_BELOW_60_PERCENT"
    CONFLICTING_EVIDENCE = "CONFLICTING_TELEMETRY_EVIDENCE"
    UNKNOWN_ROOT_CAUSE = "UNKNOWN_OR_INSUFFICIENT_RCA"
    FALLBACK_TRIGGERED = "SYNTHESIZER_FALLBACK_TRIGGERED"
    OPERATOR_REJECTION = "OPERATOR_REJECTION_FEEDBACK"


# Explicit SLA Durations in Seconds
SLA_SECONDS = {
    SeverityLevel.CRITICAL: 15 * 60,    # 15 Minutes (900 seconds)
    SeverityLevel.HIGH: 60 * 60,        # 1 Hour (3600 seconds)
    SeverityLevel.MEDIUM: 4 * 3600,     # 4 Hours (14400 seconds)
}


@dataclass
class ReviewQueueItem:
    item_id: str
    incident_id: int
    device_name: str
    severity: SeverityLevel
    raw_decision: str
    clean_decision: str
    confidence_score: float
    trigger_reasons: List[ReviewTriggerReason]
    sla_deadline: float
    status: str = "PENDING_HUMAN_REVIEW"  # PENDING_HUMAN_REVIEW, APPROVED_FOR_GOLDEN_DATASET, REJECTED, SLA_BREACHED
    operator_comments: Optional[str] = None
    created_at: float = field(default_factory=time.time)

    def is_sla_breached(self, current_time: Optional[float] = None) -> bool:
        now = current_time or time.time()
        return self.status == "PENDING_HUMAN_REVIEW" and now > self.sla_deadline


class HumanReviewQueue:
    """Governance Review Queue with SLA enforcement."""

    def __init__(self):
        self._queue: Dict[str, ReviewQueueItem] = {}

    def should_route_to_review(
        self,
        confidence_score: float,
        rca_text: str,
        fallback_used: bool,
        operator_flag: Optional[str] = None
    ) -> Tuple[bool, List[ReviewTriggerReason]]:
        reasons = []

        if confidence_score < 0.60:
            reasons.append(ReviewTriggerReason.LOW_CONFIDENCE)

        rca_lower = rca_text.lower() if rca_text else ""
        if "unknown" in rca_lower or "insufficient" in rca_lower:
            reasons.append(ReviewTriggerReason.UNKNOWN_ROOT_CAUSE)

        if fallback_used:
            reasons.append(ReviewTriggerReason.FALLBACK_TRIGGERED)

        if operator_flag and operator_flag in ["HUMAN_REJECTION", "REJECTED", "WRONG"]:
            reasons.append(ReviewTriggerReason.OPERATOR_REJECTION)

        return len(reasons) > 0, reasons

    def enqueue(
        self,
        incident_id: int,
        device_name: str,
        raw_decision: str,
        clean_decision: str,
        confidence_score: float,
        reasons: List[ReviewTriggerReason],
        severity: SeverityLevel = SeverityLevel.MEDIUM
    ) -> ReviewQueueItem:
        now = time.time()
        sla_duration = SLA_SECONDS.get(severity, SLA_SECONDS[SeverityLevel.MEDIUM])
        sla_deadline = now + sla_duration

        item_id = f"REV-{incident_id}-{int(now)}"
        item = ReviewQueueItem(
            item_id=item_id,
            incident_id=incident_id,
            device_name=device_name,
            severity=severity,
            raw_decision=raw_decision,
            clean_decision=clean_decision,
            confidence_score=confidence_score,
            trigger_reasons=reasons,
            sla_deadline=sla_deadline,
            created_at=now
        )
        self._queue[item_id] = item
        logger.info(f"[HumanReviewQueue] Enqueued Incident #{incident_id} [{severity.value} SLA: {sla_duration}s]. ItemID: {item_id}")
        return item

    def check_sla_breaches(self, current_time: Optional[float] = None) -> List[ReviewQueueItem]:
        now = current_time or time.time()
        breached_items = []
        for item in self._queue.values():
            if item.is_sla_breached(now):
                item.status = "SLA_BREACHED"
                breached_items.append(item)
                logger.warning(f"[HumanReviewQueue] SLA BREACHED for Incident #{item.incident_id} (Severity: {item.severity.value})")
        return breached_items

    def approve_for_golden_dataset(self, item_id: str, reviewer_comments: str = "") -> Optional[ReviewQueueItem]:
        item = self._queue.get(item_id)
        if item:
            item.status = "APPROVED_FOR_GOLDEN_DATASET"
            item.operator_comments = reviewer_comments
            logger.info(f"[HumanReviewQueue] Item {item_id} APPROVED by Human Reviewer. Added to Golden Dataset queue.")
            return item
        return None

    def get_pending_items(self) -> List[ReviewQueueItem]:
        return [item for item in self._queue.values() if item.status == "PENDING_HUMAN_REVIEW"]
