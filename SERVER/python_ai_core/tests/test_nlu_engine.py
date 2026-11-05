import unittest
import sys
import os

# Ensure SERVER/python_ai_core is in PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.nlu_engine import NLUEngine, NLUPayload

class TestNLUEngine(unittest.TestCase):
    """
    Automated Unit Test Suite for Enterprise NLU Engine.
    """

    def setUp(self):
        self.nlu = NLUEngine()

    def test_device_entity_extraction(self):
        query = "Tolong cek status PC-KASIR-01"
        payload = self.nlu.understand(query)
        self.assertEqual(payload.entities.get("device_name"), "PC-KASIR-01")

    def test_ip_address_extraction(self):
        query = "Ping IP address 192.168.1.50 sekarang"
        payload = self.nlu.understand(query)
        self.assertEqual(payload.entities.get("ip_address"), "192.168.1.50")

    def test_urgency_emergency_detection(self):
        query = "Darurat! Server Gudang-01 mati total segera tangani"
        payload = self.nlu.understand(query)
        self.assertEqual(payload.urgency, "EMERGENCY")

    def test_urgency_normal_detection(self):
        query = "Berapa jumlah printer yang terhubung saat ini?"
        payload = self.nlu.understand(query)
        self.assertEqual(payload.urgency, "NORMAL")

    def test_symptom_and_action_slot_filling(self):
        query = "Tolong bersihkan antrean print spooler macet pada PC-TMS-02"
        payload = self.nlu.understand(query)
        self.assertEqual(payload.entities.get("device_name"), "PC-TMS-02")
        self.assertIn("spooler macet", payload.entities.get("symptoms", []))
        self.assertIn("CLEAR_QUEUE", payload.entities.get("actions", []))

    def test_sentiment_negative_detection(self):
        query = "Jaringan down parah dan transaksi kasir error rugi besar"
        payload = self.nlu.understand(query)
        self.assertEqual(payload.sentiment, "NEGATIVE")

if __name__ == "__main__":
    unittest.main()
