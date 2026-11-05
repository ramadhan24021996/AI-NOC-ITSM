"""
SERVER.orchestrator.closed_loop.review_audit_trail
==================================================
Component: Review Audit Trail Tracker

Tracks and persists chronological audit logs per review iteration:
Review #1 (Historical FAIL) -> Review #2 (Sandbox FAIL) -> Review #3 (APPROVED)
"""
import logging
from typing import List, Dict, Any
from SERVER.contracts.schemas import IterativeReviewIteration, ReviewAuditTrailRecord

logger = logging.getLogger("orchestrator.closed_loop.audit_trail")


class ReviewAuditTrailTracker:
    """
    Tracks and records multi-round review history per incident session.
    """

    def record_trail(
        self, session_id: str, iterations: List[IterativeReviewIteration]
    ) -> ReviewAuditTrailRecord:
        final_verdict = "APPROVED" if (iterations and iterations[-1].status == "PASS") else "REJECTED"

        record = ReviewAuditTrailRecord(
            session_id=session_id,
            total_rounds=len(iterations),
            iterations=iterations,
            final_verdict=final_verdict,
        )

        logger.debug(f"[ReviewAuditTrailTracker] Audit trail recorded for {session_id} across {len(iterations)} rounds (Verdict: {final_verdict})")
        return record
