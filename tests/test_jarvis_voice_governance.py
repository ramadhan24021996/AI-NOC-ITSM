"""
Unit & Integration Tests for JARVIS Voice Strategic Remediation (WS-J1 .. WS-J7)
================================================================================
Verifies:
  - WS-J1: ThreadedJarvisHTTPServer multi-threaded concurrency
  - WS-J2: Raw PCM16 -> 44-byte RIFF/WAV framing & runtime provider properties
  - WS-J3: Concise `spoken_text` vs full `answer_text` splitter for <800ms TTS
  - WS-J4: RBAC Role Gate blocking viewer/read_only roles from voice remediation
  - WS-J5: Axiom Rule #6 (`PENDING_VERIFICATION` & zero premature RAG auto-learn)
           and K-07 (`PENDING_DASHBOARD_CONFIRMATION` on voice HITL approve/reject/override)
  - WS-J6: 10 Control Gates V4.0 (Kill-Switch & GATE-07 Autonomy Budget loop block)
  - WS-J7: EdgeTTSProvider fast circuit breaker -> instant KokoroTTS fallback
"""
import struct
import time
from http.server import ThreadingHTTPServer
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from SERVER.contracts.schemas import StructuredActionContext
from SERVER.jarvis.api.jarvis_voice_server import ThreadedJarvisHTTPServer
from SERVER.jarvis.runtime.intent_action_handler import IntentActionHandlerMixin
from SERVER.jarvis.runtime.jarvis_presentation_runtime import JarvisPresentationRuntime
from SERVER.jarvis.voice.stt_provider import _wrap_pcm16_in_wav
from SERVER.jarvis.voice.tts_provider import EdgeTTSProvider
from SERVER.jarvis.workflow.workflow_governance_control_plane import (
    get_workflow_governance_control_plane_v38,
)


class DummyActionRuntime(IntentActionHandlerMixin):
    """Minimal harness for testing IntentActionHandlerMixin deterministically."""

    def __init__(self):
        self.one_click_remediator = None
        self.sandbox_verifier = None
        self.catalog_validator = MagicMock()
        self.catalog_validator.validate.return_value = {
            "verdict": "APPROVED",
            "risk_level": "LOW",
            "action_id": "ACT_CLEAR_DNS",
            "action_name": "Flush DNS Cache",
        }
        self.hitl_feedback = MagicMock()
        self.persona_reg = MagicMock()
        self.gateway = MagicMock()
        self.gateway.handle_request.return_value = {
            "answer_text": "Perintah flush DNS dikirim ke agen.",
            "policy_effect": "ALLOW_LOW_RISK",
            "requires_hitl": False,
            "risk_level": "LOW",
        }
        self.kb_learning_bridge = MagicMock()


def test_ws_j1_threaded_http_server():
    """WS-J1: Server must inherit ThreadingHTTPServer with daemon_threads=True."""
    assert issubclass(ThreadedJarvisHTTPServer, ThreadingHTTPServer)
    assert ThreadedJarvisHTTPServer.daemon_threads is True


def test_ws_j2_pcm16_wav_framing():
    """WS-J2: Raw 16kHz PCM16 bytes must be wrapped in a valid 44-byte RIFF/WAV header."""
    raw_pcm = b"\x00\x01" * 8000  # 16,000 bytes (0.5s at 16kHz 16-bit mono)
    wav_bytes = _wrap_pcm16_in_wav(raw_pcm, sample_rate=16000)

    assert len(wav_bytes) == 44 + len(raw_pcm)
    assert wav_bytes[:4] == b"RIFF"
    assert wav_bytes[8:12] == b"WAVE"
    assert wav_bytes[12:16] == b"fmt "
    assert wav_bytes[36:40] == b"data"
    sample_rate = struct.unpack("<I", wav_bytes[24:28])[0]
    data_size = struct.unpack("<I", wav_bytes[40:44])[0]
    assert sample_rate == 16000
    assert data_size == len(raw_pcm)
    # Idempotency check: already wrapped WAV is not double-wrapped
    assert _wrap_pcm16_in_wav(wav_bytes, sample_rate=16000) == wav_bytes


def test_ws_j3_concise_spoken_summary_splitter():
    """WS-J3: Full UI answer_text is preserved while spoken_text is concise (1-2 sentences, no CoT/Emoji)."""
    long_narrative = (
        "✅ **Status Kasir-1**: CPU tercatat 94% akibat proses `spoolsv.exe` yang hang. "
        "Layanan print spooler telah dijadwalkan untuk di-restart melalui agen.\n"
        "- Detail PID: 4412\n"
        "- Memory usage: 1.8 GB\n"
        "- Uptime: 14 hari\n\n"
        "💡 Insight Proaktif: Disarankan melakukan pembersihan folder spooler.\n\n"
        "🧠 Riwayat Episodik: Perangkat ini mengalami insiden serupa 3 hari lalu."
    )
    spoken = JarvisPresentationRuntime._build_concise_spoken_summary(long_narrative)
    assert len(spoken) <= 240
    assert "Riwayat Episodik" not in spoken
    assert "Insight Proaktif" not in spoken
    assert "**" not in spoken
    assert "`" not in spoken
    assert "Status Kasir-1" in spoken


def test_ws_j4_rbac_blocks_readonly_operator():
    """WS-J4: Viewer / read-only roles must be blocked from voice remediation."""
    rt = DummyActionRuntime()
    intent_res = SimpleNamespace(target_device="PC-KASIR-01", target_incident="INC-101")
    session = SimpleNamespace(user_id="guest_user", user_role="viewer", active_persona_id="noc_engineer")
    ctx = StructuredActionContext(detected_intent="REMEDIATE", intent_confidence=0.95)

    answer, out_ctx = rt._handle_remediate("flush dns PC-KASIR-01", intent_res, "sess-1", session, ctx)
    assert out_ctx.execution_status == "FORBIDDEN_RBAC"
    assert "Akses ditolak (RBAC)" in answer
    rt.gateway.handle_request.assert_not_called()


