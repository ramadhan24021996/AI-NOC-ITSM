"""
Unit Tests for JARVIS Voice Copilot Enhancements (#4, #5, #6):
  - #4: SHIFT_HANDOVER_REPORT ("Jarvis, laporan pergantian shift")
  - #5: FORENSIC_RULE6_DRILLDOWN ("Jarvis, jelaskan bukti resolusi insiden terakhir")
  - #6: Zero-Downtime Natural Indonesian Narrator (synthesize_deterministic_noc_narrative)
"""
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import MagicMock

from SERVER.jarvis.command.intent_router import JarvisCommandIntentRouter, JarvisIntent
from SERVER.jarvis.runtime.intent_query_handler import IntentQueryHandlerMixin
from SERVER.jarvis.runtime.shift_handoff_briefer import ShiftHandoffBriefer


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
    """Creates a mock psycopg2 connection whose cursor executes cursor_handler(sql, params)."""
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


class TestJarvisShiftHandoverReport:
    """Tests for Feature #4: Shift Handover Executive Briefing."""

    def test_intent_router_classifies_shift_handover_as_query(self):
        router = JarvisCommandIntentRouter()
        res = router.classify("Jarvis, laporan pergantian shift")
        assert res.intent == JarvisIntent.QUERY

    def test_shift_handover_briefing_with_postgres_data(self):
        def _handler(sql, params):
            q = " ".join(sql.split()).lower()
            if "as resolved_total" in q and "as rule6_verified" in q:
                return (7, 7)
            if "upper(coalesce(flag, 'open')) not in ('resolved'" in q:
                return [
                    (104, "PC-KASIR-02", 7, "PENDING_VERIFICATION", "Spooler Stuck"),
                    (109, "GW-CABANG-01", 3, "AWAITING_HITL", "Packet Loss 85%"),
                ]
            if "group by device_name" in q:
                return [
                    ("PC-KASIR-02", 5),
                    ("GW-CABANG-01", 3),
                    ("PRINTER-GUDANG-01", 2),
                ]
            if "and execution_time is not null" in q:
                return (2,)
            return None

        mock_bridge = MagicMock()
        briefer = ShiftHandoffBriefer(
            noc_bridge=mock_bridge,
            db_conn=_make_mock_conn(_handler),
        )
        qh = _QueryHandler(noc_bridge=mock_bridge, briefer=briefer)

        reply, ctx = qh.ask("Jarvis, laporan pergantian shift", session_id="s-shift")
        assert ctx.action_taken == "SHIFT_HANDOVER_REPORT"
        assert ctx.execution_status == "SUCCESS"
        assert "7 insiden selesai" in reply
        assert "Rule #6" in reply
        assert "INC-#104" in reply and "PC-KASIR-02" in reply
        assert "INC-#109" in reply and "GW-CABANG-01" in reply
        assert "18/20" in reply


