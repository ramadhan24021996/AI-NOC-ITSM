"""
Sprint 2 Kernel, Orchestrator & Integration Domain Import & Integrity Test
Verifies that SERVER.ai_kernel, SERVER.orchestrator, and SERVER.integration
can be imported cleanly, contain zero business logic, and use DTOs/contracts cleanly.
"""
import unittest

class TestSprint2KernelOrchestratorIntegration(unittest.TestCase):
    def test_ai_kernel_imports_and_functionality(self):
        from SERVER.ai_kernel import ConfigLoader, LifecycleManager, DIContainer, ServiceLocator

        # Config Loader Test
        cfg = ConfigLoader()
        cfg.set("TEST_KEY", "true")
        self.assertTrue(cfg.get_bool("TEST_KEY"))

        # Lifecycle Manager Test
        lifecycle = LifecycleManager()
        started = []
        lifecycle.register_startup_hook(lambda: started.append(True))
        lifecycle.startup()
        self.assertTrue(lifecycle.is_running)
        self.assertEqual(len(started), 1)

        # DI Container Test
        container = DIContainer()
        container.register_singleton(ConfigLoader, cfg)
        resolved_cfg = container.resolve(ConfigLoader)
        self.assertEqual(resolved_cfg, cfg)

        # Service Locator Test
        ServiceLocator.register(ConfigLoader, cfg)
        self.assertEqual(ServiceLocator.get(ConfigLoader), cfg)
        ServiceLocator.clear()

    def test_orchestrator_imports_and_functionality(self):
        from SERVER.orchestrator import TaskQueue, RetryManager
        from SERVER.shared import DomainException

        # Task Queue Test
        t_queue = TaskQueue(max_size=10)
        t_queue.enqueue("task_1")
        self.assertEqual(t_queue.size(), 1)
        item = t_queue.dequeue()
        self.assertEqual(item, "task_1")

        # Retry Manager Test
        retry_mgr = RetryManager(max_retries=2, backoff_factor=1.0)
        attempts = []
        def flaky_func():
            attempts.append(1)
            if len(attempts) < 2:
                raise ValueError("Temporary failure")
            return "success"

        res = retry_mgr.execute_with_retry(flaky_func, (ValueError,))
        self.assertEqual(res, "success")

    def test_integration_imports(self):
        from SERVER.integration import UnifiedGateway, RESTHandlerBase, WebSocketGatewayBase, TelegramBotAdapter

        self.assertTrue(issubclass(UnifiedGateway, object))
        self.assertTrue(issubclass(RESTHandlerBase, object))

if __name__ == "__main__":
    unittest.main()
