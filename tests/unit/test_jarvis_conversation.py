"""Unit tests: CHAT-1..CHAT-5 — JARVIS natural conversation."""
import os
import sys
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from SERVER.jarvis.conversation.conversation_manager import ConversationManager
from SERVER.jarvis.conversation.conversational_llm import ChatReply, ConversationalLLMEngine
from SERVER.jarvis.runtime.intent_chat_handler import IntentChatHandlerMixin


class _Handler(IntentChatHandlerMixin):
    def __init__(self, engine=None):
        self.noc_bridge = MagicMock()
        self.conv_mgr = ConversationManager()
        self._chat_engine = engine if engine is not None else False


def _ctx():
    return SimpleNamespace(action_taken=None, execution_status=None)


class TestConversationalEngine(unittest.TestCase):
    def test_no_provider_returns_none(self):
        eng = ConversationalLLMEngine(gemini_api_key="", ollama_model="")
        self.assertFalse(eng.available)
        self.assertIsNone(eng.reply("halo"))

    def test_gemini_payload_has_history_and_system(self):
        eng = ConversationalLLMEngine(gemini_api_key="k")
        captured = {}

        def fake_post(url, payload):
            captured.update(payload)
            return {"candidates": [{"content": {"parts": [{"text": "Baik, Bosku."}]}}]}

        eng._post_json = fake_post
        hist = [{"role": "user", "content": "server A lambat"},
                {"role": "assistant", "content": "Saya catat."},
                {"role": "user", "content": "kenapa ya?"}]
        r = eng.reply("kenapa ya?", history=hist)
        self.assertEqual(r.text, "Baik, Bosku.")
        self.assertEqual(r.provider, "gemini")
        roles = [c["role"] for c in captured["contents"]]
        self.assertEqual(roles, ["user", "model", "user"])  # current turn de-duplicated
        self.assertNotIn("tools", captured)  # CHAT-4: text-only
        self.assertIn("maksimal 3 kalimat", captured["systemInstruction"]["parts"][0]["text"])

    def test_falls_back_to_ollama(self):
        eng = ConversationalLLMEngine(gemini_api_key="k", ollama_model="llama3")
        eng._post_json = lambda url, p: None if "googleapis" in url else {"message": {"content": "Halo dari lokal"}}
        r = eng.reply("halo")
        self.assertEqual((r.text, r.provider), ("Halo dari lokal", "ollama"))


class TestChatHandler(unittest.TestCase):
    def test_free_chat_uses_llm_with_history(self):
        engine = MagicMock()
        engine.reply.return_value = ChatReply("Kabar baik, Bosku!", "gemini")
        h = _Handler(engine)
        h.conv_mgr.add_turn("s1", "user", "halo")
        h.conv_mgr.add_turn("s1", "assistant", "Halo!")
        ans, ctx = h._handle_chat("apa kabar?", None, _ctx(), session_id="s1")
        self.assertEqual(ans, "Kabar baik, Bosku!")
        self.assertEqual(ctx.execution_status, "SUCCESS")
        self.assertEqual(len(engine.reply.call_args.kwargs["history"]), 2)
        h.noc_bridge.send_chat_message.assert_not_called()  # free talk never posts to dashboard

    def test_free_chat_degraded_is_honest(self):
        h = _Handler()
        ans, ctx = h._handle_chat("apa kabar?", None, _ctx(), session_id="s1")
        self.assertEqual(ctx.execution_status, "DEGRADED")
        self.assertIn("tidak tersedia", ans)

    def test_send_message_failure_not_claimed_success(self):
        h = _Handler()
        h.noc_bridge.send_chat_message.return_value = SimpleNamespace(success=False, error="HTTP 503")
        ans, ctx = h._handle_chat("kirim pesan ke budi server normal", None, _ctx())
        self.assertEqual(ctx.execution_status, "FAILED")
        self.assertIn("HTTP 503", ans)
        self.assertNotIn("TERKIRIM", ans)

    def test_send_message_success_confirmed(self):
        h = _Handler()
        h.noc_bridge.send_chat_message.return_value = SimpleNamespace(success=True, error=None)
        ans, ctx = h._handle_chat("kirim pesan ke budi server normal", None, _ctx())
        self.assertEqual(ctx.execution_status, "SUCCESS")
        self.assertIn("dikonfirmasi NOC API", ans)

    def test_no_dummy_chat_history(self):
        h = _Handler()
        ans, ctx = h._handle_chat("baca chat", None, _ctx())
        self.assertNotIn("Budi", ans)
        self.assertEqual(ctx.execution_status, "UNSUPPORTED")

    def test_suggestion_uses_real_api(self):
        h = _Handler()
        h.noc_bridge.get_chat_suggestion.return_value = SimpleNamespace(success=True, data={"suggestion": "Cek kabel LAN"})
        ans, ctx = h._handle_chat("saran balasan", None, _ctx())
        self.assertIn("Cek kabel LAN", ans)
        self.assertNotIn("94%", ans)

    def test_close_session_failure(self):
        h = _Handler()
        h.noc_bridge.update_chat_session_status.side_effect = RuntimeError("timeout")
        ans, ctx = h._handle_chat("tutup chat", None, _ctx())
        self.assertEqual(ctx.execution_status, "FAILED")


class TestAgenticModelFallback(unittest.TestCase):
    def test_dispatcher_falls_back_to_next_model(self):
        from SERVER.jarvis.agentic.agentic_dispatcher import AgenticDispatcher
        d = AgenticDispatcher(MagicMock())
        d._models = ["dead-model", "good-model"]
        calls = []

        def fake(model, messages, schemas):
            calls.append(model)
            return None if model == "dead-model" else {"candidates": [{"content": {"parts": [{"text": "ok"}]}}]}

        d._call_gemini_model = fake
        self.assertIsNotNone(d._call_gemini_with_tools([], []))
        self.assertEqual(calls, ["dead-model", "good-model"])

    def test_no_retired_model_default(self):
        from SERVER.jarvis.conversation.conversational_llm import resolve_gemini_models
        self.assertNotIn("gemini-2.5-flash", resolve_gemini_models())


if __name__ == "__main__":
    unittest.main()
