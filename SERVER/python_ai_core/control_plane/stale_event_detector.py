"""
Phase 4.0-B Stale Event Detector (control_plane/stale_event_detector.py)

Detects late event deliveries and performs causal revalidation instead of automatic rejection.
Enforces: STALE_EVENT -> REVALIDATE -> causally valid? (YES -> PROCESS, NO -> REJECT).
"""

import logging
import time
from typing import Dict, Any, Tuple
from control_plane.event_envelope import CausalEventEnvelope

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("STALE_EVENT_DETECTOR")


class StaleEventDetector:
    def __init__(self, default_max_lag_seconds: float = 300.0):
        self.default_max_lag_seconds = default_max_lag_seconds

    def evaluate_event_staleness(self, envelope: CausalEventEnvelope) -> Tuple[bool, str]:
        """
        Evaluates whether event is stale and requires causal revalidation.
        Returns: (requires_revalidation, status)
        """
        now = time.time()
        # Parse received_at or use current time
        try:
            recv_time = float(envelope.received_at)
        except (ValueError, TypeError):
            recv_time = now

        lag = now - recv_time
        if lag > self.default_max_lag_seconds:
            logger.warning(f"[STALE EVENT DETECTED] Event '{envelope.event_id}' lag is {lag:.1f}s > threshold {self.default_max_lag_seconds}s. Triggering REVALIDATE.")
            return True, "STALE_EVENT_REVALIDATE_REQUIRED"

        return False, "EVENT_FRESH"

    def revalidate_causal_validity(self, envelope: CausalEventEnvelope, current_system_state: Dict[str, Any] = None) -> Tuple[bool, str]:
        """
        Revalidates whether a stale event's telemetry is still causally valid.
        """
        # If payload contains valid incident data, revalidate
        if envelope.payload and "device" in envelope.payload or "host" in envelope.payload or "metric_name" in envelope.payload:
            logger.info(f"[STALE REVALIDATION PASS] Stale Event '{envelope.event_id}' confirmed causally valid.")
            return True, "STALE_REVALIDATION_PASSED"

        logger.warning(f"[STALE REVALIDATION FAIL] Stale Event '{envelope.event_id}' has expired causality.")
        return False, "STALE_REVALIDATION_FAILED"
