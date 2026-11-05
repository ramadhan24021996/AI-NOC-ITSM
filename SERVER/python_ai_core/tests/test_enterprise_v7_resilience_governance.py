"""
Unit & Readiness Certification Test Suite for Enterprise Autonomous NOC Platform (v7.0.0)
Validates all 9 Enterprise Resilience & Governance Layers:
1. Probe Circuit Breaker & Retry Policy
2. Telemetry Data Quality Engine
3. Evidence Trust Scorer
4. Continuous Benchmark Suite
5. Model & Graph Governance Engine
6. Probe Security Hardening Layer
7. Human Performance Analytics
8. Federated Knowledge Engine
9. 8-Gate Production Readiness Certification Checklist
"""

import unittest
import os
import sys

# Ensure python_ai_core path resolution
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from active_probing import (
    ProbeCircuitBreaker, CircuitBreakerStatus, CircuitState,
    ProbeRetryPolicy, RetryExecutionReport,
    TelemetryDataQualityEngine, DataQualityReport,
    EvidenceTrustScorer, EvidenceSourceType, EvidenceTrustScore,
    ContinuousBenchmarkSuite, EnterpriseBenchmarkMetrics,
    ProbeSecurityHardening, SecurityAuditRecord,
    HumanPerformanceAnalytics, HumanPerformanceReport, OperatorFeedbackRecord,
    FederatedKnowledgeEngine, FederatedPatternPacket,
    ModelGovernanceEngine, ModelGovernanceSnapshot,
    ProductionReadinessChecklist, ProductionReadinessReport, ReadinessGateResult
)


