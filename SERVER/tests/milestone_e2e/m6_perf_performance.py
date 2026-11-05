"""
M6-PERF: Performance Validation (Latency Budget Compliance)
Validates: Fast Track <500ms, Standard Track <1500ms, Critical Track <3000ms
           Queue does not grow unbounded, no memory growth on sustained load.

Note: These are micro-benchmarks exercising the domain layer abstractions.
      Full production load benchmarks require infrastructure (PostgreSQL, Redis, LLM).
      This suite validates the domain overhead does NOT itself exceed latency budgets.
"""
import unittest
import time
import gc
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from SERVER.shared.constants import (
    FAST_TRACK_MAX_LATENCY_MS,
    STANDARD_TRACK_MAX_LATENCY_MS,
    CRITICAL_TRACK_MAX_LATENCY_MS,
)


def _timed_ms(func) -> float:
    """Execute func and return wall-clock duration in milliseconds."""
    t0 = time.perf_counter()
    func()
    return (time.perf_counter() - t0) * 1000.0


class PERF01_DomainLayerLatencyBudget(unittest.TestCase):
    """PERF-01: Domain layer contract/DTO operations complete within Fast Track budget."""

    def test_contract_creation_within_fast_track_budget(self):
        from SERVER.contracts.schemas import IncidentQueryContract

        def create_100_contracts():
            for i in range(100):
                IncidentQueryContract(
                    query_id=f"QRY-{i:04d}",
                    user_id="usr-perf",
                    user_role="noc_operator",
                    query_text=f"Performance test query {i}",
                    telemetry_context={"cpu": i % 100},
                )

        elapsed = _timed_ms(create_100_contracts)
        # 100 contract creations must complete well under a single Fast Track budget
        self.assertLess(elapsed, FAST_TRACK_MAX_LATENCY_MS,
                        f"100 contract creations took {elapsed:.1f}ms > "
                        f"{FAST_TRACK_MAX_LATENCY_MS}ms budget")

    def test_evidence_score_computation_within_fast_track_budget(self):
        from SERVER.shared.adapters import compute_composite_evidence_score

        def compute_500_scores():
            for _ in range(500):
                compute_composite_evidence_score(
                    similarity=0.85, coverage=0.80,
                    freshness=0.95, source_trust=1.0, consensus=0.88
                )

        elapsed = _timed_ms(compute_500_scores)
        self.assertLess(elapsed, FAST_TRACK_MAX_LATENCY_MS,
                        f"500 evidence score computations took {elapsed:.1f}ms > "
                        f"{FAST_TRACK_MAX_LATENCY_MS}ms budget")

    def test_event_hash_computation_within_standard_track_budget(self):
        from SERVER.enterprise.event_sourcing.event_store import ImmutableEventEntry

        def hash_200_events():
            prev_hash = "GENESIS"
            for i in range(200):
                entry = ImmutableEventEntry(
                    event_id=f"E{i:05d}",
                    event_type="IncidentCreated",
                    aggregate_id=f"INC-{i:04d}",
                    payload={"severity": "critical", "site": "Surabaya"},
                    actor_id="supervisor-01",
                    timestamp=f"2026-08-05T0{i%10}:00:00+00:00",
                    previous_hash=prev_hash,
                )
                prev_hash = entry.compute_hash()

        elapsed = _timed_ms(hash_200_events)
        self.assertLess(elapsed, STANDARD_TRACK_MAX_LATENCY_MS,
                        f"200 SHA-256 event hashes took {elapsed:.1f}ms > "
                        f"{STANDARD_TRACK_MAX_LATENCY_MS}ms Standard Track budget")


class PERF02_TaskQueueThroughput(unittest.TestCase):
    """PERF-02: TaskQueue enqueue/dequeue does not accumulate backlog under load."""

    def test_queue_drains_fully_under_sustained_load(self):
        from SERVER.orchestrator.queue.task_queue import TaskQueue
        queue = TaskQueue(max_size=10_000)

        # Enqueue 5000 tasks
        TASK_COUNT = 5000
        for i in range(TASK_COUNT):
            queue.enqueue({"id": i})

        self.assertEqual(queue.size(), TASK_COUNT)

        # Drain entirely
        drained = 0
        t0 = time.perf_counter()
        while queue.size() > 0:
            queue.dequeue()
            drained += 1
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertEqual(drained, TASK_COUNT)
        self.assertEqual(queue.size(), 0)
        self.assertLess(elapsed_ms, CRITICAL_TRACK_MAX_LATENCY_MS,
                        f"Draining {TASK_COUNT} queue items took {elapsed_ms:.1f}ms > "
                        f"{CRITICAL_TRACK_MAX_LATENCY_MS}ms Critical Track budget")

    def test_queue_overflow_does_not_block(self):
        """Overflow must return False immediately — never block the caller."""
        from SERVER.orchestrator.queue.task_queue import TaskQueue
        queue = TaskQueue(max_size=5)
        for i in range(5):
            queue.enqueue(i)

        # 6th enqueue must return False within microseconds
        t0 = time.perf_counter()
        result = queue.enqueue("overflow")
        elapsed_ms = (time.perf_counter() - t0) * 1000.0

        self.assertFalse(result)
        self.assertLess(elapsed_ms, 5.0,
                        f"Queue overflow block took {elapsed_ms:.3f}ms — must be non-blocking")


class PERF03_MemoryStability(unittest.TestCase):
    """PERF-03: Repeated domain operations do not accumulate unreclaimed objects."""

    def test_no_object_accumulation_over_repeated_runs(self):
        from SERVER.contracts.schemas import IncidentQueryContract
        from SERVER.shared.adapters import compute_composite_evidence_score

        # Warm-up pass
        for i in range(100):
            q = IncidentQueryContract(
                query_id=f"W-{i}", user_id="u", user_role="r", query_text="warm"
            )
            compute_composite_evidence_score(0.8, 0.7)
        gc.collect()

        objects_before = len(gc.get_objects())

        # Measurement pass
        for i in range(1000):
            q = IncidentQueryContract(
                query_id=f"M-{i}", user_id="u", user_role="r", query_text="measure"
            )
            compute_composite_evidence_score(0.85, 0.75)

        gc.collect()
        objects_after = len(gc.get_objects())

        # Growth should be negligible (< 500 lingering objects after GC)
        growth = objects_after - objects_before
        self.assertLess(growth, 500,
                        f"Object count grew by {growth} after 1000 ops — potential leak")


if __name__ == "__main__":
    unittest.main(verbosity=2)
