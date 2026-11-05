"""
Probe Circuit Breaker Module
Implements 3-state Circuit Breaker (CLOSED, OPEN, HALF_OPEN) per probe:
Trips to OPEN state after 3 consecutive failures to prevent probe storms or cascading system overload.
"""

from dataclasses import dataclass
from typing import Dict, Any
import time
from enum import Enum


class CircuitState(Enum):
    CLOSED = "CLOSED"        # Normal execution
    OPEN = "OPEN"            # Tripped: Execution blocked
    HALF_OPEN = "HALF_OPEN"  # Testing recovery


@dataclass
class CircuitBreakerStatus:
    probe_id: str
    state: CircuitState
    failure_count: int
    consecutive_failures: int
    last_failure_time: float
    trip_reason: str


class ProbeCircuitBreaker:
    """Manages probe failure thresholds and prevents probe storms using 3-state circuit breakers."""

    def __init__(self, failure_threshold: int = 3, recovery_timeout_sec: float = 30.0):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        # probe_id -> CircuitBreakerStatus
        self.breakers: Dict[str, CircuitBreakerStatus] = {}

    def get_status(self, probe_id: str) -> CircuitBreakerStatus:
        if probe_id not in self.breakers:
            self.breakers[probe_id] = CircuitBreakerStatus(
                probe_id=probe_id,
                state=CircuitState.CLOSED,
                failure_count=0,
                consecutive_failures=0,
                last_failure_time=0.0,
                trip_reason="Normal operating status"
            )
        return self.breakers[probe_id]

    def allow_execution(self, probe_id: str) -> tuple[bool, str]:
        status = self.get_status(probe_id)

        if status.state == CircuitState.CLOSED:
            return True, "CLOSED: Execution permitted"

        if status.state == CircuitState.OPEN:
            elapsed = time.time() - status.last_failure_time
            if elapsed >= self.recovery_timeout_sec:
                status.state = CircuitState.HALF_OPEN
                return True, "HALF_OPEN: Testing recovery execution"
            return False, f"OPEN: Circuit breaker tripped ({status.consecutive_failures} failures); reset in {round(self.recovery_timeout_sec - elapsed, 1)}s"

        if status.state == CircuitState.HALF_OPEN:
            return True, "HALF_OPEN: Single trial execution permitted"

        return True, "Execution permitted"

    def record_outcome(self, probe_id: str, success: bool):
        status = self.get_status(probe_id)

        if success:
            status.consecutive_failures = 0
            status.state = CircuitState.CLOSED
            status.trip_reason = "Normal operating status"
        else:
            status.failure_count += 1
            status.consecutive_failures += 1
            status.last_failure_time = time.time()

            if status.consecutive_failures >= self.failure_threshold:
                status.state = CircuitState.OPEN
                status.trip_reason = f"Tripped: {status.consecutive_failures} consecutive probe failures detected"
