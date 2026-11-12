"""
Unit Tests for OSI 7-Layer Knowledge Matrix & JARVIS Layer Integration:
  - OSI Layer Knowledge definitions (L1 to L7)
  - Cross-Layer Causal Propagation (Anti-Symptom Illusion)
  - Axiom Rule #6 Dual-Evidence Verification per layer
  - JARVIS Voice Intent Routing & Layer Breakdown Queries
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from SERVER.jarvis.command.intent_router import JarvisCommandIntentRouter, JarvisIntent
from SERVER.jarvis.runtime.intent_query_handler import IntentQueryHandlerMixin
from SERVER.jarvis.runtime.shift_handoff_briefer import ShiftHandoffBriefer
from SERVER.python_ai_core.knowledge.osi_layer_matrix import (
    evaluate_cross_layer_causality,
    explain_all_layers,
    explain_layer,
    get_layer_knowledge,
    verify_layer_rule6_evidence,
)


class _QueryHandler(IntentQueryHandlerMixin):
    def __init__(self, noc_bridge=None, briefer=None, gateway=None):
        self.noc_bridge = noc_bridge or MagicMock()
        self._shift_briefer = briefer
        self.gateway = gateway
        self.browser_control = MagicMock()
        self.browser_control.is_waiting_for_song.return_value = False
        self.router = JarvisCommandIntentRouter()

    def ask(self, text: str, session_id: str = "s-test"):
        intent_res = self.router.classify(text)
        ctx = SimpleNamespace(action_taken=None, execution_status=None, session_id=session_id)
        return self._handle_query(text, intent_res, None, ctx, session_id=session_id)


def _make_mock_conn(cursor_handler):
    conn = MagicMock()
    cur = MagicMock()

    def _execute(sql, params=None):
        cur._last_result = cursor_handler(sql, params)

    def _fetchone():
        res = getattr(cur, "_last_result", None)
        if isinstance(res, list):
            return res[0] if res else None
        return res

    def _fetchall():
        res = getattr(cur, "_last_result", None)
        if isinstance(res, list):
            return res
        return [res] if res is not None else []

    cur.execute.side_effect = _execute
    cur.fetchone.side_effect = _fetchone
    cur.fetchall.side_effect = _fetchall
    conn.cursor.return_value.__enter__.return_value = cur
    return conn


class TestOSILayerMatrixCore:
    """Tests for core functions in osi_layer_matrix.py."""

    def test_get_layer_knowledge_all_seven_layers(self):
        for l in range(1, 8):
            k = get_layer_knowledge(l)
            assert k is not None
            assert k["layer"] == l
            assert "name" in k and "components" in k and "symptoms" in k
            assert "sops" in k and "rule6_verification" in k

    def test_explain_layer_and_explain_all(self):
        exp3 = explain_layer(3)
        assert "Layer 3" in exp3 and "Network" in exp3
        assert "Routing" in exp3

        all_exp = explain_all_layers()
        for l in range(1, 8):
            assert f"Layer {l}" in all_exp
        assert "Prinsip Kausalitas" in all_exp

    def test_evaluate_cross_layer_causality_bottom_up(self):
        # L1, L4, L7 active simultaneously -> L1 is root cause, L4 & L7 are secondary symptoms
        res = evaluate_cross_layer_causality([7, 1, 4])
        assert res["root_cause_layer"] == 1
        assert res["secondary_symptom_layers"] == [4, 7]
        assert "Dilarang me-restart service Layer 7" in res["recommendation"]

    def test_verify_layer_rule6_evidence_layer1_success(self):
        t_exec = datetime(2026, 11, 6, 15, 0, 0, tzinfo=timezone.utc)
        t_post = t_exec + timedelta(seconds=12)

        exec_ev = {"status": "SUCCESS", "executed_at": t_exec, "exit_code": 0}
        post_tel = {"timestamp": t_post, "carrier": 1, "speed": 1000}

        ok, msg, audit = verify_layer_rule6_evidence(1, exec_ev, post_tel)
        assert ok is True
        assert "SAH dan terverifikasi penuh" in msg
        assert audit["temporal_valid"] is True
        assert audit["metric_satisfied"] is True

    def test_verify_layer_rule6_evidence_fails_when_temporal_inverted(self):
        t_exec = datetime(2026, 11, 6, 15, 0, 0, tzinfo=timezone.utc)
        t_post = t_exec - timedelta(seconds=5)  # Inverted

        exec_ev = {"status": "SUCCESS", "executed_at": t_exec, "exit_code": 0}
        post_tel = {"timestamp": t_post, "carrier": 1}

        ok, msg, audit = verify_layer_rule6_evidence(1, exec_ev, post_tel)
        assert ok is False
        assert "Pelanggaran Temporal Rule #6" in msg


class TestJarvisOSILayerIntegration:
    """Tests for JARVIS Intent Router & Query Handler with OSI Layer features."""

    def test_router_extracts_target_layer(self):
        router = JarvisCommandIntentRouter()
        res = router.classify("Jarvis, jelaskan fungsi layer 3")
        assert res.intent == JarvisIntent.QUERY
        assert res.target_layer == 3

    def test_jarvis_explain_osi_layer_specific(self):
        qh = _QueryHandler()
        reply, ctx = qh.ask("Jarvis, jelaskan fungsi layer 2", session_id="s-l2")
        assert ctx.action_taken == "EXPLAIN_OSI_LAYER"
        assert ctx.execution_status == "SUCCESS"
        assert "Layer 2" in reply and "Data Link" in reply
        assert "MAC" in reply or "Switch" in reply

    def test_jarvis_explain_all_osi_layers(self):
        qh = _QueryHandler()
        reply, ctx = qh.ask("Jarvis, jelaskan layer 1 sampai 7", session_id="s-all-layers")
        assert ctx.action_taken == "EXPLAIN_OSI_LAYER"
        assert ctx.execution_status == "SUCCESS"
        assert "RINGKASAN MODEL OSI 7-LAYER" in reply
        assert "Layer 1 (Physical)" in reply
        assert "Layer 7 (Application)" in reply

    def test_jarvis_layer_health_breakdown_with_causality(self):
        def _handler(sql, params):
            q = " ".join(sql.split()).lower()
            if "select incident_id" in q and "from incidents" in q:
                return [
                    (101, "SW-CORE-01", 1, "OPEN", "Kabel fiber bengkok rx_crc_errors"),
                    (102, "SRV-APP-01", 4, "OPEN", "TCP SYN timeout"),
                    (103, "PC-KASIR-01", 7, "OPEN", "HTTP 502 Bad Gateway"),
                ]
            return None

        briefer = ShiftHandoffBriefer(db_conn=_make_mock_conn(_handler))
        qh = _QueryHandler(briefer=briefer)

        reply, ctx = qh.ask("Jarvis, rincikan sebaran insiden per layer", session_id="s-brk")
        assert ctx.action_taken == "LAYER_HEALTH_BREAKDOWN"
        assert ctx.execution_status == "SUCCESS"
        assert "REKAPITULASI SEBARAN INSIDEN PER LAYER OSI" in reply
        assert "Layer 1" in reply and "Layer 7" in reply
        assert "Alur Propagasi Kausalitas" in reply
        assert "Dilarang me-restart service Layer 7" in reply

    def test_jarvis_layer_specific_breakdown_single_layer(self):
        def _handler(sql, params):
            q = " ".join(sql.split()).lower()
            if "select incident_id" in q and "from incidents" in q:
                return [
                    (201, "PRT-HR-01", 7, "OPEN", "Print Spooler Frozen"),
                ]
            return None

        briefer = ShiftHandoffBriefer(db_conn=_make_mock_conn(_handler))
        qh = _QueryHandler(briefer=briefer)

        reply, ctx = qh.ask("Jarvis, periksa insiden di layer 7", session_id="s-l7-only")
        assert ctx.action_taken == "LAYER_HEALTH_BREAKDOWN"
        assert ctx.execution_status == "SUCCESS"
        assert "STATUS LAYER 7" in reply
        assert "INC-#201" in reply and "PRT-HR-01" in reply
        assert "SOP-APP" in reply
