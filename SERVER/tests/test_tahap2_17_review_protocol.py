"""
SERVER.tests.test_tahap2_17_review_protocol
============================================
Tahap 2.17 — AI NOC ↔ Jarvis Review Protocol & Audit Engine Test Suite

Menguji 5 modul Protokol & Engine Peninjauan:
  1. AINOCReviewContractValidator (Konstruksi & Validasi JSON Kontrak AI NOC)
  2. AIReviewProtocolEngine (Audit 6 Tahap: Evidence, Policy, SOP, Memory, Sandbox, LLM Peer)
  3. ReviewConfidenceDivergenceEvaluator (Evaluasi Delta Keyakinan AI NOC vs Jarvis: ACCEPT / REVIEW_REQUIRED)
  4. AuditRejectionLoopManager (Loop Penolakan Audit & Umpan Balik Remediasi ke AI NOC)
  5. Gateway Review Protocol Integration
"""
import unittest
from SERVER.orchestrator.protocol.review_contract import AINOCReviewContractValidator
from SERVER.orchestrator.protocol.ai_review_protocol import AIReviewProtocolEngine
from SERVER.orchestrator.protocol.confidence_divergence import ReviewConfidenceDivergenceEvaluator
from SERVER.orchestrator.protocol.audit_rejection_loop import AuditRejectionLoopManager
from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway


class TestAIReviewProtocolSuite(unittest.TestCase):
    def test_review_contract_validator(self):
        validator = AINOCReviewContractValidator()
        contract = validator.build_contract(
            incident_id="INC-TEST-17",
            hypothesis=["Backup Lock"],
            evidence=["[Netdata] CPU 98%"],
            recommended_actions=["Throttle Backup"],
            ai_noc_confidence=0.96,
        )
        self.assertEqual(contract.incident_id, "INC-TEST-17")
        self.assertEqual(contract.ai_noc_confidence, 0.96)
        self.assertFalse(contract.review_required)

    def test_ai_review_protocol_engine(self):
        validator = AINOCReviewContractValidator()
        engine = AIReviewProtocolEngine()

        # PASS Case
        contract_pass = validator.build_contract(
            incident_id="INC-PASS",
            hypothesis=["Backup Lock"],
            evidence=["[Netdata] CPU 98%"],
            recommended_actions=["Throttle Backup"],
        )
        report_pass = engine.audit_contract(contract_pass)
        self.assertEqual(report_pass.overall_protocol_verdict, "APPROVED")

        # REJECT Case (Missing evidence)
        contract_reject = validator.build_contract(
            incident_id="INC-REJ",
            hypothesis=["Memory Leak"],
            evidence=[],
            recommended_actions=["Restart Container"],
            missing_evidence=["PostgreSQL Log"],
        )
        report_reject = engine.audit_contract(contract_reject)
        self.assertEqual(report_reject.overall_protocol_verdict, "REJECTED_NEEDS_REMEDIATION")

    def test_confidence_divergence_evaluator(self):
        evaluator = ReviewConfidenceDivergenceEvaluator()

        # ACCEPT Case (Delta <= 15%)
        accept_res = evaluator.evaluate_divergence(ai_noc_confidence_pct=96, jarvis_review_confidence_pct=91)
        self.assertEqual(accept_res.divergence_delta_pct, 5)
        self.assertEqual(accept_res.audit_status, "ACCEPT")

        # REVIEW REQUIRED Case (Delta > 15%)
        review_res = evaluator.evaluate_divergence(ai_noc_confidence_pct=96, jarvis_review_confidence_pct=58)
        self.assertEqual(review_res.divergence_delta_pct, 38)
        self.assertEqual(review_res.audit_status, "REVIEW_REQUIRED")

    def test_audit_rejection_loop_manager(self):
        validator = AINOCReviewContractValidator()
        manager = AuditRejectionLoopManager()

        contract_missing = validator.build_contract(
            incident_id="INC-MISSING-LOG",
            hypothesis=["Table Lock"],
            evidence=["[Netdata] CPU 99%"],
            recommended_actions=["Kill Query"],
            missing_evidence=["PostgreSQL Log"],
        )
        feedback = manager.process_audit_result(contract_missing, is_audit_pass=False)

        self.assertTrue(feedback.is_rejected)
        self.assertIn("Evidence PostgreSQL Log belum tersedia", feedback.rejection_reason)
        self.assertGreater(len(feedback.required_remediation), 0)


class TestGatewayReviewProtocolIntegration(unittest.TestCase):
    def setUp(self):
        self.gateway = NOCIntegrationGateway()

    def test_gateway_returns_review_protocol_payload(self):
        req = {
            "query_id": "Q-REVIEW-2.17",
            "user_id": "Rama",
            "user_role": "Senior System Engineer",
            "query_text": "Audit independen kontrak AI NOC untuk insiden CPU High 98%",
            "telemetry_context": {"netdata_cpu_usage": 98.0},
        }
        res = self.gateway.handle_request(req)

        self.assertEqual(res["query_id"], "Q-REVIEW-2.17")
        self.assertIn("review_contract", res)
        self.assertEqual(res["review_contract"]["ai_noc_confidence"], 0.96)

        self.assertIn("review_protocol", res)
        self.assertEqual(res["review_protocol"]["overall_protocol_verdict"], "APPROVED")

        self.assertIn("confidence_divergence", res)
        self.assertEqual(res["confidence_divergence"]["audit_status"], "ACCEPT")

        self.assertIn("rejection_feedback", res)
        self.assertFalse(res["rejection_feedback"]["is_rejected"])

    def test_gateway_execute_ai_review_protocol_api(self):
        raw_contract = {
            "incident_id": "INC-RAW-99",
            "hypothesis": ["Memory Leak"],
            "evidence": ["[Netdata] RAM 98%"],
            "recommended_actions": ["Restart Service"],
            "confidence": 0.96,
            "missing_evidence": ["PostgreSQL Heap Dump Log"],
        }
        res = self.gateway.execute_ai_review_protocol(raw_contract)

        self.assertEqual(res["review_contract"]["incident_id"], "INC-RAW-99")
        self.assertEqual(res["review_protocol_report"]["overall_protocol_verdict"], "REJECTED_NEEDS_REMEDIATION")
        self.assertTrue(res["rejection_feedback"]["is_rejected"])
        self.assertIn("PostgreSQL Heap Dump Log", res["rejection_feedback"]["rejection_reason"])


if __name__ == "__main__":
    unittest.main()
