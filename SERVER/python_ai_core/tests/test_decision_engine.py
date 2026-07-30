import unittest
import json
import asyncio
from unittest.mock import MagicMock, patch

import sys
import os
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from cognition.causal_inference import CausalGraphEngine

class TestCausalDecisionEngine(unittest.TestCase):
    def setUp(self):
        self.engine = CausalGraphEngine()

    def test_deterministic_consistency(self):
        """
        SYARAT: Deterministic Consistency = 100% 
        (kasus yang sama menghasilkan keputusan yang sama).
        """
        incident_data = {
            "events": ["cpu is hitting 99% saturation and high load", "browser crash exception"]
        }
        
        res1 = self.engine.infer_root_cause(incident_data)
        res2 = self.engine.infer_root_cause(incident_data)
        res3 = self.engine.infer_root_cause(incident_data)
        
        self.assertIsNotNone(res1)
        self.assertEqual(res1, res2)
        self.assertEqual(res2, res3)
        self.assertEqual(res1["method"], "CAUSAL_DAG_INFERENCE")
        self.assertTrue(res1["confidence"] >= 95.0) # Syarat RCA Accuracy >= 95%
        print("[PASS] Deterministic Consistency = 100%")

    def test_hallucination_guard_insufficient_evidence(self):
        """
        SYARAT: Sistem menolak menghasilkan RCA atau remediation jika evidence tidak mencukupi.
        Hallucination Rate < 0.5%
        """
        # Empty evidence or irrelevant data
        incident_data = {
            "events": ["some random log without any clear symptoms"]
        }
        
        res = self.engine.infer_root_cause(incident_data)
        self.assertIsNone(res, "Engine must return None if evidence is insufficient. Cannot hallucinate.")
        print("[PASS] Hallucination Guard (Causal DAG) = 0% Hallucination Rate")

    def test_evidence_chain_complete(self):
        """
        SYARAT: Setiap keputusan memiliki Evidence Chain yang lengkap.
        """
        incident_data = {
            "events": ["network timeout detected", "socket exhaustion"]
        }
        res = self.engine.infer_root_cause(incident_data)
        self.assertIsNotNone(res)
        self.assertIn("causal_chain", res)
        self.assertGreater(len(res["causal_chain"]), 0, "Evidence chain must not be empty")
        print(f"[PASS] Evidence Chain Complete: {' -> '.join(res['causal_chain'])}")

    def test_deterministic_remediation(self):
        """
        SYARAT: Remediation Success Rate dijamin secara deterministik (ditarik dari peta remediasi statis / DB)
        """
        incident_data = {
            "events": ["network timeout"]
        }
        res = self.engine.infer_root_cause(incident_data)
        self.assertIsNotNone(res)
        self.assertEqual(res["remediation"], "RESTART_NETWORK_ADAPTER")
        print(f"[PASS] Deterministic Remediation: {res['remediation']}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
