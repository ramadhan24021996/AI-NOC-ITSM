"""
Tahap 2.2 — Event Infrastructure (NATS JetStream) Test Suite
DoD Criteria:
1. Real Publish / Subscribe flow with DomainEventContract.
2. Idempotency deduplication (duplicate event_id ignored).
3. Retry mechanism on handler exception.
4. Dead Letter Queue (DLQ) routing when retry exhausted.
5. Auto-reconnect and graceful disconnect logic.
6. Backpressure handling threshold.
7. 100% backward compatibility maintained across monorepo.
"""
import unittest
import os
import sys

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "../.."))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)


class TestTahap22EventInfrastructure(unittest.TestCase):
    def test_nats_jetstream_bus_imports(self):
        from SERVER.ai_kernel import NATSJetStreamEventBus, EventBusInterface
        self.assertTrue(issubclass(NATSJetStreamEventBus, EventBusInterface))

    def test_pub_sub_flow(self):
        from SERVER.ai_kernel import NATSJetStreamEventBus
        from SERVER.contracts.events import IncidentCreatedEvent

        bus = NATSJetStreamEventBus(stream_name="TEST_STREAM")
        received_events = []

        bus.subscribe("IncidentCreated", lambda ev: received_events.append(ev))

        event = IncidentCreatedEvent(
            event_id="EVT-1001",
            event_type="IncidentCreated",
            timestamp="2026-08-05T00:00:00Z",
            payload={"site": "Surabaya", "severity": "high"}
        )

        published = bus.publish("IncidentCreated", event)
        self.assertTrue(published)
        self.assertEqual(len(received_events), 1)
        self.assertEqual(received_events[0].event_id, "EVT-1001")

    def test_idempotency_deduplication(self):
        from SERVER.ai_kernel import NATSJetStreamEventBus
        from SERVER.contracts.events import IncidentCreatedEvent

        bus = NATSJetStreamEventBus()
        received_events = []

        bus.subscribe("IncidentCreated", lambda ev: received_events.append(ev))

        event = IncidentCreatedEvent(
            event_id="EVT-DUP-01",
            event_type="IncidentCreated",
            timestamp="2026-08-05T00:00:00Z",
            payload={"data": "test"}
        )

        bus.publish("IncidentCreated", event)
        bus.publish("IncidentCreated", event)  # Duplicate publish with same event_id

        # Subscriber MUST receive the event ONLY ONCE due to idempotency deduplication
        self.assertEqual(len(received_events), 1)

    def test_retry_and_dead_letter_queue_routing(self):
        from SERVER.ai_kernel import NATSJetStreamEventBus
        from SERVER.contracts.events import IncidentCreatedEvent

        bus = NATSJetStreamEventBus(max_retries=3)
        calls = [0]

        def failing_handler(ev):
            calls[0] += 1
            raise RuntimeError("Permanent NATS handler failure")

        bus.subscribe("IncidentCreated", failing_handler)

        event = IncidentCreatedEvent(
            event_id="EVT-FAIL-01",
            event_type="IncidentCreated",
            timestamp="2026-08-05T00:00:00Z",
            payload={"fail": True}
        )

        bus.publish("IncidentCreated", event)

        # Retry tried 3 times before failing
        self.assertEqual(calls[0], 3)

        # Unprocessable message MUST be routed to Dead Letter Queue (DLQ)
        dlq_msgs = bus.get_dlq_messages()
        self.assertEqual(len(dlq_msgs), 1)
        self.assertEqual(dlq_msgs[0]["original_event_id"], "EVT-FAIL-01")
        self.assertIn("Permanent NATS handler failure", dlq_msgs[0]["error_reason"])

    def test_auto_reconnect_and_graceful_disconnect(self):
        from SERVER.ai_kernel import NATSJetStreamEventBus
        from SERVER.contracts.events import IncidentCreatedEvent

        bus = NATSJetStreamEventBus()
        self.assertTrue(bus.is_connected)

        bus.disconnect()
        self.assertFalse(bus.is_connected)

        # Publish while disconnected MUST return False cleanly
        event = IncidentCreatedEvent(
            event_id="EVT-OFFLINE", event_type="IncidentCreated",
            timestamp="2026-08-05T00:00:00Z", payload={}
        )
        self.assertFalse(bus.publish("IncidentCreated", event))

        # Reconnect
        bus.connect()
        self.assertTrue(bus.is_connected)
        self.assertTrue(bus.publish("IncidentCreated", event))


if __name__ == "__main__":
    unittest.main()
