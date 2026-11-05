"""
LF-1 Learning Framework — Full Integration Test Suite
Tests all 9 concrete implementations against their interface contracts.
Runs in offline/fallback mode (no DB or Redis required).
"""
import asyncio
import hashlib
import json
import logging
import sys
import time
import unittest

# ─── Patch sys.path for local imports ─────────────────────────────────────────
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

logging.basicConfig(level=logging.WARNING)


# ==============================================================================
# 1. Knowledge Store Tests
# ==============================================================================
class TestPostgresKnowledgeStore(unittest.TestCase):
    """Tests for PostgresKnowledgeStore (in-memory fallback mode)."""

    def setUp(self):
        from learning.knowledge_store.knowledge_store_impl import PostgresKnowledgeStore
        self.store = PostgresKnowledgeStore()
        # Force in-memory fallback (no DB in CI)
        self.store._db_available = False

    def test_add_document(self):
        ok = self.store.add_document("doc-001", "DNS resolution failure on site A", {"source": "telemetry"})
        self.assertTrue(ok)
        self.assertIn("doc-001", self.store._memory)

    def test_add_document_idempotent(self):
        self.store.add_document("doc-002", "TCP SYN timeout", {})
        self.store.add_document("doc-002", "TCP SYN timeout UPDATED", {})  # Should NOT overwrite
        self.assertEqual(self.store._memory["doc-002"]["content"], "TCP SYN timeout")

    def test_update_document(self):
        self.store.add_document("doc-003", "Original content", {})
        ok = self.store.update_document("doc-003", "Updated content")
        self.assertTrue(ok)
        self.assertEqual(self.store._memory["doc-003"]["content"], "Updated content")
        self.assertEqual(self.store._memory["doc-003"]["version"], 2)

    def test_update_nonexistent_document(self):
        ok = self.store.update_document("nonexistent", "content")
        self.assertFalse(ok)

    def test_archive_document(self):
        self.store.add_document("doc-004", "Old knowledge", {})
        ok = self.store.archive_document("doc-004")
        self.assertTrue(ok)
        self.assertTrue(self.store._memory["doc-004"]["archived"])

    def test_update_archived_document_fails(self):
        self.store.add_document("doc-005", "Content", {})
        self.store.archive_document("doc-005")
        ok = self.store.update_document("doc-005", "Updated content")
        self.assertFalse(ok)

    def test_search_finds_matching_document(self):
        self.store.add_document("doc-006", "DHCP lease exhaustion detected on subnet 10.0.1.0/24", {})
        self.store.add_document("doc-007", "CPU temperature spike on server-01", {})
        results = self.store.search("DHCP")
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0]["doc_id"], "doc-006")

    def test_search_excludes_archived(self):
        self.store.add_document("doc-008", "TLS handshake failure", {})
        self.store.archive_document("doc-008")
        results = self.store.search("TLS")
        self.assertEqual(len(results), 0)

    def test_version_returns_v1_for_new_doc(self):
        self.store.add_document("doc-009", "content", {})
        self.assertEqual(self.store.version("doc-009"), "v1")

    def test_version_increments_on_update(self):
        self.store.add_document("doc-010", "v1 content", {})
        self.store.update_document("doc-010", "v2 content")
        self.assertEqual(self.store.version("doc-010"), "v2")

    def test_version_not_found(self):
        self.assertEqual(self.store.version("nonexistent"), "NOT_FOUND")

    def test_checksum_integrity(self):
        content = "DNS resolution failure"
        expected_checksum = hashlib.sha256(content.encode()).hexdigest()
        self.store.add_document("doc-011", content, {})
        self.assertEqual(self.store._memory["doc-011"]["checksum"], expected_checksum)


