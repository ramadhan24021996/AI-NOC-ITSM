"""
test_K09_dual_evidence.py: Rule #6 / K-09 regression.

The verifier must not mark remediation successful without execution_evidence
AND post_remediation_evidence bound to the same incident_id + target_asset,
with T_post >= T_exec.
"""
import os
import sys

ROOT = os.path.join(os.path.dirname(__file__), "..")
sys.path.insert(0, os.path.join(ROOT, "SERVER", "python_ai_core"))

import pytest

from verification.evidence_gate import (
    FAILED, PENDING_VERIFICATION, VERIFIED, check_dual_evidence,
)

INC, ASSET = "INC-42", "PRN-01"


def _exec(**kw):
    ev = {"source": "agent_exit_code", "exit_code": 0, "executed_at": "2026-11-02T10:00:00Z",
          "incident_id": INC, "target_asset": ASSET}
    ev.update(kw)
    return ev


def _post(**kw):
    ev = {"captured_at": "2026-11-02T10:01:00Z", "metrics": {"spooler": "RUNNING", "queue": 0},
          "healthy": True, "incident_id": INC, "target_asset": ASSET}
    ev.update(kw)
    return ev


def test_valid_dual_evidence_verifies():
    assert check_dual_evidence(INC, ASSET, _exec(), _post()).status == VERIFIED


@pytest.mark.parametrize("ex,post", [(None, None), (_exec(), None), (None, _post()),
                                     (_exec(), {"captured_at": "2026-11-02T10:01:00Z"})])
def test_missing_evidence_is_pending_not_success(ex, post):
    assert check_dual_evidence(INC, ASSET, ex, post).status == PENDING_VERIFICATION


def test_post_before_exec_rejected():
    r = check_dual_evidence(INC, ASSET, _exec(), _post(captured_at="2026-11-02T09:59:00Z"))
    assert r.status == PENDING_VERIFICATION and any("T_post" in x for x in r.reasons)


@pytest.mark.parametrize("field,value", [("incident_id", "INC-OTHER"), ("target_asset", "PRN-99")])
def test_causal_binding_mismatch_rejected(field, value):
    assert check_dual_evidence(INC, ASSET, _exec(), _post(**{field: value})).status != VERIFIED
    assert check_dual_evidence(INC, ASSET, _exec(**{field: value}), _post()).status != VERIFIED


def test_nonzero_exit_fails():
    assert check_dual_evidence(INC, ASSET, _exec(exit_code=1), _post()).status == FAILED


def test_unhealthy_telemetry_fails():
    assert check_dual_evidence(INC, ASSET, _exec(), _post(healthy=False)).status == FAILED


def test_ack_without_actor_is_pending():
    ex = _exec(source="technician_ack")
    ex.pop("exit_code")
    assert check_dual_evidence(INC, ASSET, ex, _post()).status == PENDING_VERIFICATION


def test_ai_verifier_rejects_status_string_only():
    """K-09 core: legacy status string alone must NOT prove success."""
    from verification.ai_verifier import AIVerificationEngine
    res = AIVerificationEngine().verify_post_execution(
        INC, {"status": "EXECUTION_SUCCESSFUL", "execution_id": "x"}, {})
    assert res["remediation_proven_successful"] is False
    assert res["next_action"] == "HOLD_PENDING_VERIFICATION"


def test_ai_verifier_accepts_bound_evidence():
    from verification.ai_verifier import AIVerificationEngine
    res = AIVerificationEngine().verify_post_execution(
        INC, {"execution_id": "x", "target_asset": ASSET, "execution_evidence": _exec()}, _post())
    assert res["remediation_proven_successful"] is True
