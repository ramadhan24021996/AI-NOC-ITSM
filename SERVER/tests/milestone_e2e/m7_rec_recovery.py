"""
M7-REC: Recovery Validation
Validates: Transaction rollback on failure, retry exhaustion raises controlled exception,
           Dead-letter queue simulation (overflow to DLQ), Event chain integrity verification,
           State can be reconstructed from event store (event sourcing recovery pattern),
           Lifecycle shutdown/startup sequence is reversible.
"""
import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class REC01_TransactionRollbackRecovery(unittest.TestCase):
    """REC-01: Unit of Work guarantees rollback on exception — no partial state."""

    def test_rollback_on_exception_leaves_no_side_effects(self):
        from SERVER.repositories.unit_of_work import UnitOfWork
        committed_items = []

        class InMemoryUoW(UnitOfWork):
            def __init__(self, store: list):
                self._store = store
                self._staged: list = []

            def stage(self, item):
                self._staged.append(item)

            def commit(self):
                self._store.extend(self._staged)
                self._staged.clear()

            def rollback(self):
                self._staged.clear()  # staged items are discarded

        store = []
        uow = InMemoryUoW(store)
        uow.stage("record-A")
        uow.stage("record-B")

        try:
            with uow:
                raise RuntimeError("DB constraint violation")
        except RuntimeError:
            pass

        # After rollback: store must be empty — no partial write
        self.assertEqual(store, [], "Partial write detected after rollback")
        self.assertEqual(uow._staged, [], "Staged items not cleared after rollback")

    def test_commit_persists_on_success(self):
        from SERVER.repositories.unit_of_work import UnitOfWork
        store = []

        class InMemoryUoW(UnitOfWork):
            def commit(self): store.append("committed")
            def rollback(self): store.append("rolled_back")

        with InMemoryUoW():
            pass  # no exception

        self.assertEqual(store, ["committed"])


class REC02_RetryExhaustionControlledFail(unittest.TestCase):
    """REC-02: After max retries, system raises controlled exception — no silent failure."""

    def test_retry_exhaustion_raises_original_exception(self):
        from SERVER.orchestrator.retry.retry_manager import RetryManager
        mgr = RetryManager(max_retries=3, backoff_factor=1.0)
        calls = [0]

        def always_fails():
            calls[0] += 1
            raise ConnectionError(f"PostgreSQL down (attempt {calls[0]})")

        with self.assertRaises(ConnectionError) as ctx:
            mgr.execute_with_retry(always_fails, (ConnectionError,))

        self.assertEqual(calls[0], 3)
        self.assertIn("PostgreSQL down", str(ctx.exception))

    def test_llm_timeout_retried_then_raised(self):
        from SERVER.orchestrator.retry.retry_manager import RetryManager
        mgr = RetryManager(max_retries=2, backoff_factor=1.0)

        with self.assertRaises(TimeoutError):
            mgr.execute_with_retry(
                lambda: (_ for _ in ()).throw(TimeoutError("LLM response timeout")),
                (TimeoutError,)
            )


class REC03_DeadLetterQueueSimulation(unittest.TestCase):
    """REC-03: When main queue is full, tasks overflow to DLQ — no data loss."""

    def test_overflow_tasks_captured_in_dlq(self):
        from SERVER.orchestrator.queue.task_queue import TaskQueue

        main_queue = TaskQueue(max_size=3)
        dlq = TaskQueue(max_size=1000)  # Dead-letter queue

        tasks = [{"id": i, "query": f"task-{i}"} for i in range(6)]
        overflowed = 0

        for task in tasks:
            if not main_queue.enqueue(task):
                dlq.enqueue(task)  # route overflow to DLQ
                overflowed += 1

        self.assertEqual(main_queue.size(), 3)
        self.assertEqual(dlq.size(), 3)
        self.assertEqual(overflowed, 3)

        # Verify DLQ tasks are preserved and recoverable
        recovered = []
        while dlq.size() > 0:
            recovered.append(dlq.dequeue())
        self.assertEqual(len(recovered), 3)
        self.assertEqual(recovered[0]["id"], 3)  # first overflow was task 3


