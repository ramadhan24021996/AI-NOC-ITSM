import unittest
import os
import sys

repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
server_path = os.path.join(repo_root, "SERVER")
python_ai_core_path = os.path.join(server_path, "python_ai_core")

if server_path not in sys.path:
    sys.path.insert(0, server_path)
if python_ai_core_path not in sys.path:
    sys.path.insert(0, python_ai_core_path)

from cognition.conversation_engine import (
    ConfidenceEngine,
    SilenceEngine,
    ClarificationEngine,
    GoalTracker,
    ActionExplanationLayer,
    ResponseFormatter,
    SentenceVariationEngine,
    EmotionLayer,
    AdaptiveConversationEngine,
    ProsodyMetadataGenerator,
    PersonaEngine,
    JarvisConversationEngine,
    get_conversation_engine
)


class TestJarvisConversationEngine(unittest.TestCase):

    def setUp(self):
        self.engine = get_conversation_engine()

    def test_01_confidence_engine(self):
        ce = ConfidenceEngine()
        # High confidence -> unchanged
        t1, c1 = ce.evaluate_confidence("CPU server normal.", 0.95)
        self.assertEqual(t1, "CPU server normal.")

        # Low confidence (< 0.70) -> humble statement
        t2, c2 = ce.evaluate_confidence("CPU server 95%", 0.50)
        self.assertTrue(t2.startswith("Saya belum cukup yakin"))
        self.assertIn("CPU server 95%", t2)

    def test_02_silence_engine(self):
        se = SilenceEngine()
        r1 = se.check_short_response("Terima kasih", operator_name="Rama")
        self.assertEqual(r1, "Sama-sama, Rama. Saya selalu siap jika Anda membutuhkan bantuan lebih lanjut.")

        r2 = se.check_short_response("Ya", operator_name="Rama")
        self.assertEqual(r2, "Baik, Rama. Saya lanjutkan.")

    def test_03_clarification_engine(self):
        cle = ClarificationEngine()
        c1 = cle.check_ambiguity("status server")
        self.assertIsNotNone(c1)
        self.assertIn("server database, server web", c1)

        c2 = cle.check_ambiguity("cek jaringan")
        self.assertIsNotNone(c2)
        self.assertIn("router core", c2)

    def test_04_goal_tracker(self):
        gt = GoalTracker()
        gt.set_goal("session_101", "Investigasi Insiden #204", {"device": "srv-accounting-01"})
        g = gt.get_goal("session_101")
        self.assertEqual(g["goal"], "Investigasi Insiden #204")
        self.assertEqual(g["details"]["device"], "srv-accounting-01")

    def test_05_action_explanation(self):
        act = ActionExplanationLayer()
        exp = act.explain_action("CHECK_LOGS", "srv-accounting-01")
        self.assertIn("srv-accounting-01", exp)
        self.assertIn("memeriksa log", exp.lower())

    def test_06_response_formatter(self):
        rf = ResponseFormatter()
        raw = "Berdasarkan analisis telemetri real-time, CPU server mencapai 95%."
        formatted = rf.format_text(raw)
        self.assertFalse(formatted.lower().startswith("berdasarkan analisis"))
        self.assertTrue(formatted.startswith("CPU server mencapai 95%."))

    def test_07_sentence_variation(self):
        sve = SentenceVariationEngine()
        var_text = sve.add_opener("CPU server mencapai 95%", is_urgent=False)
        self.assertTrue(any(var_text.startswith(op) for op in sve.normal_openers))

    def test_08_emotion_layer(self):
        el = EmotionLayer()
        t1 = el.determine_tone("LOW")
        self.assertEqual(t1["emotion"], "CALM")

        t2 = el.determine_tone("CRITICAL")
        self.assertEqual(t2["emotion"], "URGENT")

    def test_09_adaptive_audience_mode(self):
        ace = AdaptiveConversationEngine()
        txt = "CPU server mencapai 95%. Memory terpakai 82%. Swap 10%. Disk I/O 45%."
        
        op_text = ace.adapt_to_audience(txt, mode="OPERATOR")
        self.assertTrue(len(op_text.split(".")) <= 4)

        admin_text = ace.adapt_to_audience(txt, mode="ADMINISTRATOR")
        self.assertTrue(admin_text.startswith("[ADMIN METRICS]"))

    def test_10_prosody_metadata_generator(self):
        pmg = ProsodyMetadataGenerator()
        meta = pmg.generate_metadata("CPU server normal.", emotion="CALM", speed=0.95)
        self.assertEqual(meta["emotion"], "CALM")
        self.assertEqual(meta["speed"], 0.95)
        self.assertIn("pause_before_ms", meta)

    def test_11_persona_engine(self):
        pe = PersonaEngine()
        persona_text = pe.apply_jarvis_persona("CPU server mencapai 95%", operator_name="Rama")
        self.assertTrue(persona_text.startswith("Rama,"))

    def test_12_unified_conversation_engine_facade(self):
        res = self.engine.process_conversation(
            user_query="Bagaimana insiden hari ini?",
            raw_llm_response="Berdasarkan analisis telemetri, terdeteksi insiden CPU load tinggai pada srv-accounting-01.",
            operator_name="Rama",
            confidence_score=0.98,
            severity="WARN",
            audience_mode="OPERATOR"
        )
        self.assertIn("final_text", res)
        self.assertIn("prosody", res)
        self.assertTrue(res["final_text"].startswith("Rama,"))
        self.assertFalse("berdasarkan analisis" in res["final_text"].lower())


if __name__ == '__main__':
    unittest.main()
