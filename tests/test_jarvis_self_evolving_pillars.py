"""
Unit Tests for JARVIS 6-Pillar Self-Evolving Voice Upgrade (V11.4)
==================================================================
Verifies:
  1. Pilar 1: Pluggable Skill Registry (@jarvis_skill) dispatch & introspection
  2. Pilar 2: Adaptive Operator Profiling (brevity SHORT/DETAILED + barge-in adaptation)
  3. Pilar 3: Telemetry-Grounded Chain-of-Thought + Governance Rule #6 validation
  4. Pilar 4: Closed-Loop Voice Feedback Learning (Voice RLHF / DPO)
  5. Pilar 5: Duplex Session skip_tts Clause Streaming & Barge-In adaptation
  6. Pilar 6: Hybrid Semantic N-Gram Similarity & Dynamic Phrase Learning
"""
from SERVER.contracts.schemas import StructuredActionContext
from SERVER.jarvis.cognition.chain_of_thought_engine import ChainOfThoughtEngine
from SERVER.jarvis.command.intent_router import JarvisCommandIntentRouter, JarvisIntent
from SERVER.jarvis.interfaces.presentation_dtos import VoiceAudioPayloadDTO
from SERVER.jarvis.memory.episodic_memory import EpisodicMemory
from SERVER.jarvis.runtime.jarvis_presentation_runtime import JarvisPresentationRuntime
from SERVER.jarvis.skills.skill_registry import get_skill_registry
from SERVER.jarvis.voice.duplex_session import JarvisVoiceDuplexSession


def test_pilar1_pluggable_skill_registry_dispatch():
    reg = get_skill_registry()
    skills = reg.list_skills()
    names = {s["name"] for s in skills}
    assert "voice_feedback_learning" in names
    assert "adaptive_operator_profile" in names
    assert "skill_registry_introspection" in names

    runtime = JarvisPresentationRuntime()
    dto = VoiceAudioPayloadDTO(
        session_id="sess-skill-1",
        audio_format="text",
        sample_rate=16000,
        audio_bytes=b"",
        text_caption="Jarvis tampilkan daftar skill jarvis",
    )
    res = runtime.process_voice_query("sess-skill-1", dto, operator_id="op_test")
    assert "JARVIS PLUGGABLE SKILL REGISTRY" in res["answer_text"]
    assert res["action_context"].action_taken == "LIST_JARVIS_SKILLS"


def test_pilar2_adaptive_operator_profiling_and_barge_in():
    mem = EpisodicMemory()
    prof = mem.infer_and_update_operator_preferences("op_barge", "cek status", barge_in=True)
    assert prof["barge_in_count"] >= 1
    prof = mem.infer_and_update_operator_preferences("op_barge", "cek status", barge_in=True)
    assert prof["preferred_brevity"] == "SHORT"

    prof_detail = mem.infer_and_update_operator_preferences("op_detail", "tolong jelaskan detail kondisi jaringan")
    assert prof_detail["preferred_brevity"] == "DETAILED"


def test_pilar3_telemetry_grounded_cot_and_rule6():
    cot = ChainOfThoughtEngine()
    res = cot.enhance_response(
        raw_response="Status tiket INC-901 menunggu verifikasi.",
        query="cek status insiden INC-901",
        live_data={
            "target_device": "SRV-CORE-01",
            "device_risk_history": "HIGH",
            "execution_status": "PENDING_VERIFICATION",
            "action_taken": "FORENSIC_RULE6_DRILLDOWN",
            "_sources": ["runtime_action_context"],
        },
        show_reasoning=True,
    )
    assert res.validate.requires_human is True
    assert "Rule #6" in res.validate.validation_notes


def test_pilar4_voice_feedback_learning_rule6_compliant():
    runtime = JarvisPresentationRuntime()
    dto = VoiceAudioPayloadDTO(
        session_id="sess-fb-1",
        audio_format="text",
        sample_rate=16000,
        audio_bytes=b"",
        text_caption="Jarvis koreksi analisa di pc-kasir-01 penyebab sebenarnya kabel switch port 4 longgar",
    )
    res = runtime.process_voice_query("sess-fb-1", dto, operator_id="op_noc")
    assert "Governance Rule #6" in res["answer_text"]
    assert res["action_context"].action_taken == "VOICE_FEEDBACK_LEARNING"


def test_pilar5_duplex_session_clause_streaming_and_barge_in():
    events = []
    session = JarvisVoiceDuplexSession("sess-dup-1", operator_user="op_duplex")
    session.state = "SPEAKING"
    session.trigger_barge_in(events.append)
    assert any(e.get("event") == "barge_in_ack" for e in events)


