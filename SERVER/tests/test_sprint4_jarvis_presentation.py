"""
Sprint 4 — Jarvis Voice & Presentation Layer Test Suite
DoD Requirements:
1. STT -> Intent -> Integration Gateway -> Response -> TTS pipeline flow.
2. Persona configurable without code changes.
3. User session isolation.
4. Uses DTOs from SERVER.contracts and SERVER.shared.
5. ZERO direct dependencies from SERVER/jarvis to repositories, knowledge, memory, or tools.
6. 100% backward compatibility maintained.
"""
import unittest
import os
import sys
from typing import Dict, Any

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestSprint4JarvisPresentation(unittest.TestCase):
    def test_jarvis_domain_imports(self):
        from SERVER.jarvis import (
            SessionManager, PersonaRegistry, PresentationPromptManager,
            ConversationManager, AvatarStateManager, JarvisPresentationRuntime,
            ConversationContextDTO, VoiceAudioPayloadDTO, STTService, TTSService
        )
        self.assertTrue(issubclass(SessionManager, object))
        self.assertTrue(issubclass(PersonaRegistry, object))

    def test_session_isolation(self):
        from SERVER.jarvis import SessionManager
        sm = SessionManager()
        s1 = sm.create_session("sess_01", "usr_alice", persona_id="noc_engineer")
        s2 = sm.create_session("sess_02", "usr_bob", persona_id="executive")

        self.assertEqual(sm.active_session_count(), 2)
        sess1 = sm.get_session("sess_01")
        sess2 = sm.get_session("sess_02")
        self.assertIsNotNone(sess1)
        self.assertIsNotNone(sess2)
        assert sess1 is not None and sess2 is not None
        self.assertEqual(sess1.user_id, "usr_alice")
        self.assertEqual(sess2.user_id, "usr_bob")

        sm.close_session("sess_01")
        self.assertEqual(sm.active_session_count(), 1)
        self.assertIsNone(sm.get_session("sess_01"))

    def test_persona_registry_switching(self):
        from SERVER.jarvis import PersonaRegistry, PersonaConfig
        pr = PersonaRegistry()
        self.assertIn("noc_engineer", pr.list_ids())
        self.assertIn("executive", pr.list_ids())

        # Register custom persona dynamically without code modification
        pr.register(PersonaConfig(
            persona_id="custom_ops",
            name="Custom Operations",
            tone="technical",
            greeting="Custom Ops Active",
            closing="End of Brief",
            detail_level="high"
        ))

        custom = pr.get("custom_ops")
        self.assertIsNotNone(custom)
        self.assertEqual(custom.name, "Custom Operations")

    def test_presentation_prompt_formatting(self):
        from SERVER.jarvis import PresentationPromptManager, PersonaRegistry
        pm = PresentationPromptManager()
        pr = PersonaRegistry()

        noc_persona = pr.get("noc_engineer")
        self.assertIsNotNone(noc_persona)
        assert noc_persona is not None
        formatted = pm.format_presentation_response("Status Nginx Surabaya normal.", noc_persona)
        self.assertIn(noc_persona.greeting, formatted)
        self.assertIn("Status Nginx Surabaya normal.", formatted)

    def test_avatar_state_transitions(self):
        from SERVER.jarvis import AvatarStateManager, AvatarState
        av = AvatarStateManager()
        self.assertEqual(av.current_state, AvatarState.IDLE)

        av.set_state(AvatarState.LISTENING)
        self.assertEqual(av.current_state, AvatarState.LISTENING)
        payload = av.get_state_payload()
        self.assertEqual(payload["avatar_state"], "listening")
        self.assertEqual(payload["animation_trigger"], "anim_listening")

    def test_jarvis_no_forbidden_imports(self):
        """DoD Rule: SERVER/jarvis MUST NOT import repositories, knowledge, memory, tools, or DB directly."""
        jarvis_dir = os.path.join(PROJECT_ROOT, "SERVER", "jarvis")
        forbidden_keywords = [
            "SERVER.repositories",
            "SERVER.knowledge",
            "SERVER.memory",
            "SERVER.tools",
            "psycopg2",
            "sqlalchemy",
            "SELECT ",
            "INSERT INTO",
        ]
        violations = []
        for root, _, files in os.walk(jarvis_dir):
            for file in files:
                if file.endswith(".py"):
                    fp = os.path.join(root, file)
                    with open(fp, "r", encoding="utf-8") as f:
                        content = f.read()
                        for kw in forbidden_keywords:
                            if kw in content:
                                violations.append(f"{fp} contains forbidden '{kw}'")

        self.assertEqual(violations, [], f"Forbidden architectural imports found in jarvis: {violations}")

    def test_end_to_end_presentation_runtime_flow(self):
        """End-to-end presentation runtime flow with mock Integration Gateway, STT, and TTS."""
        from SERVER.jarvis import (
            JarvisPresentationRuntime, VoiceAudioPayloadDTO, STTService, TTSService
        )
        from SERVER.integration import UnifiedGateway
        from SERVER.contracts.schemas import IncidentQueryContract, IncidentResponseContract
        from SERVER.shared.enums import ExecutionTrack

        # Mock Integration Gateway
        class MockGateway(UnifiedGateway):
            def handle_request(self, raw_request: Dict[str, Any]) -> Dict[str, Any]:
                return {
                    "query_id": raw_request.get("query_id", "Q-1"),
                    "answer_text": "Nginx throughput is 1200 req/s, CPU 45%.",
                    "evidence_score": 0.95,
                    "execution_track": "fast_track"
                }

            def translate_to_contract(self, raw_request: Dict[str, Any]) -> IncidentQueryContract:
                return IncidentQueryContract(
                    query_id="Q-1", user_id="u1", user_role="operator", query_text="Check Nginx"
                )

            def translate_from_contract(self, response_contract: IncidentResponseContract) -> Dict[str, Any]:
                return {"query_id": response_contract.query_id, "answer_text": response_contract.answer_text}

        # Mock STT
        class MockSTT(STTService):
            def transcribe(self, payload: VoiceAudioPayloadDTO) -> str:
                return "Berapa throughput Nginx Surabaya saat ini?"

        # Mock TTS
        class MockTTS(TTSService):
            def synthesize(
                self,
                text: str,
                persona_id: str = "noc_engineer",
                locale: str = "id-ID",
                severity: str = "INFO",
                skip_normalization: bool = False,
            ) -> VoiceAudioPayloadDTO:
                return VoiceAudioPayloadDTO(
                    session_id="s1", audio_format="wav", sample_rate=16000, audio_bytes=b"RIFF...WAV", text_caption=text
                )

        gateway = MockGateway()
        stt = MockSTT()
        tts = MockTTS()

        runtime = JarvisPresentationRuntime(gateway=gateway, stt_service=stt, tts_service=tts)

        audio_in = VoiceAudioPayloadDTO(session_id="sess_e2e", audio_format="wav", audio_bytes=b"AUDIO_INPUT")
        result = runtime.process_voice_query("sess_e2e", audio_in)

        self.assertEqual(result["session_id"], "sess_e2e")
        self.assertEqual(result["query_text"], "Berapa throughput Nginx Surabaya saat ini?")
        self.assertIn("1200 req/s", result["answer_text"])
        self.assertIsNotNone(result["audio_output"])
        self.assertEqual(result["audio_output"].audio_format, "wav")


if __name__ == "__main__":
    unittest.main()