# ==============================================================================
# 2. Evaluator Tests
# ==============================================================================
class TestLLMEvaluationContract(unittest.TestCase):
    """Tests for LLMEvaluationContract."""

    def setUp(self):
        from learning.evaluator.evaluator_impl import LLMEvaluationContract
        self.evaluator = LLMEvaluationContract()
        self.sample_payload = {
            "header": {"protocol_version": "v6.1", "message_type": "TELEMETRY", "message_id": "msg-001"},
            "routing": {"tenant_id": "customer-A", "device_id": "pc-101"},
            "payload": {"metric_class": "DNS", "value": 1.0, "quality_score": 0.9},
            "confidence": 0.85,
        }

    def test_evaluate_returns_four_dimensions(self):
        scores = self.evaluator.evaluate(self.sample_payload)
        self.assertIn("accuracy", scores)
        self.assertIn("relevance", scores)
        self.assertIn("confidence", scores)
        self.assertIn("novelty", scores)

    def test_evaluate_scores_in_valid_range(self):
        scores = self.evaluator.evaluate(self.sample_payload)
        for dim, score in scores.items():
            self.assertGreaterEqual(score, 0.0, f"{dim} score below 0")
            self.assertLessEqual(score, 1.0, f"{dim} score above 1")

    def test_validate_requires_header_and_payload(self):
        bad_payload = {"only_routing": {}}
        ok = self.evaluator.validate(bad_payload)
        self.assertFalse(ok)

    def test_validate_passes_valid_payload(self):
        ok = self.evaluator.validate(self.sample_payload)
        self.assertTrue(ok)

    def test_score_returns_weighted_composite(self):
        self.evaluator.evaluate(self.sample_payload)
        composite = self.evaluator.score({})
        self.assertGreater(composite, 0.0)
        self.assertLessEqual(composite, 1.0)

    def test_benchmark_returns_known_categories(self):
        results = self.evaluator.benchmark()
        self.assertIn("dns_rca_accuracy", results)
        self.assertIn("false_positive_rate", results)
        all_in_range = all(0.0 <= v <= 1.0 for v in results.values())
        self.assertTrue(all_in_range)

    def test_approve_high_quality_payload(self):
        self.evaluator.evaluate(self.sample_payload)
        # score is ~0.875 for quality_score=0.9, known metric class
        result = self.evaluator.approve()
        self.assertIsInstance(result, bool)

    def test_reject_sets_rejected_flag(self):
        self.assertTrue(self.evaluator.reject())
        self.assertTrue(self.evaluator._rejected)
        self.assertFalse(self.evaluator._approved)

    def test_adapted_payload_gets_lower_novelty(self):
        adapted = dict(self.sample_payload)
        adapted["header"] = {**self.sample_payload["header"], "protocol_version": "v6.1_adapted"}
        scores = self.evaluator.evaluate(adapted)
        self.assertEqual(scores["novelty"], 0.5)

    def test_unknown_metric_class_gets_lower_relevance(self):
        unknown_payload = dict(self.sample_payload)
        unknown_payload["payload"] = {**self.sample_payload["payload"], "metric_class": "QUANTUM_BEAM"}
        scores = self.evaluator.evaluate(unknown_payload)
        self.assertEqual(scores["relevance"], 0.5)


# ==============================================================================
# 3. Scheduler Tests
# ==============================================================================
class TestAsyncIOScheduler(unittest.TestCase):
    """Tests for AsyncIOScheduler."""

    def setUp(self):
        from learning.scheduler.scheduler_impl import AsyncIOScheduler
        self.scheduler = AsyncIOScheduler()

    def test_register_job(self):
        ok = self.scheduler.register_job("job-1", "@every 60s", lambda p: None)
        self.assertTrue(ok)
        self.assertIn("job-1", self.scheduler._jobs)

    def test_register_duplicate_job_returns_false(self):
        self.scheduler.register_job("job-2", "@every 30s", lambda p: None)
        ok = self.scheduler.register_job("job-2", "@every 30s", lambda p: None)
        self.assertFalse(ok)

    def test_apply_retry_policy(self):
        self.scheduler.register_job("job-3", "@every 120s", lambda p: None)
        self.scheduler.apply_retry_policy("job-3", 5)
        self.assertEqual(self.scheduler._jobs["job-3"].max_retries, 5)

    def test_apply_timeout_policy(self):
        self.scheduler.register_job("job-4", "@every 60s", lambda p: None)
        self.scheduler.apply_timeout_policy("job-4", 5000)
        self.assertEqual(self.scheduler._jobs["job-4"].timeout_ms, 5000)

    def test_enqueue_unknown_job_returns_false(self):
        ok = self.scheduler.enqueue("nonexistent-job", {})
        self.assertFalse(ok)

    def test_enqueue_known_job_returns_true(self):
        self.scheduler.register_job("job-5", "@every 60s", lambda p: None)
        ok = self.scheduler.enqueue("job-5", {"test": True})
        self.assertTrue(ok)
        self.assertFalse(self.scheduler._queue.empty())

    def test_execute_sync_job_via_event_loop(self):
        """Tests that a synchronous job runs successfully via run_in_executor."""
        results = []
        self.scheduler.register_job("job-sync", "@every 60s", lambda p: results.append(p))

        async def _run():
            self.scheduler.enqueue("job-sync", {"key": "value"})
            await self.scheduler._execute_job("job-sync", {"key": "value"})

        asyncio.run(_run())
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0], {"key": "value"})


    def test_cron_to_interval_parser(self):
        from learning.scheduler.scheduler_impl import AsyncIOScheduler
        self.assertEqual(AsyncIOScheduler._cron_to_interval("@every 300s"), 300)
        self.assertEqual(AsyncIOScheduler._cron_to_interval("@every 60s"), 60)
        self.assertIsNone(AsyncIOScheduler._cron_to_interval("*/5 * * * *"))


