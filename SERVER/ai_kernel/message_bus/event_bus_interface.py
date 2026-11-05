"""
AI Kernel - Event Bus Interface (NATS Adapter Wrapper)
Provides event bus interface abstraction without reimplementing NATS logic.
"""
from abc import ABC, abstractmethod
from typing import Callable, Any, Dict
from SERVER.contracts.events import DomainEventContract

class EventBusInterface(ABC):
    """Abstract event bus interface wrapper for NATS/Message Bus."""
    @abstractmethod
    def publish(self, topic: str, event: DomainEventContract) -> bool:
        pass

    @abstractmethod
    def subscribe(self, topic: str, handler: Callable[[DomainEventContract], None]) -> None:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 8.1 (P1-4 Bounded ThreadPoolExecutor)
# ══════════════════════════════════════════════════════════════════════════════
import json
import logging
import threading
import asyncio
from concurrent.futures import ThreadPoolExecutor
from typing import Callable, Any, Dict
from SERVER.shared.db_pool import get_redis

_eblog = logging.getLogger("ai_kernel.event_bus")

class NATSEventBus(EventBusInterface):
    """
    Concrete event bus using Redis pub/sub with bounded ThreadPoolExecutor for listeners.
    Prevents thread explosion under high subscription count.
    """

    def __init__(self, max_listeners: int = 20):
        self._handlers: Dict[str, list] = {}
        self._lock = threading.Lock()
        self._executor = ThreadPoolExecutor(max_workers=max_listeners, thread_name_prefix="evt-bus-sub")
        self._nats_url = __import__("os").getenv("NATS_URL", "nats://localhost:4222")
        self._nats_token = __import__("os").getenv("NATS_TOKEN", "")

    def publish(self, topic: str, event: "DomainEventContract") -> bool:
        payload = json.dumps({
            "event_id":   event.event_id,
            "event_type": event.event_type,
            "timestamp":  event.timestamp,
            "payload":    event.payload,
            "version":    event.version,
        }).encode()

        # Try Redis pub/sub pool
        try:
            rc = get_redis()
            rc.publish(f"evt:{topic}", payload)
            _eblog.info("[EventBus] Published to Redis evt:%s — event_type=%s", topic, event.event_type)
            return True
        except Exception as e:
            _eblog.warning("[EventBus] Redis publish failed: %s", e)

        # Fallback: in-memory delivery to local subscribers
        self._deliver_local(topic, event)
        return True

    def subscribe(self, topic: str, handler: Callable[["DomainEventContract"], None]) -> None:
        with self._lock:
            self._handlers.setdefault(topic, []).append(handler)
        _eblog.info("[EventBus] Subscribed handler to topic: %s", topic)

        # Submit background Redis subscriber to bounded ThreadPoolExecutor
        self._executor.submit(self._redis_listener, topic, handler)

    def _deliver_local(self, topic: str, event: "DomainEventContract") -> None:
        """Deliver event to all in-process subscribers."""
        with self._lock:
            handlers = list(self._handlers.get(topic, []))
        for h in handlers:
            try:
                h(event)
            except Exception as e:
                _eblog.error("[EventBus] Local handler error for topic=%s: %s", topic, e, exc_info=True)

    def _redis_listener(self, topic: str, handler: Callable) -> None:
        """Background Redis pub/sub listener for a single topic."""
        try:
            from SERVER.contracts.events import DomainEventContract
            rc = get_redis()
            ps = rc.pubsub()
            ps.subscribe(f"evt:{topic}")
            _eblog.info("[EventBus] Redis listener started for topic: %s", topic)
            for msg in ps.listen():
                if msg["type"] == "message":
                    try:
                        data = json.loads(msg["data"])
                        event = DomainEventContract(**data)
                        handler(event)
                    except Exception as e:
                        _eblog.error("[EventBus] Handler error for topic=%s: %s", topic, e, exc_info=True)
        except Exception as e:
            _eblog.error("[EventBus] Redis listener failed for topic=%s: %s", topic, e, exc_info=True)

