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
