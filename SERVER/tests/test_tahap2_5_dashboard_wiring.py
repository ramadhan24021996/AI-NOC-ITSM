"""
Tahap 2.5 — Dashboard AI NOC Wiring Test Suite
================================================
DoD Criteria:
 1. NOCIntegrationGateway dan NOCExecutionCoordinator dapat diimpor tanpa error.
 2. NOCExecutionCoordinator.execute() mengembalikan IncidentResponseContract valid.
 3. ExecutionTrack dipilih berdasarkan severity (CRITICAL → CRITICAL_TRACK).
 4. Correlation IDs (request_id, trace_id) di-auto-generate dan di-propagasi.
 5. EventBus dipanggil sebelum DAN sesudah workflow (observer pattern).
 6. Kegagalan EventBus TIDAK menghentikan workflow (non-fatal observer).
 7. NOCExecutionCoordinator tersedia via DI Container (from_container factory).
 8. NOCIntegrationGateway.handle_request() mengembalikan dict valid.
 9. Jarvis Runtime dapat menggunakan NOCIntegrationGateway sebagai gateway.
10. execute_async() tersedia sebagai native coroutine (tanpa asyncio.run() bridge).
11. Architecture: Jarvis tidak import LLMDispatcher/RAGDispatcher langsung.
12. Coordinator menggunakan DI Container — tidak ada direct instantiation di dalamnya.
13. Fallback response tersedia jika coordinator tidak dikonfigurasi.
14. IncidentQueryContract memiliki 4 Correlation ID fields yang benar.
"""
import unittest
import asyncio
import os
import sys
import inspect

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestTahap25DashboardWiring(unittest.TestCase):

    # ── Test 1: Import Architecture ───────────────────────────────────────────
    def test_all_components_importable(self):
        """NOCIntegrationGateway dan NOCExecutionCoordinator dapat diimpor."""
        from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway
        from SERVER.orchestrator.coordinator.noc_execution_coordinator import NOCExecutionCoordinator
        from SERVER.orchestrator import NOCExecutionCoordinator as PublicExport
        from SERVER.integration import NOCIntegrationGateway as PubGW
        self.assertTrue(callable(NOCExecutionCoordinator))
        self.assertTrue(callable(NOCIntegrationGateway))
        self.assertIs(NOCExecutionCoordinator, PublicExport)
        self.assertIs(NOCIntegrationGateway, PubGW)

    # ── Test 2: IncidentQueryContract Correlation IDs ─────────────────────────
    def test_incident_query_contract_has_correlation_id_fields(self):
        """IncidentQueryContract memiliki 4 Correlation ID fields."""
        from SERVER.contracts.schemas import IncidentQueryContract
        import dataclasses
        fields = {f.name for f in dataclasses.fields(IncidentQueryContract)}
        for field_name in ("request_id", "conversation_id", "trace_id", "session_id"):
            self.assertIn(field_name, fields, f"Missing field: {field_name}")

    # ── Test 3: Coordinator execute() basic ──────────────────────────────────
    def test_coordinator_execute_returns_valid_response(self):
        """NOCExecutionCoordinator.execute() mengembalikan IncidentResponseContract."""
        from SERVER.orchestrator.coordinator.noc_execution_coordinator import NOCExecutionCoordinator
        from SERVER.contracts.schemas import IncidentQueryContract, IncidentResponseContract
        coordinator = NOCExecutionCoordinator()  # no dispatchers = fallback mode
        contract = IncidentQueryContract(
            query_id="Q-TEST-001",
            user_id="test_user",
            user_role="noc_operator",
            query_text="CPU spike di PEKALONGAN-PC-01 mencapai 98%",
        )
        response = coordinator.execute(contract)
        self.assertIsInstance(response, IncidentResponseContract)
        self.assertEqual(response.query_id, "Q-TEST-001")
        self.assertIsInstance(response.answer_text, str)
        self.assertGreater(len(response.answer_text), 0)

    # ── Test 4: ExecutionTrack mapping ────────────────────────────────────────
    def test_coordinator_selects_critical_track_for_critical_severity(self):
        """ExecutionTrack.CRITICAL_TRACK dipilih untuk severity=critical."""
        from SERVER.orchestrator.coordinator.noc_execution_coordinator import NOCExecutionCoordinator
        from SERVER.contracts.schemas import IncidentQueryContract
        from SERVER.shared.enums import ExecutionTrack
        coordinator = NOCExecutionCoordinator()
        contract = IncidentQueryContract(
            query_id="Q-002", user_id="u1", user_role="noc_operator",
            query_text="Network down",
            telemetry_context={"severity": "critical"},
        )
        response = coordinator.execute(contract)
        self.assertEqual(response.execution_track, ExecutionTrack.CRITICAL_TRACK)
        self.assertTrue(response.requires_hitl)

    def test_coordinator_selects_fast_track_for_low_severity(self):
        """ExecutionTrack.FAST_TRACK dipilih untuk severity=low."""
        from SERVER.orchestrator.coordinator.noc_execution_coordinator import NOCExecutionCoordinator
        from SERVER.contracts.schemas import IncidentQueryContract
        from SERVER.shared.enums import ExecutionTrack
        coordinator = NOCExecutionCoordinator()
        contract = IncidentQueryContract(
            query_id="Q-003", user_id="u1", user_role="noc_operator",
            query_text="Minor disk warning",
            telemetry_context={"severity": "low"},
        )
        response = coordinator.execute(contract)
        self.assertEqual(response.execution_track, ExecutionTrack.FAST_TRACK)

    # ── Test 5: Correlation ID auto-generation ────────────────────────────────
    def test_coordinator_auto_generates_correlation_ids(self):
        """Coordinator auto-generate request_id dan trace_id jika kosong."""
        from SERVER.orchestrator.coordinator.noc_execution_coordinator import NOCExecutionCoordinator
        from SERVER.contracts.schemas import IncidentQueryContract
        coordinator = NOCExecutionCoordinator()
        contract = IncidentQueryContract(
            query_id="Q-004", user_id="u1", user_role="noc_operator",
            query_text="Test",
        )
        # Sebelum execute: correlation IDs kosong
        self.assertEqual(contract.request_id, "")
        self.assertEqual(contract.trace_id, "")
        response = coordinator.execute(contract)
        # Setelah execute: harus terisi dan dipropagasi ke response
        self.assertTrue(response.request_id.startswith("REQ-"))
        self.assertTrue(response.trace_id.startswith("TRC-"))

    # ── Test 6: EventBus sebagai observer ─────────────────────────────────────
    def test_eventbus_called_as_observer_before_and_after(self):
        """EventBus dipanggil sebelum dan sesudah workflow (observer pattern)."""
        from SERVER.orchestrator.coordinator.noc_execution_coordinator import NOCExecutionCoordinator
        from SERVER.contracts.schemas import IncidentQueryContract

        published_events = []

        class MockEventBus:
            def publish(self, event_type, payload):
                published_events.append(event_type)

        coordinator = NOCExecutionCoordinator(event_bus=MockEventBus())
        contract = IncidentQueryContract(
            query_id="Q-005", user_id="u1", user_role="noc_operator",
            query_text="Service down",
        )
        coordinator.execute(contract)

        self.assertEqual(len(published_events), 2)
        self.assertIn("noc.incident.analysis.started", published_events[0])
        self.assertIn("noc.incident.analysis.completed", published_events[1])

    def test_eventbus_failure_does_not_stop_workflow(self):
        """Kegagalan EventBus tidak menghentikan workflow utama."""
        from SERVER.orchestrator.coordinator.noc_execution_coordinator import NOCExecutionCoordinator
        from SERVER.contracts.schemas import IncidentQueryContract, IncidentResponseContract

        class BrokenEventBus:
            def publish(self, event_type, payload):
                raise RuntimeError("NATS connection lost")

        coordinator = NOCExecutionCoordinator(event_bus=BrokenEventBus())
        contract = IncidentQueryContract(
            query_id="Q-006", user_id="u1", user_role="noc_operator",
            query_text="Memory leak",
        )
        # Tidak boleh raise exception
        response = coordinator.execute(contract)
        self.assertIsInstance(response, IncidentResponseContract)

    # ── Test 7: DI Container factory ─────────────────────────────────────────
    def test_coordinator_from_di_container(self):
        """NOCExecutionCoordinator.from_container() menggunakan DIContainer."""
        from SERVER.orchestrator.coordinator.noc_execution_coordinator import NOCExecutionCoordinator
        from SERVER.ai_kernel.dependency_injection.container import DIContainer
        from SERVER.orchestrator.dispatcher.llm_dispatcher import LLMDispatcher
        from SERVER.orchestrator.dispatcher.rag_dispatcher import RAGDispatcher

        container = DIContainer()
        container.register_singleton(LLMDispatcher, LLMDispatcher())
        container.register_singleton(RAGDispatcher, RAGDispatcher())

        coordinator = NOCExecutionCoordinator.from_container(container)
        self.assertIsInstance(coordinator, NOCExecutionCoordinator)
        # Dispatcher harus terisi dari container
        self.assertIsNotNone(coordinator._llm)
        self.assertIsNotNone(coordinator._rag)

    # ── Test 8: NOCIntegrationGateway.handle_request() ───────────────────────
    def test_gateway_handle_request_returns_valid_dict(self):
        """NOCIntegrationGateway.handle_request() mengembalikan dict lengkap."""
        from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway
        gateway = NOCIntegrationGateway()  # tanpa coordinator = fallback
        result = gateway.handle_request({
            "query_text": "Cek status interface GigabitEthernet1",
            "user_id": "ops_team",
            "user_role": "noc_operator",
        })
        required_keys = {"query_id", "answer_text", "execution_track", "trace_id", "request_id"}
        for key in required_keys:
            self.assertIn(key, result, f"Missing key: {key}")

    def test_gateway_auto_generates_correlation_ids_in_response(self):
        """Gateway auto-generate trace_id dan request_id jika tidak ada di request."""
        from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway
        gateway = NOCIntegrationGateway()
        result = gateway.handle_request({"query_text": "ping test"})
        self.assertTrue(result.get("trace_id", "").startswith("TRC-"))
        self.assertTrue(result.get("request_id", "").startswith("REQ-"))

    # ── Test 9: Gateway + Coordinator end-to-end ─────────────────────────────
    def test_e2e_gateway_to_coordinator(self):
        """E2E: Gateway → Coordinator → Response tanpa crash."""
        from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway
        from SERVER.orchestrator.coordinator.noc_execution_coordinator import NOCExecutionCoordinator
        coordinator = NOCExecutionCoordinator()
        gateway = NOCIntegrationGateway(coordinator=coordinator)
        result = gateway.handle_request({
            "query_text": "CPU 98% pada PEKALONGAN-PC-01 selama 15 menit.",
            "user_id": "jarvis",
            "user_role": "noc_operator",
            "telemetry_context": {"severity": "high"},
        })
        self.assertIn("answer_text", result)
        self.assertIsInstance(result["answer_text"], str)
        self.assertGreaterEqual(result.get("processing_ms", -1), 0)

    # ── Test 10: execute_async() adalah native coroutine ─────────────────────
    def test_execute_async_is_native_coroutine(self):
        """execute_async() adalah native coroutine, bukan menggunakan asyncio.run()."""
        from SERVER.orchestrator.coordinator.noc_execution_coordinator import NOCExecutionCoordinator
        coordinator = NOCExecutionCoordinator()
        # inspect.iscoroutinefunction() menjamin ini adalah async def
        self.assertTrue(
            inspect.iscoroutinefunction(coordinator.execute_async),
            "execute_async must be declared as `async def`"
        )
        self.assertTrue(
            inspect.iscoroutinefunction(coordinator._retrieve_knowledge_async),
            "_retrieve_knowledge_async must be `async def`"
        )

    def test_execute_async_runs_without_asyncio_run(self):
        """execute_async() dapat dijalankan via asyncio.get_event_loop() tanpa error."""
        from SERVER.orchestrator.coordinator.noc_execution_coordinator import NOCExecutionCoordinator
        from SERVER.contracts.schemas import IncidentQueryContract, IncidentResponseContract
        coordinator = NOCExecutionCoordinator()
        contract = IncidentQueryContract(
            query_id="Q-ASYNC-001", user_id="u1", user_role="noc_operator",
            query_text="Async test",
        )
        # Jalankan dengan asyncio.run() di sini (dalam test context) — bukan di dalam coordinator
        response = asyncio.run(coordinator.execute_async(contract))
        self.assertIsInstance(response, IncidentResponseContract)
        self.assertEqual(response.query_id, "Q-ASYNC-001")

    # ── Test 11: handle_request_async() tersedia di gateway ──────────────────
    def test_gateway_handle_request_async_is_coroutine(self):
        """NOCIntegrationGateway.handle_request_async() adalah native coroutine."""
        from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway
        gateway = NOCIntegrationGateway()
        self.assertTrue(inspect.iscoroutinefunction(gateway.handle_request_async))

    # ── Test 12: Architecture Isolation — Jarvis tidak import dispatcher langsung
    def test_jarvis_does_not_import_dispatchers_directly(self):
        """
        Aturan Arsitektur: SERVER/jarvis TIDAK BOLEH mengimpor LLMDispatcher,
        RAGDispatcher, atau ToolDispatcher langsung. Harus melalui NOCIntegrationGateway.
        """
        import ast
        jarvis_root = os.path.join(PROJECT_ROOT, "SERVER", "jarvis")
        violations = []
        forbidden = ["llm_dispatcher", "rag_dispatcher", "tool_dispatcher", "noc_execution_coordinator"]
        for root, _, files in os.walk(jarvis_root):
            for f in files:
                if not f.endswith(".py"):
                    continue
                fp = os.path.join(root, f)
                with open(fp, encoding="utf-8") as fh:
                    try:
                        tree = ast.parse(fh.read(), filename=fp)
                    except SyntaxError:
                        continue
                for node in ast.walk(tree):
                    if isinstance(node, (ast.Import, ast.ImportFrom)):
                        module = (getattr(node, "module", "") or "").lower()
                        if any(f_name in module for f_name in forbidden):
                            violations.append(f"{fp}: imports {module}")
        self.assertEqual(violations, [], "Architecture violation:\n" + "\n".join(violations))


if __name__ == "__main__":
    unittest.main()