# ==============================================================================
# 4. Versioning Tests
# ==============================================================================
class TestSemanticVersionController(unittest.TestCase):
    """Tests for SemanticVersionController."""

    def setUp(self):
        from learning.versioning.versioning_impl import SemanticVersionController
        self.vc = SemanticVersionController()

    def test_same_version_compatible(self):
        self.assertTrue(self.vc.check_compatibility("2.3.1", "2.3.1"))

    def test_same_major_different_minor_compatible(self):
        self.assertTrue(self.vc.check_compatibility("2.3.1", "2.4.0"))

    def test_same_major_different_patch_compatible(self):
        self.assertTrue(self.vc.check_compatibility("3.1.0", "3.1.5"))

    def test_different_major_incompatible(self):
        self.assertFalse(self.vc.check_compatibility("1.0.0", "2.0.0"))

    def test_invalid_version_format_returns_false(self):
        self.assertFalse(self.vc.check_compatibility("v1.0", "1.0.0"))

    def test_trigger_migration_hook_noop(self):
        ok = self.vc.trigger_migration_hook("1.0.0")
        self.assertTrue(ok)
        self.assertEqual(len(self.vc._migration_history), 1)

    def test_generate_rollback_metadata_has_required_fields(self):
        meta = self.vc.generate_rollback_metadata("3.2.5")
        self.assertIn("snapshot_version", meta)
        self.assertIn("rollback_target", meta)
        self.assertIn("can_rollback", meta)
        self.assertEqual(meta["snapshot_version"], "3.2.5")

    def test_rollback_target_decrements_patch(self):
        meta = self.vc.generate_rollback_metadata("1.0.3")
        self.assertEqual(meta["rollback_target"], "1.0.2")

    def test_rollback_target_at_patch_zero_decrements_minor(self):
        meta = self.vc.generate_rollback_metadata("2.5.0")
        self.assertEqual(meta["rollback_target"], "2.4.0")


# ==============================================================================
# 5. Audit Tests
# ==============================================================================
class TestLearningAuditLogger(unittest.TestCase):
    """Tests for LearningAuditLogger — file fallback mode."""

    def setUp(self):
        from learning.audit.audit_impl import LearningAuditLogger, _FALLBACK_LOG_FILE
        self.logger = LearningAuditLogger(actor="test_actor")
        # Ensure file fallback is invoked by forcing DB write to return False in fallback tests
        self.logger._write_to_db = lambda *args, **kwargs: False
        self.log_file = _FALLBACK_LOG_FILE
        # Clear log file before each test
        if os.path.exists(self.log_file):
            os.remove(self.log_file)

    def test_log_writes_to_file_when_db_unavailable(self):
        from learning.audit.interfaces import AuditEvent
        self.logger.log(AuditEvent.LEARNING_STARTED, {"job_id": "test-job-001"})
        self.assertTrue(os.path.exists(self.log_file))
        with open(self.log_file) as f:
            record = json.loads(f.readline())
        self.assertEqual(record["action_type"], "LF1_LEARNING_STARTED")
        self.assertEqual(record["actor"], "test_actor")
        self.assertEqual(record["target"], "test-job-001")

    def test_all_audit_events_are_mapped(self):
        from learning.audit.interfaces import AuditEvent
        from learning.audit.audit_impl import LearningAuditLogger
        for event in AuditEvent:
            self.assertIn(event, LearningAuditLogger._EVENT_MAP)

    def test_multiple_logs_are_appended(self):
        from learning.audit.interfaces import AuditEvent
        self.logger.log(AuditEvent.LEARNING_STARTED, {"job_id": "job-A"})
        self.logger.log(AuditEvent.EVALUATION_STARTED, {"job_id": "job-A"})
        self.logger.log(AuditEvent.LEARNING_FINISHED, {"job_id": "job-A"})
        with open(self.log_file) as f:
            lines = f.readlines()
        self.assertEqual(len(lines), 3)


