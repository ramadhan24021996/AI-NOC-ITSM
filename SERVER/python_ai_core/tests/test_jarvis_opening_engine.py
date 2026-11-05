import unittest
import sys
import os
from datetime import datetime

# Ensure SERVER/python_ai_core is in PYTHONPATH
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from core.jarvis_opening_engine import JarvisOpeningEngine

class TestJarvisOpeningEngine(unittest.TestCase):
    """
    Automated Unit Test Suite for Jarvis Dynamic Conversation Opening Engine.
    """

    def setUp(self):
        self.engine = JarvisOpeningEngine()

    def test_opening_time_of_day_pagi(self):
        dt = datetime(2026, 8, 7, 8, 30) # Friday 08:30 AM
        ctx = {"current_time": dt}
        opening = self.engine.generate_opening(ctx)
        self.assertIn("pagi", opening.lower())

    def test_opening_time_of_day_malam(self):
        dt = datetime(2026, 8, 7, 21, 0) # Friday 21:00 PM
        ctx = {"current_time": dt}
        opening = self.engine.generate_opening(ctx)
        self.assertIn("malam", opening.lower())

    def test_opening_active_critical_incident(self):
        dt = datetime(2026, 8, 7, 14, 0)
        ctx = {
            "current_time": dt,
            "active_incidents": [{"device_name": "PC-NOC-01", "flag": "PING_TIMEOUT"}],
            "max_severity": "CRITICAL"
        }
        opening = self.engine.generate_opening(ctx)
        self.assertTrue("insiden" in opening.lower() or "anomali" in query_lower(opening) or "gangguan" in query_lower(opening) or "peringatan" in query_lower(opening))

    def test_opening_long_absence_welcome_back(self):
        dt = datetime(2026, 8, 7, 10, 0)
        ctx = {
            "current_time": dt,
            "days_since_last_session": 4.0
        }
        opening = self.engine.generate_opening(ctx)
        self.assertIn("kembali", opening.lower())

    def test_opening_diversity_and_uniqueness(self):
        # Generate 30 openings under normal context
        openings = set()
        for _ in range(30):
            openings.add(self.engine.generate_opening())
        
        # Verify high variance/diversity (should produce multiple unique variations)
        self.assertGreater(len(openings), 5)

def query_lower(text: str) -> str:
    return text.lower()

if __name__ == "__main__":
    unittest.main()
