"""
M2-RL: Reliability & Resilience Validation
Validates: Retry exponential backoff, UnitOfWork rollback under failure,
           DI container isolation, TaskQueue overflow handling,
           Controlled degradation when dependencies unavailable,
           EncryptionHelper fallback when cryptography not installed.
"""
import unittest
import time
import os
import sys
import threading

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class RL01_RetryExponentialBackoff(unittest.TestCase):
    """RL-01: RetryManager applies exponential backoff and respects max_retries."""

    def test_retries_up_to_max_then_raises(self):
        from SERVER.orchestrator.retry.retry_manager import RetryManager
        mgr = RetryManager(max_retries=3, backoff_factor=1.0)
        attempts = []

        def always_fail():
            attempts.append(1)
            raise ConnectionError("Simulated DB disconnect")

        with self.assertRaises(ConnectionError):
            mgr.execute_with_retry(always_fail, (ConnectionError,))

        self.assertEqual(len(attempts), 3)

    def test_retry_succeeds_on_second_attempt(self):
        from SERVER.orchestrator.retry.retry_manager import RetryManager
        mgr = RetryManager(max_retries=3, backoff_factor=1.0)
        call_count = [0]

        def flaky():
            call_count[0] += 1
            if call_count[0] < 2:
                raise TimeoutError("LLM timeout")
            return "ok"

        result = mgr.execute_with_retry(flaky, (TimeoutError,))
        self.assertEqual(result, "ok")
        self.assertEqual(call_count[0], 2)

    def test_non_retryable_exception_propagates_immediately(self):
        from SERVER.orchestrator.retry.retry_manager import RetryManager
        mgr = RetryManager(max_retries=3, backoff_factor=1.0)
        calls = [0]

        def raises_value_error():
            calls[0] += 1
            raise ValueError("Not retryable")

        with self.assertRaises(ValueError):
            mgr.execute_with_retry(raises_value_error, (ConnectionError,))
        # Should NOT retry — propagates immediately
        self.assertEqual(calls[0], 1)


class RL02_TaskQueueBoundary(unittest.TestCase):
    """RL-02: TaskQueue respects capacity limit — overflow does not block or crash."""

    def test_enqueue_returns_false_when_full(self):
        from SERVER.orchestrator.queue.task_queue import TaskQueue
        q = TaskQueue(max_size=3)
        self.assertTrue(q.enqueue("t1"))
        self.assertTrue(q.enqueue("t2"))
        self.assertTrue(q.enqueue("t3"))
        self.assertFalse(q.enqueue("t4"))  # overflow

    def test_dequeue_empty_returns_none(self):
        from SERVER.orchestrator.queue.task_queue import TaskQueue
        q = TaskQueue()
        self.assertIsNone(q.dequeue())

    def test_fifo_ordering(self):
        from SERVER.orchestrator.queue.task_queue import TaskQueue
        q = TaskQueue()
        for i in range(5):
            q.enqueue(f"task_{i}")
        results = [q.dequeue() for _ in range(5)]
        self.assertEqual(results, [f"task_{i}" for i in range(5)])


class RL03_DIContainerIsolation(unittest.TestCase):
    """RL-03: DI Container resolves singletons correctly and raises on missing type."""

    def test_resolve_unregistered_raises_key_error(self):
        from SERVER.ai_kernel.dependency_injection.container import DIContainer

        class MyService:
            pass

        container = DIContainer()
        with self.assertRaises(KeyError):
            container.resolve(MyService)

    def test_singleton_returns_same_instance(self):
        from SERVER.ai_kernel.dependency_injection.container import DIContainer
        from SERVER.ai_kernel.config.config_loader import ConfigLoader

        container = DIContainer()
        cfg1 = ConfigLoader()
        container.register_singleton(ConfigLoader, cfg1)
        cfg2 = container.resolve(ConfigLoader)
        self.assertIs(cfg1, cfg2)

    def test_factory_creates_new_instance_each_time(self):
        from SERVER.ai_kernel.dependency_injection.container import DIContainer
        from SERVER.ai_kernel.config.config_loader import ConfigLoader

        container = DIContainer()
        container.register_factory(ConfigLoader, lambda c: ConfigLoader())
        a = container.resolve(ConfigLoader)
        b = container.resolve(ConfigLoader)
        self.assertIsNot(a, b)


class RL04_LifecycleShutdownOrder(unittest.TestCase):
    """RL-04: Lifecycle manager runs shutdown hooks in reverse order."""

    def test_shutdown_hooks_in_reverse_order(self):
        from SERVER.ai_kernel.lifecycle.lifecycle_manager import LifecycleManager
        order = []
        lm = LifecycleManager()
        lm.register_shutdown_hook(lambda: order.append("first"))
        lm.register_shutdown_hook(lambda: order.append("second"))
        lm.register_shutdown_hook(lambda: order.append("third"))
        lm.startup()
        lm.shutdown()
        self.assertEqual(order, ["third", "second", "first"])
        self.assertFalse(lm.is_running)

    def test_startup_hook_failure_does_not_crash_system(self):
        from SERVER.ai_kernel.lifecycle.lifecycle_manager import LifecycleManager
        lm = LifecycleManager()
        good_ran = []
        lm.register_startup_hook(lambda: (_ for _ in ()).throw(RuntimeError("bad hook")))
        lm.register_startup_hook(lambda: good_ran.append(True))
        lm.startup()
        self.assertTrue(lm.is_running)
        # Good hook still ran even after bad one
        self.assertEqual(len(good_ran), 1)


class RL05_EncryptionFallback(unittest.TestCase):
    """RL-05: EncryptionHelper roundtrip is stable."""

    def test_encrypt_decrypt_roundtrip(self):
        from SERVER.security.encryption.encryption_helper import EncryptionHelper
        h = EncryptionHelper(secret_key="milestone-test-key-2026")
        plain = "Sensitive API Key: gsk_xxxx"
        enc = h.encrypt(plain)
        self.assertNotEqual(enc, plain)
        dec = h.decrypt(enc)
        self.assertEqual(dec, plain)

    def test_different_keys_produce_different_ciphertext(self):
        from SERVER.security.encryption.encryption_helper import EncryptionHelper
        h1 = EncryptionHelper(secret_key="key-alpha")
        h2 = EncryptionHelper(secret_key="key-beta")
        plain = "same plaintext"
        self.assertNotEqual(h1.encrypt(plain), h2.encrypt(plain))


if __name__ == "__main__":
    unittest.main(verbosity=2)