class TestJarvisForensicRule6Drilldown:
    """Tests for Feature #5: Forensic Rule #6 & Causal Drilldown via Voice."""

    def test_intent_router_classifies_forensic_rule6_as_query(self):
        router = JarvisCommandIntentRouter()
        res = router.classify("Jarvis, jelaskan bukti resolusi insiden terakhir")
        assert res.intent == JarvisIntent.QUERY

    def test_forensic_rule6_verified_when_t_post_gte_t_exec(self):
        t_exec = datetime(2026, 11, 6, 14, 0, 0, tzinfo=timezone.utc)
        t_post = t_exec + timedelta(seconds=18)

        def _handler(sql, params):
            q = " ".join(sql.split()).lower()
            if "from incidents" in q:
                return (
                    205,
                    "PC-KASIR-01",
                    7,
                    "RESOLVED",
                    "Print Spooler Frozen (POST telemetry verified)",
                    t_exec,
                    t_post,
                    t_post,
                    t_exec - timedelta(minutes=2),
                )
            if "from remediation_logs" in q:
                return ("SOP-PRT-02 Restart Spooler", "SUCCESS", t_exec)
            if "from ai_evidence_logs" in q:
                return [("POST_REMEDIATION_TELEMETRY", '{"spooler": "RUNNING", "queue": 0}', t_post)]
            return None

        briefer = ShiftHandoffBriefer(db_conn=_make_mock_conn(_handler))
        qh = _QueryHandler(briefer=briefer)

        reply, ctx = qh.ask(
            "Jarvis, jelaskan bukti resolusi insiden terakhir", session_id="s-r6-ok"
        )
        assert ctx.action_taken == "FORENSIC_RULE6_DRILLDOWN"
        assert ctx.execution_status == "SUCCESS"
        assert "#205" in reply
        assert "STATUS RULE #6 SAH (TERVERIFIKASI)" in reply
        assert "Invarian T_post >= T_exec: VALID" in reply

    def test_forensic_rule6_locked_when_post_telemetry_missing(self):
        t_exec = datetime(2026, 11, 6, 14, 10, 0, tzinfo=timezone.utc)

        def _handler(sql, params):
            q = " ".join(sql.split()).lower()
            if "from incidents" in q:
                return (
                    206,
                    "PC-KASIR-09",
                    2,
                    "PENDING_VERIFICATION",
                    "Network Adapter Reset (ACK received)",
                    t_exec,
                    None,
                    None,
                    t_exec - timedelta(minutes=1),
                )
            if "from remediation_logs" in q:
                return ("SOP-NET-01 Reset NIC", "ACK_RECEIVED", t_exec)
            if "from ai_evidence_logs" in q:
                return []
            return None

        briefer = ShiftHandoffBriefer(db_conn=_make_mock_conn(_handler))
        qh = _QueryHandler(briefer=briefer)

        reply, ctx = qh.ask(
            "Jarvis, kenapa masih pending verification insiden #206?", session_id="s-r6-lock"
        )
        assert ctx.action_taken == "FORENSIC_RULE6_DRILLDOWN"
        assert ctx.execution_status == "SUCCESS"
        assert "#206" in reply
        assert "STATUS RULE #6 TERKUNCI (PENDING_VERIFICATION)" in reply
        assert "Bukti Telemetri Pasca-Remediasi" in reply


class TestJarvisDeterministicIndonesianNarrator:
    """Tests for Feature #6: Zero-Downtime Natural Indonesian Narrator when Cloud LLM is offline."""

    def test_deterministic_narrator_replaces_offline_gateway_fallback(self):
        def _handler(sql, params):
            q = " ".join(sql.split()).lower()
            if "as resolved_total" in q and "as rule6_verified" in q:
                return (14, 14)
            if "upper(coalesce(flag, 'open')) not in ('resolved'" in q:
                return [
                    (301, "SW-CORE-01", 3, "PENDING_VERIFICATION", "BGP Peer Flapping"),
                    (302, "PC-KASIR-04", 7, "AWAITING_HITL", "Spooler Jam"),
                ]
            if "group by device_name" in q:
                return [("SW-CORE-01", 4)]
            if "and execution_time is not null" in q:
                return (3,)
            return None

        briefer = ShiftHandoffBriefer(db_conn=_make_mock_conn(_handler))
        mock_gw = MagicMock()
        mock_gw.handle_request.return_value = {
            "answer_text": (
                "⚠️ Mode Inferensi Lokal (Gemini API: Offline / Lokal).\n"
                "Ringkasan Analitik: Data Tidak Tersedia (Menggunakan rule-based inference fallback)."
            )
        }
        qh = _QueryHandler(briefer=briefer, gateway=mock_gw)

        reply, ctx = qh.ask(
            "Jarvis, bagaimana kondisi operasional tiket di jaringan saat ini?",
            session_id="s-offline-nar",
        )
        assert ctx.action_taken == "DETERMINISTIC_NOC_NARRATOR"
        assert ctx.execution_status == "SUCCESS"
        assert "Berdasarkan data faktual NOC saat ini" in reply
        assert "2 insiden aktif" in reply
        assert "1 menunggu verifikasi Rule #6 di PENDING_VERIFICATION" in reply
        assert "14 insiden telah selesai" in reply
        assert "SW-CORE-01" in reply