# ==============================================================================
# 6. Metrics Tests
# ==============================================================================
class TestPrometheusMetricsTracker(unittest.TestCase):
    """Tests for PrometheusMetricsTracker."""

    def setUp(self):
        from learning.metrics.metrics_impl import PrometheusMetricsTracker
        self.tracker = PrometheusMetricsTracker()
        self.tracker._redis = None  # Disable Redis for tests

    def test_record_increments_count(self):
        from learning.metrics.interfaces import LearningKPI
        self.tracker.record(LearningKPI.LEARNING_ACCURACY, 0.85)
        self.assertEqual(self.tracker._counts[LearningKPI.LEARNING_ACCURACY], 1)

    def test_average_calculated_correctly(self):
        from learning.metrics.interfaces import LearningKPI
        self.tracker.record(LearningKPI.LEARNING_ACCURACY, 0.8)
        self.tracker.record(LearningKPI.LEARNING_ACCURACY, 0.9)
        avg = self.tracker.average(LearningKPI.LEARNING_ACCURACY)
        self.assertAlmostEqual(avg, 0.85, places=4)

    def test_min_max_tracked(self):
        from learning.metrics.interfaces import LearningKPI
        self.tracker.record(LearningKPI.FALSE_POSITIVE, 0.03)
        self.tracker.record(LearningKPI.FALSE_POSITIVE, 0.12)
        self.tracker.record(LearningKPI.FALSE_POSITIVE, 0.05)
        self.assertAlmostEqual(self.tracker._mins[LearningKPI.FALSE_POSITIVE], 0.03, places=4)
        self.assertAlmostEqual(self.tracker._maxs[LearningKPI.FALSE_POSITIVE], 0.12, places=4)


    def test_history_capped_at_500(self):
        from learning.metrics.interfaces import LearningKPI
        for i in range(600):
            self.tracker.record(LearningKPI.TOKEN_COST, float(i))
        self.assertEqual(len(self.tracker._history[LearningKPI.TOKEN_COST]), 500)

    def test_exposition_contains_all_kpis(self):
        from learning.metrics.interfaces import LearningKPI
        self.tracker.record(LearningKPI.LEARNING_ACCURACY, 0.9)
        output = self.tracker.exposition()
        for kpi in LearningKPI:
            self.assertIn(kpi.value, output)

    def test_summary_returns_all_kpis(self):
        summary = self.tracker.summary()
        from learning.metrics.interfaces import LearningKPI
        for kpi in LearningKPI:
            self.assertIn(kpi.value, summary)

    def test_reset_clears_all(self):
        from learning.metrics.interfaces import LearningKPI
        self.tracker.record(LearningKPI.LEARNING_ACCURACY, 0.9)
        self.tracker.reset()
        self.assertEqual(len(self.tracker._counts), 0)
        self.assertEqual(self.tracker._total_records, 0)


