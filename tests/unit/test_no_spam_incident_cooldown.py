"""
Unit Tests for Incident No-Spam & Cooldown Notification Mechanism
====================================================================
Tests the anti-spam, deduplication, global rate limiter, alert cooldown,
and log suppression components across the AI NOC system.
"""

import time
import logging
import unittest
from unittest.mock import MagicMock, patch

from SERVER.jarvis.proactive.jarvis_proactive_announcer import (
    ProactiveEvent,
    AlertCooldownManager,
    GlobalRateLimiter,
    NarrativeContextMemory,
    NarrativeHistoryEntry,
    JarvisProactiveAnnouncer,
    COOLDOWN_CONFIG,
    PERMANENT_COOLDOWN_TYPES,
)
from SERVER.python_ai_core.core.logger import DuplicateLogFilter


class TestAlertCooldownManager(unittest.TestCase):
    def setUp(self):
        self.mgr = AlertCooldownManager()

    def test_initial_announcement_allowed(self):
        event = ProactiveEvent(
            event_type="incident_new",
            severity="HIGH",
            title="CPU High",
            details="CPU at 95%",
            device="KASIR-01",
            incident_id="INC-100",
        )
        can_announce, remaining = self.mgr.can_announce(event)
        self.assertTrue(can_announce)
        self.assertEqual(remaining, 0)

    def test_subsequent_announcement_blocked_within_cooldown(self):
        event = ProactiveEvent(
            event_type="incident_new",
            severity="HIGH",
            title="CPU High",
            details="CPU at 95%",
            device="KASIR-01",
            incident_id="INC-100",
        )
        self.mgr.mark_announced(event)

        can_announce, remaining = self.mgr.can_announce(event)
        self.assertFalse(can_announce)
        self.assertGreater(remaining, 0)

    def test_severity_escalation_bypasses_cooldown(self):
        event_medium = ProactiveEvent(
            event_type="incident_new",
            severity="MEDIUM",
            title="Disk Usage Warning",
            details="Disk at 80%",
            device="SERVER-01",
            incident_id="INC-200",
        )
        self.mgr.mark_announced(event_medium)

        # Immediate escalation to CRITICAL
        event_critical = ProactiveEvent(
            event_type="incident_new",
            severity="CRITICAL",
            title="Disk Full Emergency",
            details="Disk at 99%",
            device="SERVER-01",
            incident_id="INC-200",
        )
        can_announce, remaining = self.mgr.can_announce(event_critical)
        self.assertTrue(can_announce, "Severity escalation should bypass active cooldown")
        self.assertEqual(remaining, 0)

    def test_permanent_cooldown_for_remediation(self):
        event_rem = ProactiveEvent(
            event_type="remediation_ok",
            severity="INFO",
            title="Service Restored",
            details="Process restarted successfully",
            device="KASIR-02",
            incident_id="INC-300",
        )
        can_announce, _ = self.mgr.can_announce(event_rem)
        self.assertTrue(can_announce)

        self.mgr.mark_announced(event_rem)

        can_announce_2, remaining = self.mgr.can_announce(event_rem)
        self.assertFalse(can_announce_2)
        self.assertEqual(remaining, -1)

    def test_reset_clears_cooldown(self):
        event = ProactiveEvent(
            event_type="early_warning",
            severity="MEDIUM",
            title="High RAM",
            details="RAM at 88%",
            device="SERVER-02",
        )
        self.mgr.mark_announced(event)
        self.assertFalse(self.mgr.can_announce(event)[0])

        self.mgr.reset(event)
        can_announce, remaining = self.mgr.can_announce(event)
        self.assertTrue(can_announce)
        self.assertEqual(remaining, 0)


class TestGlobalRateLimiter(unittest.TestCase):
    def setUp(self):
        self.limiter = GlobalRateLimiter(max_per_minute=3, min_gap=5)

    def test_min_gap_enforcement(self):
        allowed1, _ = self.limiter.can_announce()
        self.assertTrue(allowed1)
        self.limiter.record()

        # Immediate second announcement within min_gap=5s
        allowed2, reason2 = self.limiter.can_announce()
        self.assertFalse(allowed2)
        self.assertIn("Min gap", reason2)

    def test_max_per_minute_enforcement(self):
        now = time.time()
        with patch("time.time", side_effect=[now, now, now+6, now+6, now+12, now+12, now+18]):
            # 1st announcement
            allowed1, _ = self.limiter.can_announce()
            self.assertTrue(allowed1)
            self.limiter.record()

            # 2nd announcement at t+6
            allowed2, _ = self.limiter.can_announce()
            self.assertTrue(allowed2)
            self.limiter.record()

            # 3rd announcement at t+12
            allowed3, _ = self.limiter.can_announce()
            self.assertTrue(allowed3)
            self.limiter.record()

            # 4th announcement at t+18 (max 3 per minute exceeded)
            allowed4, reason4 = self.limiter.can_announce()
            self.assertFalse(allowed4)
            self.assertIn("Rate limit", reason4)


class TestNarrativeContextMemory(unittest.TestCase):
    def setUp(self):
        self.mem = NarrativeContextMemory(max_history=10)

    def test_add_and_get_context(self):
        event = ProactiveEvent(
            event_type="incident_new",
            severity="HIGH",
            title="CPU Spike",
            details="CPU 92%",
            device="KASIR-05",
        )
        self.mem.add(event, "Darurat! CPU kasir lima mengalami fluktuasi tinggi.")
        
        ctx = self.mem.get_context_for_llm(event)
        self.assertIn("JANGAN DIULANG", ctx)
        self.assertIn("KEJADIAN INI SUDAH TERJADI 1 KALI SEBELUMNYA", ctx)
        self.assertIn("Darurat! CPU kasir", ctx)


class TestJarvisProactiveAnnouncer(unittest.TestCase):
    @patch("SERVER.jarvis.proactive.jarvis_proactive_announcer.LLMDynamicNarrator.generate")
    def test_announce_flow_and_suppression(self, mock_generate):
        mock_generate.return_value = "Perhatian. Insiden baru terdeteksi pada server utama."

        announcer = JarvisProactiveAnnouncer()
        # Mock TTS to avoid binary dependencies
        announcer._tts_service = MagicMock()
        announcer._tts_service.synthesize.return_value = None

        event_payload = {
            "event_type": "incident_new",
            "severity": "HIGH",
            "title": "Database Connection Pool Exhausted",
            "details": "Conns 100/100",
            "device": "DB-MASTER-01",
            "incident_id": "INC-999",
        }

        # 1st attempt: Should succeed
        res1 = announcer.announce(event_payload)
        self.assertFalse(res1["skipped"])
        self.assertEqual(res1["event_type"], "incident_new")

        # 2nd immediate attempt: Should be suppressed by cooldown
        res2 = announcer.announce(event_payload)
        self.assertTrue(res2["skipped"])
        self.assertIn("cooldown", res2["skip_reason"])


class TestDuplicateLogFilter(unittest.TestCase):
    def setUp(self):
        self.filter = DuplicateLogFilter(window_sec=2.0)

    def test_duplicate_log_suppression(self):
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="System heartbeat ok",
            args=(),
            exc_info=None,
        )

        # 1st log line allowed
        self.assertTrue(self.filter.filter(record))
        # 2nd identical log line within 2.0s suppressed
        self.assertFalse(self.filter.filter(record))

        # Different log line allowed
        record2 = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=11,
            msg="System metric updated",
            args=(),
            exc_info=None,
        )
        self.assertTrue(self.filter.filter(record2))


if __name__ == "__main__":
    unittest.main()