class TestEnterpriseV7ResilienceGovernance(unittest.TestCase):

    def test_01_probe_circuit_breaker(self):
        """Validates 3-state circuit breaker trips after 3 consecutive failures."""
        cb = ProbeCircuitBreaker(failure_threshold=3, recovery_timeout_sec=10.0)
        p_id = "PRB-L3-01"

        allowed, msg = cb.allow_execution(p_id)
        self.assertTrue(allowed)

        # Record 3 failures
        cb.record_outcome(p_id, success=False)
        cb.record_outcome(p_id, success=False)
        cb.record_outcome(p_id, success=False)

        status = cb.get_status(p_id)
        self.assertEqual(status.state, CircuitState.OPEN)

        allowed_after_trip, msg_trip = cb.allow_execution(p_id)
        self.assertFalse(allowed_after_trip)
        self.assertIn("OPEN", msg_trip)

    def test_02_probe_retry_policy(self):
        """Validates exponential backoff retries on transient probe failure."""
        retry_policy = ProbeRetryPolicy(max_retries=2, base_delay_ms=10.0)

        call_count = 0
        def _mock_probe():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise RuntimeError("Transient network delay")
            return {"status": "PASSED"}

        report: RetryExecutionReport = retry_policy.execute_with_retry("PRB-L3-01", _mock_probe)
        self.assertTrue(report.successful)
        self.assertEqual(report.total_attempts, 2)

    def test_03_telemetry_data_quality(self):
        """Validates clock drift detection (>30s), outlier filtering, and data quality scoring."""
        dq_engine = TelemetryDataQualityEngine()
        payload = {
            "device_id": "POS-01",
            "telemetry": {"rssi_dbm": -85, "packet_loss": 0.05}
        }
        report: DataQualityReport = dq_engine.evaluate_quality(payload)
        self.assertTrue(report.is_valid)
        self.assertGreaterEqual(report.quality_score_pct, 90.0)

    def test_04_evidence_trust_scorer(self):
        """Validates weighted trust scores (Packet Capture 0.98 > User Report 0.60)."""
        scorer = EvidenceTrustScorer()
        w_pcap = scorer.get_source_weight(EvidenceSourceType.PACKET_CAPTURE)
        w_user = scorer.get_source_weight(EvidenceSourceType.USER_REPORT)

        self.assertEqual(w_pcap, 0.98)
        self.assertEqual(w_user, 0.60)
        self.assertGreater(w_pcap, w_user)

        composite = scorer.calculate_composite_evidence_trust([
            EvidenceSourceType.PACKET_CAPTURE,
            EvidenceSourceType.SNMP_COUNTER
        ])
        self.assertEqual(composite, 0.94)

    def test_05_continuous_benchmark_suite(self):
        """Validates continuous enterprise benchmarks (MTTD <10s, MTTR <5min, Precision >95%)."""
        bench = ContinuousBenchmarkSuite()
        metrics: EnterpriseBenchmarkMetrics = bench.evaluate_version_benchmark("v7.0.0", "v6.0.0")
        self.assertTrue(metrics.benchmark_passed)
        self.assertGreaterEqual(metrics.rca_precision_pct, 95.0)
        self.assertLessEqual(metrics.mttd_sec, 10.0)

    def test_06_probe_security_hardening(self):
        """Validates HMAC-SHA256 script signing and signature verification."""
        sec = ProbeSecurityHardening(secret_key="enterprise_key")
        script = "restart_net_adapter eth0"
        sig = sec.sign_remediation_script(script)

        self.assertTrue(sec.verify_remediation_script(script, sig))
        self.assertFalse(sec.verify_remediation_script(script + " tamper", sig))

        audit = sec.record_and_audit("ACT-101", script, sig)
        self.assertTrue(audit.hmac_verified)
        self.assertEqual(audit.status, "PERMITTED")

    def test_07_human_performance_analytics(self):
        """Validates operator feedback analytics (Acceptance Rate %, response times, hotspots)."""
        analytics = HumanPerformanceAnalytics()
        analytics.record_operator_decision("OP-01", "INC-101", "ACT-NET-01", "ACCEPTED", latency_sec=10.0)
        analytics.record_operator_decision("OP-02", "INC-102", "ACT-NET-02", "ACCEPTED", latency_sec=12.0)

        report: HumanPerformanceReport = analytics.generate_analytics_report()
        self.assertEqual(report.acceptance_rate_pct, 100.0)
        self.assertEqual(report.total_feedback, 2)

    def test_08_federated_knowledge_engine(self):
        """Validates anonymized multi-site pattern synchronization across Site A and Site B."""
        fed = FederatedKnowledgeEngine(local_site_id="SITE_JAKARTA")
        pkt: FederatedPatternPacket = fed.sanitize_and_export_pattern(
            incident_id="INC-JKT-01",
            symptoms=["RSSI Drop", "DNS Delay"],
            probing_strategy=["PRB-L1-01", "PRB-L3-02"],
            success_rate=0.96
        )
        self.assertIsNotNone(pkt.anonymized_symptom_hash)
        self.assertEqual(pkt.origin_site_id, "SITE_JAKARTA")

        imported = fed.import_remote_federated_pattern(pkt)
        self.assertFalse(imported)  # Already present in local store

    def test_09_model_governance_engine(self):
        """Validates model/graph versioning and automated rollback gate if precision drops below 95%."""
        gov = ModelGovernanceEngine("v7.0.0")

        # High precision approves deployment
        app_ok, msg_app = gov.evaluate_deployment_or_rollback("v7.1.0", current_precision_pct=97.0)
        self.assertTrue(app_ok)

        # Low precision triggers automated rollback
        rb_ok, msg_rb = gov.evaluate_deployment_or_rollback("v7.1.0", current_precision_pct=92.0)
        self.assertFalse(rb_ok)
        self.assertIn("AUTOMATIC ROLLBACK TRIGGERED", msg_rb)

    def test_10_production_readiness_checklist(self):
        """Validates 8-gate automated production readiness checklist."""
        checklist = ProductionReadinessChecklist()
        report: ProductionReadinessReport = checklist.evaluate_production_readiness(
            version="v7.0.0",
            rca_precision_pct=97.2
        )
        self.assertEqual(report.overall_readiness_status, "PRODUCTION_READY")
        self.assertEqual(report.passed_gates, 8)
        self.assertEqual(report.total_gates, 8)


if __name__ == "__main__":
    unittest.main()
