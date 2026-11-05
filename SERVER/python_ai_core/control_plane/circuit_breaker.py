"""
Phase 4.0-B Circuit Breaker (control_plane/circuit_breaker.py)

Manages Control Plane Circuit Breaker pattern (CLOSED -> OPEN -> HALF_OPEN).
Prevents cascading DB / pipeline overload during failure spikes.
"""

import logging
import time
from typing import Dict, Any, Tuple

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("CIRCUIT_BREAKER")

STATE_CLOSED = "CLOSED"
STATE_OPEN = "OPEN"
STATE_HALF_OPEN = "HALF_OPEN"


class CircuitBreaker:
    def __init__(self, failure_threshold: int = 5, cool_off_seconds: float = 10.0):
        self.failure_threshold = failure_threshold
        self.cool_off_seconds = cool_off_seconds
        self.state = STATE_CLOSED
        self.failure_count = 0
        self.last_state_change = time.time()

    def allow_request(self) -> Tuple[bool, str]:
        """Checks if request is allowed by Circuit Breaker."""
        now = time.time()
        if self.state == STATE_OPEN:
            if now - self.last_state_change > self.cool_off_seconds:
                self.state = STATE_HALF_OPEN
                self.last_state_change = now
                logger.info("[CIRCUIT BREAKER] Transitioned to HALF_OPEN (Trial State)")
                return True, "CIRCUIT_HALF_OPEN_TRIAL"
            else:
                logger.warning(f"[CIRCUIT BREAKER REJECT] Circuit OPEN! Cool-off remaining: {self.cool_off_seconds - (now - self.last_state_change):.1f}s")
                return False, "CIRCUIT_BREAKER_OPEN_REJECTED"

        return True, "CIRCUIT_CLOSED_ALLOWED"

    def record_success(self):
        """Records successful execution."""
        if self.state in [STATE_HALF_OPEN, STATE_OPEN]:
            logger.info("[CIRCUIT BREAKER] Success recorded! Resetting to CLOSED.")
            self.state = STATE_CLOSED
            self.failure_count = 0
            self.last_state_change = time.time()

    def record_failure(self):
        """Records failure and trips circuit if threshold exceeded."""
        self.failure_count += 1
        logger.warning(f"[CIRCUIT BREAKER FAILURE] Count: {self.failure_count}/{self.failure_threshold}")
        if self.failure_count >= self.failure_threshold:
            self.state = STATE_OPEN
            self.last_state_change = time.time()
            logger.error(f"[CIRCUIT BREAKER TRIPPED] Circuit is now OPEN due to {self.failure_count} consecutive failures!")
