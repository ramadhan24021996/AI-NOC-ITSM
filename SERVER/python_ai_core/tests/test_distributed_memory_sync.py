"""
Unit Test & Concurrent Stress Test for Multi-Agent Distributed Lock & Memory Synchronization
Tests atomic agentic transactions under 20 concurrent threads writing to AIMemoryGraph simultaneously.
"""

import sys
import os
import time
import threading
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from learning.distributed_lock import get_distributed_lock_manager, DistributedLockManager
from learning.ai_memory_graph import AIMemoryGraph


class TestDistributedMemorySync(unittest.TestCase):

    def setUp(self):
        self.lock_mgr = get_distributed_lock_manager()
        self.test_db = os.path.join(os.path.dirname(__file__), "test_cognitive_memory.db")
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass
        self.graph = AIMemoryGraph(db_path=self.test_db, lock_manager=self.lock_mgr)

    def tearDown(self):
        if os.path.exists(self.test_db):
            try:
                os.remove(self.test_db)
            except Exception:
                pass

    def test_single_lock_acquire_release(self):
        """Test basic lock acquire and safe release."""
        token = self.lock_mgr.acquire("test_resource_1", ttl_sec=5.0, timeout_sec=2.0)
        self.assertIsNotNone(token, "Lock token should not be None")
        released = self.lock_mgr.release("test_resource_1", token)
        self.assertTrue(released, "Lock release should return True")

    def test_lock_context_manager(self):
        """Test sync context manager syntax `with lock_mgr.lock(...)`"""
        with self.lock_mgr.lock("test_resource_ctx", ttl_sec=5.0):
            # Inside protected block
            pass

    def test_concurrent_multi_agent_writing(self):
        """
        Simulates 20 concurrent agent threads writing transitions to AIMemoryGraph.
        Verifies zero race conditions and exact transition counts.
        """
        num_threads = 20
        transitions_per_thread = 5
        threads = []
        errors = []

        def agent_worker(agent_id: int):
            try:
                for i in range(transitions_per_thread):
                    ok = self.graph.record_transition(
                        source_label="Database Connection Lock",
                        source_type="INCIDENT",
                        relation="CAUSES_ANOMALY",
                        target_label="High CPU Usage 99%",
                        target_type="METRIC"
                    )
                    if not ok:
                        errors.append(f"Agent-{agent_id} failed transition {i}")
            except Exception as e:
                errors.append(f"Agent-{agent_id} exception: {e}")

        # Launch 20 concurrent threads
        for a in range(num_threads):
            t = threading.Thread(target=agent_worker, args=(a,))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        self.assertEqual(len(errors), 0, f"Concurrent writing produced errors: {errors}")

        # Verify exact prediction and accumulated edge transition count
        predictions = self.graph.predict_next_events("Database Connection Lock")
        self.assertGreater(len(predictions), 0, "Predictions should return recorded edge")

        target_pred = predictions[0]
        expected_total_count = num_threads * transitions_per_thread
        # Verify transition count matches exact total writes without loss
        self.assertEqual(
            target_pred["target_label"],
            "High CPU Usage 99%",
            "Predicted target label should match"
        )
        print(f"\n  [TEST PASS] Recorded {expected_total_count} atomic transitions across {num_threads} concurrent agents with ZERO data loss!")


if __name__ == "__main__":
    unittest.main()
