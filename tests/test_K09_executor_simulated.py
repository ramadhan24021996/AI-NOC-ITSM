"""
test_K09_executor_simulated.py
Rule #6 / K-09 regression test.

Ensures:
  (a) execute_plan NEVER returns status EXECUTION_SUCCESSFUL.
  (b) execute_plan returns status SIMULATED with null evidence fields.
  (c) AWAITING_HITL_APPROVAL is returned when hitl not approved.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest


@pytest.fixture
def engine():
    from SERVER.python_ai_core.execution.ai_executor import AIExecutionEngine
    return AIExecutionEngine()


def test_K09_no_execution_successful_status(engine):
    """K-09: execute_plan must NEVER return EXECUTION_SUCCESSFUL."""
    result = engine.execute_plan(
        incident_id="INC-001",
        plan_id="plan-001",
        action="RESTART_SERVICE",
    )
    assert result["status"] != "EXECUTION_SUCCESSFUL", (
        "K-09 VIOLATION: execute_plan returned EXECUTION_SUCCESSFUL without real ACK. "
        "Rule #6: success status requires execution_evidence AND post_remediation_evidence."
    )


def test_K09_returns_simulated(engine):
    """K-09: execute_plan must return SIMULATED when real dispatch is not wired."""
    result = engine.execute_plan(
        incident_id="INC-002",
        plan_id="plan-002",
        action="CLEAR_SPOOLER",
    )
    assert result["status"] == "SIMULATED", (
        f"Expected SIMULATED, got {result['status']!r}"
    )


def test_K09_evidence_fields_null(engine):
    """Rule #6: evidence fields must be null when in SIMULATED mode."""
    result = engine.execute_plan(
        incident_id="INC-003",
        plan_id="plan-003",
        action="RELEASE_DHCP_LEASE",
    )
    assert result.get("execution_evidence") is None, "execution_evidence must be null in SIMULATED mode"
    assert result.get("post_remediation_evidence") is None, "post_remediation_evidence must be null in SIMULATED mode"


def test_K09_hitl_not_approved_blocks_execution(engine):
    """K-09: HITL required + not approved must NOT execute."""
    result = engine.execute_plan(
        incident_id="INC-004",
        plan_id="plan-004",
        action="RESTART_SERVICE",
        requires_hitl=True,
        hitl_approved=False,
    )
    assert result["status"] == "AWAITING_HITL_APPROVAL"
    assert result.get("execution_evidence") is None


def test_K09_incident_id_present_in_result(engine):
    """K-09: incident_id must be bound to the result for causal correlation (Rule #6.3)."""
    result = engine.execute_plan(
        incident_id="INC-999",
        plan_id="plan-005",
        action="FLUSH_DNS",
    )
    assert result.get("incident_id") == "INC-999", (
        "incident_id must be echoed in result so verifier can bind evidence to the same incident"
    )
