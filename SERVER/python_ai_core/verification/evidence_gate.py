"""
evidence_gate.py — Rule #6 Dual-Evidence Binding gate (K-09).

An incident may only be considered remediated when BOTH are present and bound
to the same incident_id + target_asset:
  (a) execution_evidence  : technician ACK, agent exit_code == 0, with timestamp
  (b) post_remediation_evidence : live telemetry captured at T_post >= T_exec

Missing evidence never means success. It yields PENDING_VERIFICATION.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

PENDING_VERIFICATION = "PENDING_VERIFICATION"
VERIFIED = "VERIFIED"
FAILED = "FAILED_VERIFICATION"

_EXEC_SOURCES = {"agent_exit_code", "technician_ack"}


@dataclass
class EvidenceResult:
    status: str
    reasons: List[str] = field(default_factory=list)

    @property
    def verified(self) -> bool:
        return self.status == VERIFIED


def _ts(value: Any) -> Optional[float]:
    if value is None or value == "":
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        s = str(value).replace("Z", "+00:00")
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except ValueError:
        return None


def check_dual_evidence(
    incident_id: Optional[str],
    target_asset: Optional[str],
    execution_evidence: Optional[Dict[str, Any]],
    post_remediation_evidence: Optional[Dict[str, Any]],
) -> EvidenceResult:
    """Return VERIFIED only if both evidences exist, succeed, and are causally bound."""
    if not incident_id or not target_asset:
        return EvidenceResult(PENDING_VERIFICATION, ["incident_id/target_asset missing"])

    ex = execution_evidence or {}
    post = post_remediation_evidence or {}
    missing = []
    if not ex:
        missing.append("execution_evidence missing")
    if not post or not post.get("metrics"):
        missing.append("post_remediation_evidence missing")
    if missing:
        return EvidenceResult(PENDING_VERIFICATION, missing)

    reasons: List[str] = []

    # (a) execution evidence
    if ex.get("source") not in _EXEC_SOURCES:
        reasons.append(f"execution_evidence.source must be one of {sorted(_EXEC_SOURCES)}")
    if ex.get("source") == "agent_exit_code" and ex.get("exit_code") != 0:
        return EvidenceResult(FAILED, [f"agent exit_code={ex.get('exit_code')!r}"])
    if ex.get("source") == "technician_ack" and not ex.get("actor_id"):
        reasons.append("technician_ack requires authenticated actor_id")
    t_exec = _ts(ex.get("executed_at"))
    if t_exec is None:
        reasons.append("execution_evidence.executed_at missing/invalid")

    # (b) post-remediation evidence
    t_post = _ts(post.get("captured_at"))
    if t_post is None:
        reasons.append("post_remediation_evidence.captured_at missing/invalid")
    elif t_exec is not None and t_post < t_exec:
        reasons.append("T_post < T_exec: telemetry predates execution")

    # causal binding
    for name, ev in (("execution_evidence", ex), ("post_remediation_evidence", post)):
        if ev.get("incident_id") != incident_id:
            reasons.append(f"{name}.incident_id mismatch")
        if ev.get("target_asset") != target_asset:
            reasons.append(f"{name}.target_asset mismatch")

    if reasons:
        return EvidenceResult(PENDING_VERIFICATION, reasons)

    if post.get("healthy") is not True:
        return EvidenceResult(FAILED, ["post-remediation telemetry not healthy"])
    return EvidenceResult(VERIFIED, [])