# ==============================================================================
# 7. Feature Validator Tests
# ==============================================================================
class TestTelemetryFeatureValidator(unittest.TestCase):
    """Tests for TelemetryFeatureValidator."""

    def setUp(self):
        from learning.feature_store.validators.validator_impl import TelemetryFeatureValidator
        self.validator = TelemetryFeatureValidator()
        self.valid_payload = {
            "header": {"protocol_version": "v6.1", "message_type": "TELEMETRY", "message_id": "m-1"},
            "routing": {"tenant_id": "customer-B", "device_id": "pc-202"},
            "payload": {"metric_class": "TCP", "value": 0.0, "quality_score": 0.85},
        }

    def test_validate_schema_valid(self):
        self.assertTrue(self.validator.validate_schema(self.valid_payload))

    def test_validate_schema_missing_header(self):
        bad = {"payload": self.valid_payload["payload"]}
        self.assertFalse(self.validator.validate_schema(bad))

    def test_validate_schema_missing_payload_fields(self):
        bad = dict(self.valid_payload)
        bad["payload"] = {"metric_class": "TCP"}  # missing value, quality_score
        self.assertFalse(self.validator.validate_schema(bad))

    def test_validate_tenant_isolation_valid(self):
        self.assertTrue(self.validator.validate_tenant_isolation(self.valid_payload))

    def test_validate_tenant_isolation_missing_tenant(self):
        bad = dict(self.valid_payload)
        bad["routing"] = {"device_id": "pc-1"}  # no tenant_id
        self.assertFalse(self.validator.validate_tenant_isolation(bad))

    def test_validate_tenant_isolation_empty_device_id(self):
        bad = dict(self.valid_payload)
        bad["routing"] = {"tenant_id": "cust-A", "device_id": ""}
        self.assertFalse(self.validator.validate_tenant_isolation(bad))

    def test_validate_checksum_no_checksum_passes(self):
        """No checksum field = optional, should pass."""
        self.assertTrue(self.validator.validate_checksum(self.valid_payload))

    def test_validate_checksum_correct_checksum_passes(self):
        content_str = json.dumps(self.valid_payload["payload"], sort_keys=True)
        checksum = hashlib.sha256(content_str.encode()).hexdigest()
        payload_with_checksum = {**self.valid_payload, "checksum": checksum}
        self.assertTrue(self.validator.validate_checksum(payload_with_checksum))

    def test_validate_checksum_wrong_checksum_fails(self):
        payload_with_bad_checksum = {**self.valid_payload, "checksum": "deadbeef" * 8}
        self.assertFalse(self.validator.validate_checksum(payload_with_bad_checksum))

    def test_validate_quality_range_valid(self):
        self.assertTrue(self.validator.validate_quality_range(self.valid_payload))

    def test_validate_quality_range_out_of_range(self):
        bad = dict(self.valid_payload)
        bad["payload"] = {**self.valid_payload["payload"], "quality_score": 1.5}
        self.assertFalse(self.validator.validate_quality_range(bad))

    def test_validate_quality_range_negative(self):
        bad = dict(self.valid_payload)
        bad["payload"] = {**self.valid_payload["payload"], "quality_score": -0.1}
        self.assertFalse(self.validator.validate_quality_range(bad))

    def test_validate_all_passes_valid_payload(self):
        self.assertTrue(self.validator.validate_all(self.valid_payload))


# ==============================================================================
# 8. Feature Registry Tests
# ==============================================================================
class TestPostgresFeatureRegistry(unittest.TestCase):
    """Tests for PostgresFeatureRegistry (in-memory fallback)."""

    def setUp(self):
        from learning.feature_store.registry.registry_impl import PostgresFeatureRegistry
        self.registry = PostgresFeatureRegistry()
        self.registry._db_available = False  # Force in-memory

    def test_register_feature_metadata(self):
        ok = self.registry.register_feature_metadata({
            "feature_id": "feat-dns-latency",
            "description": "DNS query latency in ms",
            "type": "float",
            "layer": 5,
        })
        self.assertTrue(ok)

    def test_get_feature_metadata_exists(self):
        self.registry.register_feature_metadata({
            "feature_id": "feat-tcp-retransmit",
            "description": "TCP retransmit count",
        })
        meta = self.registry.get_feature_metadata("feat-tcp-retransmit")
        self.assertEqual(meta["feature_id"], "feat-tcp-retransmit")

    def test_get_feature_metadata_not_found(self):
        meta = self.registry.get_feature_metadata("nonexistent-feature")
        self.assertEqual(meta, {})

    def test_cache_hit_after_register(self):
        self.registry.register_feature_metadata({
            "feature_id": "feat-wifi-rssi",
            "description": "WiFi RSSI signal strength",
        })
        # Second get should hit cache
        meta = self.registry.get_feature_metadata("feat-wifi-rssi")
        self.assertIn("feat-wifi-rssi", self.registry._cache)
        self.assertEqual(meta["feature_id"], "feat-wifi-rssi")

    def test_register_requires_feature_id(self):
        ok = self.registry.register_feature_metadata({"description": "No feature_id"})
        self.assertFalse(ok)


