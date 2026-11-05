"""
human_review_queue.py
======================
Action-Level Human-In-The-Loop (HITL) Governance Review Queue.
Mendukung persetujuan tindakan operasional terperinci dengan opsi:
APPROVE | REJECT | MODIFY | ESCALATE.
"""

import json
import logging
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("HumanReviewQueue")


class ReviewDecisionOption(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    MODIFY = "MODIFY"
    ESCALATE = "ESCALATE"


class ReviewTriggerReason(str, Enum):
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    HIGH_RISK_ACTION = "HIGH_RISK_ACTION"
    UNKNOWN_ROOT_CAUSE = "UNKNOWN_ROOT_CAUSE"
    FALLBACK_TRIGGERED = "FALLBACK_TRIGGERED"
    CRITICAL_SEVERITY = "CRITICAL_SEVERITY"


class SeverityLevel(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"



@dataclass
class ActionLevelHITLItem:
    item_id: str
    incident_id: str
    device_id: str
    evidence_summary: List[Dict[str, Any]]
    root_cause_probability: float
    proposed_action: Dict[str, Any]
    expected_impact: str
    risk_score: float
    blast_radius: float
    rollback_plan: str
    verification_plan: List[str]
    status: str = "PENDING_APPROVAL"       # PENDING_APPROVAL | APPROVED | REJECTED | MODIFIED | ESCALATED
    modified_action: Optional[Dict[str, Any]] = None
    operator_comments: Optional[str] = None
    created_at: float = field(default_factory=time.time)


@dataclass
class HumanReviewItem:
    item_id: str
    incident_id: Any
    device_name: str
    raw_decision: str
    clean_decision: str
    confidence_score: float
    reasons: List[ReviewTriggerReason]
    severity: SeverityLevel = SeverityLevel.MEDIUM
    status: str = "PENDING_HUMAN_REVIEW"
    created_at: float = field(default_factory=time.time)
    sla_deadline: float = 0.0


class HumanReviewQueue:
    """Action-Level HITL Governance Engine."""

    def __init__(self):
        self._queue: Dict[str, Any] = {}

    def should_route_to_review(
        self,
        confidence_score: float,
        rca_text: str = "",
        fallback_used: bool = False,
        operator_flag: str = ""
    ) -> Tuple[bool, List[ReviewTriggerReason]]:
        """Evaluates whether an incident must be routed to Human Review Queue."""
        reasons = []
        if confidence_score < 0.60:
            reasons.append(ReviewTriggerReason.LOW_CONFIDENCE)
        if rca_text and ("unknown" in rca_text.lower() or "unclear" in rca_text.lower()):
            reasons.append(ReviewTriggerReason.UNKNOWN_ROOT_CAUSE)
        if fallback_used:
            reasons.append(ReviewTriggerReason.FALLBACK_TRIGGERED)
        if operator_flag and "REJECT" in operator_flag.upper():
            reasons.append(ReviewTriggerReason.HIGH_RISK_ACTION)

        return (len(reasons) > 0, reasons)

    def enqueue(
        self,
        incident_id: Any,
        device_name: str,
        raw_decision: str,
        clean_decision: str,
        confidence_score: float,
        reasons: List[ReviewTriggerReason],
        severity: SeverityLevel = SeverityLevel.MEDIUM
    ) -> HumanReviewItem:
        """Enqueues an item for human review with SLA tracking."""
        item_id = f"review-{incident_id}-{int(time.time())}"
        now = time.time()
        
        sla_seconds = 3600.0
        if severity == SeverityLevel.CRITICAL:
            sla_seconds = 900.0
        elif severity == SeverityLevel.HIGH:
            sla_seconds = 1800.0

        item = HumanReviewItem(
            item_id=item_id,
            incident_id=incident_id,
            device_name=device_name,
            raw_decision=raw_decision,
            clean_decision=clean_decision,
            confidence_score=confidence_score,
            reasons=reasons,
            severity=severity,
            status="PENDING_HUMAN_REVIEW",
            created_at=now,
            sla_deadline=now + sla_seconds
        )
        self._queue[item_id] = item
        return item

    def check_sla_breaches(self, current_time: Optional[float] = None) -> List[HumanReviewItem]:
        """Checks pending items that have breached SLA deadline."""
        now = current_time or time.time()
        breached = []
        for item in self._queue.values():
            if isinstance(item, HumanReviewItem) and item.status in ["PENDING_REVIEW", "PENDING_HUMAN_REVIEW"]:
                if now > item.sla_deadline:
                    item.status = "SLA_BREACHED"
                    breached.append(item)
        return breached

    def approve_for_golden_dataset(self, item_id: str, reviewer_notes: str = "") -> Optional[HumanReviewItem]:
        """Approves a review item for inclusion in the golden dataset."""
        item = self._queue.get(item_id)
        if item:
            item.status = "APPROVED_FOR_GOLDEN_DATASET"
            return item
        return None



    def enqueue_action_for_review(
        self,
        incident_context: Any,
        proposed_action: Dict[str, Any]
    ) -> ActionLevelHITLItem:
        """Enqueues an action for HITL operator review."""
        item_id = f"hitl-{incident_context.incident_id}-{int(time.time())}"
        
        raw_risk = proposed_action.get("risk_score") if proposed_action else None
        risk_val = float(raw_risk) if raw_risk is not None else float(getattr(incident_context, "risk_score", 0.1))

        rollback_val = proposed_action.get("rollback") if proposed_action else None
        if not rollback_val:
            rollback_val = "Standard service restart rollback"

        action_name = proposed_action.get("name", "N/A") if proposed_action else "N/A"

        hitl_item = ActionLevelHITLItem(
            item_id=item_id,
            incident_id=incident_context.incident_id,
            device_id=incident_context.device_id,
            evidence_summary=incident_context.evidence,
            root_cause_probability=float(getattr(incident_context, "confidence", 0.85)),
            proposed_action=proposed_action or {},
            expected_impact=getattr(incident_context, "business_impact", "MEDIUM"),
            risk_score=risk_val,
            blast_radius=float(getattr(incident_context, "blast_radius", 0.1)),
            rollback_plan=str(rollback_val),
            verification_plan=["spooler_running", "queue_cleared"]
        )

        self._queue[item_id] = hitl_item
        incident_context.hitl_status = "PENDING"
        logger.info(f"[HITLQueue] Enqueued Action '{action_name}' for incident '{incident_context.incident_id}' (ItemID: {item_id})")
        return hitl_item

    def submit_operator_decision(
        self,
        item_id: str,
        decision: ReviewDecisionOption,
        comments: str = "",
        modified_action: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Processes operator decision: APPROVE, REJECT, MODIFY, or ESCALATE."""
        item = self._queue.get(item_id)
        if not item:
            return {"status": "ERROR", "message": f"HITL Item {item_id} not found."}

        if hasattr(item, "operator_comments"):
            item.operator_comments = comments

        if decision == ReviewDecisionOption.APPROVE:
            item.status = "APPROVED"
        elif decision == ReviewDecisionOption.REJECT:
            item.status = "REJECTED"
        elif decision == ReviewDecisionOption.MODIFY:
            item.status = "MODIFIED"
            if hasattr(item, "modified_action"):
                item.modified_action = modified_action
        elif decision == ReviewDecisionOption.ESCALATE:
            item.status = "ESCALATED"

        logger.info(f"[HITLQueue] Operator decision for {item_id}: {item.status} ({comments})")
        return {
            "status": "SUCCESS",
            "item_id": item_id,
            "decision": item.status,
            "modified_action": getattr(item, "modified_action", None)
        }

