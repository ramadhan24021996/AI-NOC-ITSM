"""
SERVER.shared.circuit_breaker — Production-Grade Circuit Breaker Pattern
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Prevents cascade failures and thread pile-ups when external services (PostgreSQL, Redis) are down.

States:
  - CLOSED (Normal operations)
  - OPEN (Failing — reject requests immediately with CircuitBreakerOpenException)
  - HALF_OPEN (Testing recovery after cooldown)
"""
import time
import logging
import threading
from typing import Callable, Any, Optional

logger = logging.getLogger("shared.circuit_breaker")

class CircuitBreakerOpenException(Exception):
    """Raised when an operation is attempted while circuit breaker is OPEN."""
    pass

class CircuitBreaker:
    """
    Lightweight, thread-safe Circuit Breaker wrapper.
    """
    def __init__(self, name: str, failure_threshold: int = 5, recovery_timeout: float = 30.0):
        self.name = name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self._failure_count = 0
        self._state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self._last_failure_time = 0.0
        self._lock = threading.Lock()

    @property
    def state(self) -> str:
        with self._lock:
            if self._state == "OPEN":
                if time.time() - self._last_failure_time >= self.recovery_timeout:
                    self._state = "HALF_OPEN"
                    logger.info("[CircuitBreaker:%s] Cooldown period expired. Transitioning to HALF_OPEN", self.name)
            return self._state

    def execute(self, func: Callable, *args, **kwargs) -> Any:
        current_state = self.state
        if current_state == "OPEN":
            raise CircuitBreakerOpenException(f"Circuit breaker '{self.name}' is OPEN. Request rejected.")

        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure()
            raise e

    def _on_success(self):
        with self._lock:
            if self._failure_count > 0 or self._state != "CLOSED":
                logger.info("[CircuitBreaker:%s] Operation succeeded. Circuit reset to CLOSED", self.name)
            self._failure_count = 0
            self._state = "CLOSED"

    def _on_failure(self):
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()
            if self._failure_count >= self.failure_threshold:
                self._state = "OPEN"
                logger.error(
                    "[CircuitBreaker:%s] Consecutive failure count (%d) reached threshold. Circuit OPEN for %.1fs",
                    self.name, self._failure_count, self.recovery_timeout
                )
