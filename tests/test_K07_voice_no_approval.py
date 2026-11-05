"""
test_K07_voice_no_approval.py
K-07 regression test.

Ensures voice channel cannot finalize HITL approval.
Expected status: PENDING_DASHBOARD_CONFIRMATION (not SUCCESS/APPROVED).
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

import pytest

VOICE_APPROVE_QUERIES = [
    "approve insiden 123",
    "setujui insiden 45",
]
VOICE_REJECT_QUERIES = [
    "tolak insiden 77",
    "reject insiden 8",
]

class _DummyContext:
    """Minimal stand-in for ActionContext so we can call the handler."""
    def __init__(self):
        self.action_taken = None
        self.execution_status = None
        self.hitl_queue_id = None


def _make_handler():
    from types import SimpleNamespace
    from SERVER.jarvis.runtime.intent_query_handler import IntentQueryHandlerMixin

    class _H(IntentQueryHandlerMixin):
        noc_bridge = None
        one_click_remediator = None

        def handle(self, query, session_id, action_context):
            intent = SimpleNamespace(target_device=None, target_site=None)
            return self._handle_query(query, intent, None, action_context, session_id)

    return _H()


@pytest.mark.parametrize("query", VOICE_APPROVE_QUERIES + VOICE_REJECT_QUERIES)
def test_K07_voice_cannot_finalize_approval(query):
    """K-07: voice query must set execution_status=PENDING_DASHBOARD_CONFIRMATION."""
    handler = _make_handler()
    ctx = _DummyContext()
    # Call the HITL block indirectly via the public handle method if available,
    # otherwise call the inner logic by constructing a minimal invocation.
    # The handler sets action_context attributes; we check those.
    try:
        _msg, action_ctx = handler.handle(query=query, session_id="voice-test", action_context=ctx)
    except Exception as exc:
        pytest.fail(f"handler raised: {exc!r}")

    # Core assertion: voice must NOT produce a finalised approval.
    assert action_ctx.execution_status != "SUCCESS", (
        f"K-07 VIOLATION: voice query {query!r} returned execution_status='SUCCESS'. "
        "Voice cannot finalise HITL approval (P2, WS-5)."
    )
    assert action_ctx.execution_status == "PENDING_DASHBOARD_CONFIRMATION", (
        f"K-07: expected PENDING_DASHBOARD_CONFIRMATION, got {action_ctx.execution_status!r}"
    )


@pytest.mark.parametrize("query", VOICE_APPROVE_QUERIES)
def test_K07_voice_approve_action_not_hitl_approve(query):
    """K-07: voice approve must set action_taken=HITL_QUEUE_REQUEST, not HITL_APPROVE."""
    handler = _make_handler()
    ctx = _DummyContext()
    try:
        _msg, action_ctx = handler.handle(query=query, session_id="voice-test", action_context=ctx)
    except Exception as exc:
        pytest.fail(f"handler raised: {exc!r}")

    assert action_ctx.action_taken == "HITL_QUEUE_REQUEST", (
        f"K-07: expected HITL_QUEUE_REQUEST, got {action_ctx.action_taken!r}. "
        "Voice must only queue, not approve."
    )