def test_pilar6_semantic_router_and_dynamic_phrase_learning():
    router = JarvisCommandIntentRouter()
    router.learn_phrase("audit kesehatan kluster kubernetes", JarvisIntent.QUERY, weight=0.95)
    res = router.classify("tolong audit kesehatan kluster kubernetes sekarang")
    assert res.intent == JarvisIntent.QUERY
    assert res.confidence >= 0.6

    # Typo / close variant semantic fallback
    sem_res = router.classify("kesehatn sistm")
    assert sem_res.intent == JarvisIntent.QUERY
    assert sem_res.confidence >= 0.5


def test_sandbox_verifier_blocks_destructive_commands_and_tracks_history():
    from SERVER.jarvis.sandbox.sandbox_verifier import JarvisSandboxVerifier
    from SERVER.jarvis.noc.noc_bridge import JarvisNOCBridge

    bridge = JarvisNOCBridge()
    verifier = JarvisSandboxVerifier(noc_bridge=bridge)

    safe_res = verifier.verify_action("RESTART_PRINT_SPOOLER", "PRT-KASIR-01")
    assert safe_res.is_safe is True
    assert safe_res.verification_score_pct >= 95.0

    blocked_res = verifier.verify_action("CUSTOM_CMD", "SRV-DB-01", raw_query="rm -rf / && drop database osi_system")
    assert blocked_res.is_safe is False
    assert blocked_res.verification_score_pct == 0.0

    hist_resp = bridge.get_sandbox_history()
    assert hist_resp.success is True
    assert "RIWAYAT PENGUJIAN SANDBOX" in hist_resp.summary

    latest_resp = bridge.get_sandbox_results(device="PRT-KASIR-01")
    assert latest_resp.success is True
    assert "RESTART_PRINT_SPOOLER" in latest_resp.summary


def test_data_pipeline_post_verification_rule6_and_canonical_metric_type():
    import time
    from SERVER.python_ai_core.verification.post_verification_engine import PostVerificationEngine
    from SERVER.python_ai_core.telemetry.telemetry_ingest_service import TelemetryIngestService

    class _StubCursor:
        def __init__(self, rows):
            self.rows = rows
            self.queries = []

        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc_val, exc_tb):
            return False

        def execute(self, sql, params=None):
            self.queries.append((sql, params))

        def fetchall(self):
            return self.rows

    class _StubConn:
        def __init__(self, rows):
            self.cur = _StubCursor(rows)
            self.committed = 0

        def cursor(self):
            return self.cur

        def commit(self):
            self.committed += 1

        def rollback(self):
            pass

    now_ts = time.time()
    # 1. Verify empty post-remediation telemetry on custom action does NOT falsely return PASS (Rule #6)
    empty_conn = _StubConn([])
    engine_empty = PostVerificationEngine(nc=None, db_conn=empty_conn)
    res_empty = engine_empty._verify_capability("PC-KASIR-01", "restart_print_spooler", exec_ts=now_ts - 5.0)
    assert res_empty["status"] == "UNKNOWN"
    assert res_empty["details"]["reason"] == "rule6_missing_post_remediation_telemetry"

    # 2. Verify canonical metric_type ('cpu_percent', 'memory_percent') with T_post >= T_exec passes
    fresh_rows = [
        ("cpu_percent", 28.5, now_ts),
        ("memory_percent", 54.0, now_ts),
    ]
    fresh_conn = _StubConn(fresh_rows)
    engine_fresh = PostVerificationEngine(nc=None, db_conn=fresh_conn)
    res_service = engine_fresh._verify_capability("PC-KASIR-01", "restart_service", exec_ts=now_ts - 2.0)
    assert res_service["status"] == "PASS"
    assert res_service["confidence"] == 100.0
    assert any("metric_type" in q[0] for q in fresh_conn.cur.queries)

    # 3. Verify stale telemetry where T_post < T_exec is rejected by Rule #6 causal ordering
    res_stale = engine_fresh._verify_capability("PC-KASIR-01", "restart_service", exec_ts=now_ts + 10.0)
    assert res_stale["status"] == "UNKNOWN"

    # 4. Verify dual-table state synchronization (incident_states + incidents + fleet_incidents)
    engine_fresh._update_state(101, "RESOLVED")
    executed_sqls = "\n".join(q[0] for q in fresh_conn.cur.queries)
    assert "ON CONFLICT (incident_id) DO UPDATE" in executed_sqls
    assert "UPDATE incidents" in executed_sqls
    assert "UPDATE fleet_incidents" in executed_sqls

    # 5. Verify TelemetryIngestService canonical metric extraction
    ingest = TelemetryIngestService()
    extracted = ingest._extract_canonical_metrics({
        "event_type": "custom_metrics",
        "cpu_usage": 42.0,
        "memory_percent": 61.5,
        "data": {"disk_usage": 70.0, "printer": {"queue_jobs": 2}},
    })
    extracted_dict = dict(extracted)
    assert extracted_dict["cpu_percent"] == 42.0
    assert extracted_dict["memory_percent"] == 61.5
    assert extracted_dict["disk_percent"] == 70.0
    assert extracted_dict["printer_queue_jobs"] == 2.0