def test_ws_j5_rule6_remediate_sets_pending_verification_and_no_auto_learn():
    """WS-J5 (Axiom Rule #6): Remediation dispatch must set PENDING_VERIFICATION and never auto-learn prematurely."""
    wf_cp = get_workflow_governance_control_plane_v38()
    wf_cp.kill_switch.deactivate_kill_switch()
    wf_cp.autonomy_budget._attempts.clear()

    rt = DummyActionRuntime()
    intent_res = SimpleNamespace(target_device="PC-KASIR-09", target_incident="INC-909")
    session = SimpleNamespace(user_id="noc_op1", user_role="noc_operator", active_persona_id="noc_engineer")
    ctx = StructuredActionContext(detected_intent="REMEDIATE", intent_confidence=0.98)

    answer, out_ctx = rt._handle_remediate("flush dns PC-KASIR-09", intent_res, "sess-r6", session, ctx)
    assert out_ctx.execution_status == "PENDING_VERIFICATION"
    assert "PENDING_VERIFICATION" in answer
    # Must NEVER call auto_learn_from_resolution before dual-evidence verification
    rt.kb_learning_bridge.auto_learn_from_resolution.assert_not_called()


def test_ws_j5_k07_blocks_voice_hitl_approval():
    """WS-J5 (Finding K-07): Voice HITL approve/reject/override must require Dashboard UI confirmation."""
    rt = DummyActionRuntime()
    intent_res = SimpleNamespace(target_device="ROUTER-CORE-01", target_incident="INC-777")
    session = SimpleNamespace(user_id="noc_op1", user_role="noc_operator")
    ctx = StructuredActionContext(detected_intent="HITL", intent_confidence=0.99)

    for cmd in ("Jarvis, approve INC-777", "Jarvis, reject INC-777", "Jarvis, override INC-777"):
        answer, out_ctx = rt._handle_hitl(cmd, intent_res, session, ctx)
        assert out_ctx.execution_status == "PENDING_DASHBOARD_CONFIRMATION"
        assert out_ctx.action_taken == "REQUEST_DASHBOARD_CONFIRMATION"
        assert "K-07" in answer
        rt.hitl_feedback.process_decision.assert_not_called()


def test_ws_j6_control_gates_kill_switch_and_autonomy_budget():
    """WS-J6: 10 Control Gates V4.0 Kill-Switch and GATE-07 Autonomy Budget (RULE-AUTO-007) must enforce limits."""
    wf_cp = get_workflow_governance_control_plane_v38()
    wf_cp.autonomy_budget._attempts.clear()

    rt = DummyActionRuntime()
    intent_res = SimpleNamespace(target_device="PC-LOOP-01", target_incident="INC-500")
    session = SimpleNamespace(user_id="noc_op1", user_role="noc_operator", active_persona_id="noc_engineer")

    # 1. Test Global Kill-Switch
    wf_cp.kill_switch.activate_kill_switch("UNIT_TEST_EMERGENCY")
    try:
        ctx_ks = StructuredActionContext(detected_intent="REMEDIATE", intent_confidence=0.95)
        ans_ks, ctx_ks = rt._handle_remediate("flush dns PC-LOOP-01", intent_res, "sess-ks", session, ctx_ks)
        assert ctx_ks.execution_status == "BLOCKED_BY_KILL_SWITCH"
        assert "Kill-Switch" in ans_ks
    finally:
        wf_cp.kill_switch.deactivate_kill_switch()

    # 2. Test GATE-07 Autonomy Budget (max 2 attempts/hour per device+action; 3rd attempt blocked)
    for attempt in range(1, 3):
        ctx_try = StructuredActionContext(detected_intent="REMEDIATE", intent_confidence=0.95)
        _, ctx_try = rt._handle_remediate("flush dns PC-LOOP-01", intent_res, f"sess-{attempt}", session, ctx_try)
        assert ctx_try.execution_status == "PENDING_VERIFICATION"

    ctx_third = StructuredActionContext(detected_intent="REMEDIATE", intent_confidence=0.95)
    ans_third, ctx_third = rt._handle_remediate("flush dns PC-LOOP-01", intent_res, "sess-3", session, ctx_third)
    assert ctx_third.execution_status == "AUTONOMY_BUDGET_EXCEEDED"
    assert ctx_third.policy_effect == "RULE_AUTO_007_LOOP_BLOCKED"
    assert "menghentikan loop remediation otonom" in ans_third


def test_ws_j7_edgetts_circuit_breaker_fast_fallback():
    """WS-J7: EdgeTTS failure opens 60s circuit breaker so subsequent calls fallback immediately to KokoroTTS."""
    provider = EdgeTTSProvider()
    provider._edge_tts_available = True

    call_count = {"edge": 0}

    def _failing_edge(*args, **kwargs):
        call_count["edge"] += 1
        raise TimeoutError("Simulated WAN timeout")

    provider._run_edge_tts_sync = _failing_edge

    # First call fails in EdgeTTS, opens circuit breaker, and falls back to Kokoro WAV
    dto1 = provider.synthesize_text("Tes suara pertama.")
    assert dto1.audio_format == "wav"
    assert len(dto1.audio_bytes) > 44
    assert call_count["edge"] == 1
    assert provider._circuit_open_until > time.time()

    # Second call sees open circuit breaker and skips _run_edge_tts_sync completely
    dto2 = provider.synthesize_text("Tes suara kedua.")
    assert dto2.audio_format == "wav"
    assert call_count["edge"] == 1