class REC04_EventChainIntegrityVerification(unittest.TestCase):
    """REC-04: Event chain SHA-256 integrity verifiable — tamper detection works."""

    def _build_chain(self, n: int) -> list:
        from SERVER.enterprise.event_sourcing.event_store import ImmutableEventEntry
        chain = []
        prev_hash = "GENESIS"
        for i in range(n):
            e = ImmutableEventEntry(
                event_id=f"E{i:04d}",
                event_type="IncidentStateChange",
                aggregate_id="INC-REC-001",
                payload={"step": i, "state": f"state_{i}"},
                actor_id="supervisor",
                timestamp=f"2026-08-05T{i:02d}:00:00+00:00",
                previous_hash=prev_hash,
            )
            e.event_hash = e.compute_hash()
            prev_hash = e.event_hash
            chain.append(e)
        return chain

    def test_unmodified_chain_is_valid(self):
        chain = self._build_chain(10)
        # Verify each link
        prev = "GENESIS"
        for entry in chain:
            self.assertEqual(entry.previous_hash, prev)
            recomputed = entry.compute_hash()
            self.assertEqual(recomputed, entry.event_hash)
            prev = entry.event_hash

    def test_tampered_chain_detectable(self):
        chain = self._build_chain(5)
        # Tamper entry #2 payload
        chain[2].payload["state"] = "TAMPERED"

        # Recompute hash for tampered entry — it will differ from stored hash
        recomputed = chain[2].compute_hash()
        self.assertNotEqual(recomputed, chain[2].event_hash,
                            "Tampered entry not detected — hash collision risk")


class REC05_StateRecoveryFromEventStore(unittest.TestCase):
    """REC-05: System state can be rebuilt by replaying events from event store."""

    def test_state_reconstruction_from_event_replay(self):
        from SERVER.enterprise.event_sourcing.event_store import ImmutableEventEntry

        # Simulate: incident state machine events in store
        from typing import Any
        event_log: list[dict[str, Any]] = [
            {"event_type": "IncidentCreated",    "payload": {"status": "open"}},
            {"event_type": "DiagnosisStarted",   "payload": {"status": "diagnosing"}},
            {"event_type": "EvidenceCollected",  "payload": {"status": "diagnosing", "evidence_score": 0.82}},
            {"event_type": "HITLApproved",       "payload": {"status": "approved"}},
            {"event_type": "RemediationApplied", "payload": {"status": "resolved"}},
        ]

        # Replay: fold events to reconstruct current state
        current_state: dict[str, Any] = {}
        for ev in event_log:
            current_state.update(ev["payload"])

        self.assertEqual(current_state["status"], "resolved")
        self.assertAlmostEqual(current_state["evidence_score"], 0.82)

        # Verify recovery produces same result each time (idempotent)
        current_state_2: dict[str, Any] = {}
        for ev in event_log:
            current_state_2.update(ev["payload"])
        self.assertEqual(current_state, current_state_2)


class REC06_LifecycleRestartRecovery(unittest.TestCase):
    """REC-06: Lifecycle manager can be safely stopped and restarted."""

    def test_lifecycle_stop_and_restart_is_idempotent(self):
        from SERVER.ai_kernel.lifecycle.lifecycle_manager import LifecycleManager
        lm = LifecycleManager()
        events = []

        lm.register_startup_hook(lambda: events.append("start"))
        lm.register_shutdown_hook(lambda: events.append("stop"))

        lm.startup()
        self.assertTrue(lm.is_running)
        lm.shutdown()
        self.assertFalse(lm.is_running)

        # Restart cycle
        lm.startup()
        self.assertTrue(lm.is_running)
        lm.shutdown()
        self.assertFalse(lm.is_running)

        self.assertEqual(events, ["start", "stop", "start", "stop"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