# ==============================================================================
# 9. Capability Registry Tests
# ==============================================================================
class TestCapabilityRegistry(unittest.TestCase):
    """Tests for CapabilityRegistry."""

    def setUp(self):
        from learning.registry.registry_impl import CapabilityRegistry
        self.registry = CapabilityRegistry()

    def test_discover_returns_8_capabilities(self):
        manifests = self.registry.discover()
        self.assertEqual(len(manifests), 8)

    def test_discover_populates_internal_manifests(self):
        self.registry.discover()
        self.assertIn("knowledge_store", self.registry._manifests)
        self.assertIn("evaluator", self.registry._manifests)
        self.assertIn("scheduler", self.registry._manifests)
        self.assertIn("audit", self.registry._manifests)
        self.assertIn("metrics", self.registry._manifests)

    def test_validate_valid_manifest(self):
        manifests = self.registry.discover()
        for m in manifests:
            self.assertTrue(self.registry.validate(m))

    def test_check_compatibility_schema_v1(self):
        manifests = self.registry.discover()
        for m in manifests:
            self.assertTrue(self.registry.check_compatibility(m))

    def test_load_evaluator(self):
        self.registry.discover()
        ok = self.registry.load("evaluator")
        self.assertTrue(ok)
        self.assertIsNotNone(self.registry.get("evaluator"))

    def test_load_scheduler(self):
        self.registry.discover()
        ok = self.registry.load("scheduler")
        self.assertTrue(ok)

    def test_load_versioning(self):
        self.registry.discover()
        ok = self.registry.load("versioning")
        self.assertTrue(ok)

    def test_load_metrics(self):
        self.registry.discover()
        ok = self.registry.load("metrics")
        self.assertTrue(ok)

    def test_load_feature_validator(self):
        self.registry.discover()
        ok = self.registry.load("feature_validator")
        self.assertTrue(ok)

    def test_load_feature_registry(self):
        self.registry.discover()
        ok = self.registry.load("feature_registry")
        self.assertTrue(ok)

    def test_activate_loaded_engine(self):
        self.registry.discover()
        self.registry.load("evaluator")
        ok = self.registry.activate("evaluator")
        self.assertTrue(ok)
        self.assertTrue(self.registry._active.get("evaluator"))

    def test_activate_unloaded_engine_fails(self):
        self.registry.discover()
        ok = self.registry.activate("knowledge_store")  # not loaded
        self.assertFalse(ok)

    def test_load_unknown_engine_fails(self):
        ok = self.registry.load("quantum_optimizer")
        self.assertFalse(ok)

    def test_metrics_returns_registry_stats(self):
        self.registry.discover()
        self.registry.load("evaluator")
        self.registry.activate("evaluator")
        stats = self.registry.metrics()
        self.assertEqual(stats["total_registered"], 8)
        self.assertEqual(stats["total_loaded"], 1)
        self.assertEqual(stats["total_active"], 1)

    def test_health_true_when_any_active(self):
        self.registry.discover()
        self.registry.load("evaluator")
        self.registry.activate("evaluator")
        self.assertTrue(self.registry.health())

    def test_health_false_when_none_active(self):
        self.assertFalse(self.registry.health())

    def test_version(self):
        self.assertEqual(self.registry.version(), "1.0.0")

    def test_dependency_status(self):
        self.registry.discover()
        status = self.registry.dependency_status()
        self.assertIn("evaluator", status)
        self.assertIn("scheduler", status)


# ==============================================================================
# Entry Point
# ==============================================================================
if __name__ == "__main__":
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    test_classes = [
        TestPostgresKnowledgeStore,
        TestLLMEvaluationContract,
        TestAsyncIOScheduler,
        TestSemanticVersionController,
        TestLearningAuditLogger,
        TestPrometheusMetricsTracker,
        TestTelemetryFeatureValidator,
        TestPostgresFeatureRegistry,
        TestCapabilityRegistry,
    ]

    for cls in test_classes:
        suite.addTests(loader.loadTestsFromTestCase(cls))

    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    total = result.testsRun
    failed = len(result.failures) + len(result.errors)
    passed = total - failed
    print(f"\n{'='*60}")
    print(f"LF-1 Framework Test Summary: {passed}/{total} PASSED")
    print(f"{'='*60}")
    sys.exit(0 if result.wasSuccessful() else 1)
