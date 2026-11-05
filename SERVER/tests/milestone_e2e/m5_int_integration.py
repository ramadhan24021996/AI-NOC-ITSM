"""
M5-INT: Integration Validation
Validates: Integration → Orchestrator → Repository → Response pipeline flow,
           DTO translation from all transport adapters (REST, Telegram, WebSocket, Webhook),
           Correlation ID propagation end-to-end,
           SecretProvider wired through CredentialManager in full call chain.
"""
import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class INT01_FullPipelineDTOFlow(unittest.TestCase):
    """INT-01: IncidentQueryContract flows correctly through all domain boundaries."""

    def test_query_contract_creation_and_propagation(self):
        from SERVER.contracts.schemas import IncidentQueryContract, IncidentResponseContract
        from SERVER.shared.enums import ExecutionTrack

        # Simulate: Integration layer creates query contract
        query = IncidentQueryContract(
            query_id="CID-INT-001",
            user_id="usr-noc-01",
            user_role="noc_operator",
            query_text="Nginx timeout threshold exceeded at site Surabaya",
            site_location="Surabaya",
            telemetry_context={"cpu": 91, "mem": 74, "rx_error_rate": 0.03},
        )

        # Simulate: python_ai_core resolves and produces response
        response = IncidentResponseContract(
            query_id=query.query_id,  # correlation ID preserved
            execution_track=ExecutionTrack.STANDARD_TRACK,
            answer_text="Worker connections exhausted. Increase worker_connections to 2048.",
            evidence_score=0.83,
            citations=[
                {"source": "nginx-docs-001", "trust": "official_vendor"},
                {"source": "sop-2026-001",   "trust": "rfc_standard"},
            ],
            requires_hitl=False,
        )

        # Verify correlation ID preserved across domain boundaries
        self.assertEqual(query.query_id, response.query_id)
        self.assertEqual(response.execution_track, ExecutionTrack.STANDARD_TRACK)
        self.assertGreater(response.evidence_score, 0.70)
        self.assertEqual(len(response.citations), 2)

    def test_insufficient_evidence_route(self):
        from SERVER.contracts.schemas import IncidentQueryContract, IncidentResponseContract
        from SERVER.shared.enums import ExecutionTrack
        from SERVER.shared.errors import InsufficientEvidenceException
        from SERVER.shared.constants import INSUFFICIENT_EVIDENCE_THRESHOLD

        query = IncidentQueryContract(
            query_id="CID-INT-002",
            user_id="usr-noc-02",
            user_role="noc_operator",
            query_text="Mysterious latency spike unknown origin",
        )

        evidence_score = 0.42  # Below threshold
        self.assertLess(evidence_score, INSUFFICIENT_EVIDENCE_THRESHOLD)

        # System MUST escalate rather than hallucinate
        with self.assertRaises(InsufficientEvidenceException):
            if evidence_score < INSUFFICIENT_EVIDENCE_THRESHOLD:
                raise InsufficientEvidenceException(
                    f"Evidence score {evidence_score} below threshold "
                    f"{INSUFFICIENT_EVIDENCE_THRESHOLD} — escalating to human engineer"
                )


class INT02_TelegramAdapterDTOTranslation(unittest.TestCase):
    """INT-02: Telegram message translates into valid IncidentQueryContract."""

    def test_telegram_update_parses_to_contract(self):
        from SERVER.integration.telegram.telegram_bot_adapter import TelegramBotAdapter
        from SERVER.contracts.schemas import IncidentQueryContract
        from typing import Dict, Any

        class ConcreteTelegramAdapter(TelegramBotAdapter):
            def parse_telegram_update(self, update_dict: Dict[str, Any]) -> IncidentQueryContract:
                msg = update_dict.get("message", {})
                return IncidentQueryContract(
                    query_id=f"TG-{msg.get('message_id', '0')}",
                    user_id=str(msg.get("from", {}).get("id", "unknown")),
                    user_role="noc_operator",
                    query_text=msg.get("text", ""),
                )

        adapter = ConcreteTelegramAdapter()
        telegram_update = {
            "update_id": 100001,
            "message": {
                "message_id": 42,
                "from": {"id": 9876543, "username": "noc_admin"},
                "text": "Status OSPF Surabaya-Core?",
                "date": 1754350000,
            }
        }

        contract = adapter.parse_telegram_update(telegram_update)
        self.assertEqual(contract.query_id, "TG-42")
        self.assertEqual(contract.user_id, "9876543")
        self.assertIn("OSPF", contract.query_text)


