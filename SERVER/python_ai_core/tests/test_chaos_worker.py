"""
Unit Test Suite for Autonomous Chaos Engineering & Resilience Testing Worker
"""

import sys
import os
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from governance.chaos_injection_worker import AutonomousChaosWorker, get_chaos_worker


class TestAutonomousChaosWorker(unittest.TestCase):

    def setUp(self):
        self.worker = AutonomousChaosWorker()

    def test_create_experiment(self):
        exp = self.worker.create_experiment("OOM_MEM_STRESS", "SRV-TEST-01", ttl_sec=15)
        self.assertIsNotNone(exp["run_id"])
        self.assertEqual(exp["experiment"], "OOM_MEM_STRESS")
        self.assertEqual(exp["status"], "PREPARING")
        self.assertEqual(exp["ttl_sec"], 15)

    def test_simulate_agent_chaos_injection(self):
        exp = self.worker.create_experiment("NET_LATENCY_INJECT", "SRV-TEST-02", ttl_sec=10)
        res = self.worker.simulate_agent_chaos_injection(exp["run_id"])
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["chaos_status"], "ACTIVE")

    def test_verify_auto_rollback(self):
        exp = self.worker.create_experiment("SERVICE_CRASH_SIMULATION", "SRV-TEST-03", ttl_sec=10)
        self.worker.simulate_agent_chaos_injection(exp["run_id"])
        ver = self.worker.verify_auto_rollback(exp["run_id"], rollback_success=True)
        self.assertEqual(ver["status"], "success")
        self.assertTrue(ver["rollback_verified"])

    def test_run_resilience_suite(self):
        res = self.worker.run_resilience_suite("SRV-STAGING-01", fuzzing=True)
        self.assertEqual(res["status"], "success")
        self.assertEqual(res["total_experiments"], 3)
        self.assertTrue(res["fuzzing_enabled"])
        self.assertEqual(res["fuzzing_ratio"], "70% Common / 30% Exotic")
        for r in res["results"]:
            self.assertTrue(r["rollback_verified"])
            self.assertIn(r["category"], ["COMMON", "EXOTIC"])

    def test_randomized_fuzzing_selection(self):
        fuzz = self.worker.select_randomized_fuzzing_experiment(exotic_ratio=0.30)
        self.assertIn(fuzz["category"], ["COMMON", "EXOTIC"])
        self.assertIsNotNone(fuzz["experiment_type"])


if __name__ == "__main__":
    unittest.main()
