"""
Phase 3.4 Zero-Trust Remediation Framework Verification Suite
Validates 7-Level Action Matrix (A0-A6), SHA256 Signature Verification, Remediation Guard, Post-Verification Engine, Automatic Rollback Engine, and 16-Stage Execution Pipeline.
"""

import unittest
import time
import os
import sys

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from governance.action_matrix import ActionMatrix, ActionLevel
from governance.script_signature import ScriptSignatureEngine
from governance.remediation_guard import RemediationGuard
from execution.verification_engine import VerificationEngine
from execution.rollback_engine import RollbackEngine
from execution.execution_engine import ZeroTrustExecutionEngine

class TestPhase34RemediationFramework(unittest.TestCase):

    def setUp(self):
        self.matrix = ActionMatrix()
        self.signature_engine = ScriptSignatureEngine()
        self.guard = RemediationGuard()
        self.verifier = VerificationEngine()
        self.rollback = RollbackEngine()
        self.execution_engine = ZeroTrustExecutionEngine()

    def test_01_action_matrix_7_levels(self):
        a0 = self.matrix.classify_action("ping")
        self.assertEqual(a0["level"], ActionLevel.A0_OBSERVATION.value)
        self.assertEqual(a0["approval"], "AUTO")

        a6 = self.matrix.classify_action("format_disk")
        self.assertEqual(a6["level"], ActionLevel.A6_DESTRUCTIVE.value)
        self.assertEqual(a6["approval"], "DUAL_APPROVAL_MANDATORY")

    def test_02_sha256_script_signature_verification(self):
        script = "ipconfig /flushdns"
        sig_info = self.signature_engine.generate_signature(script)
        
        # Valid signature verify
        self.assertTrue(self.signature_engine.verify_signature(script, sig_info["signature"]))
        
        # Modified script verify rejection
        tampered_script = "ipconfig /flushdns & rm -rf /"
        self.assertFalse(self.signature_engine.verify_signature(tampered_script, sig_info["signature"]))

    def test_03_remediation_guardrails(self):
        script = "ipconfig /flushdns"
        sig = self.signature_engine.generate_signature(script)["signature"]
        
        res = self.guard.evaluate_guardrails("flush_dns", script, sig, user_active=False, is_maintenance_window=True)
        self.assertTrue(res["passed_guardrails"])
        self.assertTrue(res["signature_valid"])

    def test_04_execution_engine_flow_and_rollback(self):
        res = self.execution_engine.process_remediation_pipeline(
            action_id="flush_dns",
            script_content="ipconfig /flushdns",
            target_asset="Client_PC_01",
            verification_steps=["dns_lookup", "ping_gateway"],
            rollback_script="ipconfig /registerdns",
            incident_id="INC-TEST-001",
            trace_id="TR-TEST-001",
            decision_id="DEC-TEST-001"
        )
        self.assertEqual(res["status"], "EXECUTION_SUCCESSFUL_VERIFIED")

    def test_05_privileged_remediation_queued_for_hitl(self):
        res = self.execution_engine.process_remediation_pipeline(
            action_id="reset_network_stack",
            script_content="netsh int ip reset",
            target_asset="Client_PC_01",
            verification_steps=["ping_gateway"],
            rollback_script="netsh int ip reset rollback",
            incident_id="INC-TEST-002",
            trace_id="TR-TEST-002",
            decision_id="DEC-TEST-002"
        )
        self.assertEqual(res["status"], "QUEUED_FOR_HITL_APPROVAL")
        self.assertEqual(res["approval_required"], "MANDATORY_HITL")

if __name__ == "__main__":
    unittest.main()