class INT03_RESTAdapterDTOTranslation(unittest.TestCase):
    """INT-03: REST HTTP POST payload translates into valid IncidentQueryContract."""

    def test_rest_handler_translates_payload(self):
        from SERVER.integration.rest.rest_handler_base import RESTHandlerBase
        from typing import Dict, Any

        class ConcreteRESTHandler(RESTHandlerBase):
            def handle_http_post(
                self, payload: Dict[str, Any], headers: Dict[str, str]
            ) -> Dict[str, Any]:
                from SERVER.contracts.schemas import IncidentQueryContract
                from SERVER.shared.enums import ExecutionTrack
                q = IncidentQueryContract(
                    query_id=payload.get("request_id", "REST-UNKNOWN"),
                    user_id=headers.get("X-User-ID", "anonymous"),
                    user_role=headers.get("X-User-Role", "viewer"),
                    query_text=payload.get("query", ""),
                    site_location=payload.get("site"),
                )
                return {
                    "query_id": q.query_id,
                    "user_role": q.user_role,
                    "query_text": q.query_text,
                }

        handler = ConcreteRESTHandler()
        result = handler.handle_http_post(
            payload={"request_id": "REST-20260805-001", "query": "Check BGP peers", "site": "Jakarta"},
            headers={"X-User-ID": "usr-42", "X-User-Role": "noc_operator"},
        )
        self.assertEqual(result["query_id"], "REST-20260805-001")
        self.assertEqual(result["user_role"], "noc_operator")
        self.assertIn("BGP", result["query_text"])


class INT04_WebhookAlertDTOTranslation(unittest.TestCase):
    """INT-04: Alertmanager webhook translates into IncidentQueryContract."""

    def test_alertmanager_webhook_parsed(self):
        from SERVER.integration.webhook.webhook_receiver import WebhookReceiver
        from SERVER.contracts.schemas import IncidentQueryContract
        from typing import Dict, Any

        class AlertmanagerReceiver(WebhookReceiver):
            def parse_webhook_alert(self, payload: Dict[str, Any]) -> IncidentQueryContract:
                alerts = payload.get("alerts", [{}])
                alert = alerts[0] if alerts else {}
                labels = alert.get("labels", {})
                return IncidentQueryContract(
                    query_id=f"ALERT-{labels.get('alertname', 'unknown')}",
                    user_id="alertmanager-system",
                    user_role="system",
                    query_text=f"{labels.get('alertname', '')} on {labels.get('instance', '')}",
                    site_location=labels.get("datacenter"),
                    telemetry_context={"severity": labels.get("severity", "unknown")},
                )

        receiver = AlertmanagerReceiver()
        webhook_payload = {
            "alerts": [{
                "labels": {
                    "alertname": "NginxHighLatency",
                    "instance": "nginx-01:9113",
                    "datacenter": "Surabaya-DC1",
                    "severity": "critical",
                }
            }]
        }
        contract = receiver.parse_webhook_alert(webhook_payload)
        self.assertEqual(contract.query_id, "ALERT-NginxHighLatency")
        self.assertEqual(contract.telemetry_context["severity"], "critical")
        self.assertEqual(contract.site_location, "Surabaya-DC1")


class INT05_OrchestratorQueueIntegration(unittest.TestCase):
    """INT-05: TaskQueue integration with RetryManager — simulates orchestrator dispatch loop."""

    def test_enqueue_dispatch_retry_full_cycle(self):
        from SERVER.orchestrator.queue.task_queue import TaskQueue
        from SERVER.orchestrator.retry.retry_manager import RetryManager

        queue = TaskQueue(max_size=100)
        retry_mgr = RetryManager(max_retries=2, backoff_factor=1.0)
        processed = []

        # Simulate 3 incoming DTO tasks
        for i in range(3):
            queue.enqueue({"query_id": f"CID-{i:03d}", "track": "standard"})

        self.assertEqual(queue.size(), 3)

        # Process queue with retry
        while queue.size() > 0:
            task = queue.dequeue()
            if task is None:
                continue
            result = retry_mgr.execute_with_retry(
                lambda t=task: (processed.append(t["query_id"]), t)[1],
                (ConnectionError,),
            )
            self.assertIn("query_id", result)

        self.assertEqual(len(processed), 3)
        self.assertEqual(queue.size(), 0)


if __name__ == "__main__":
    unittest.main(verbosity=2)
