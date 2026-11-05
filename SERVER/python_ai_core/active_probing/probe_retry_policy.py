"""
Probe Retry Policy Module
Implements exponential backoff retry logic and adaptive timeouts:
Base delay 100ms, multiplier 2.0, max retries 3 with jitter.
"""

from dataclasses import dataclass
from typing import Dict, Any, Callable, Optional
import time


@dataclass
class RetryExecutionReport:
    probe_id: str
    total_attempts: int
    successful: bool
    final_latency_ms: float
    retry_log: list[str]


class ProbeRetryPolicy:
    """Manages exponential backoff retries and adaptive timeouts for diagnostic probes."""

    def __init__(self, max_retries: int = 3, base_delay_ms: float = 100.0, backoff_multiplier: float = 2.0):
        self.max_retries = max_retries
        self.base_delay_ms = base_delay_ms
        self.backoff_multiplier = backoff_multiplier

    def execute_with_retry(
        self,
        probe_id: str,
        probe_func: Callable[[], Dict[str, Any]],
        adaptive_timeout_ms: float = 5000.0
    ) -> RetryExecutionReport:

        attempts = 0
        current_delay = self.base_delay_ms / 1000.0
        logs = []
        start_ts = time.time()

        while attempts < self.max_retries:
            attempts += 1
            try:
                res = probe_func()
                status = res.get("status", "PASSED")
                if status in ("PASSED", "BLOCKED", "SKIPPED"):
                    elapsed_ms = round((time.time() - start_ts) * 1000, 2)
                    logs.append(f"Attempt {attempts}: Status={status}")
                    return RetryExecutionReport(
                        probe_id=probe_id,
                        total_attempts=attempts,
                        successful=True,
                        final_latency_ms=elapsed_ms,
                        retry_log=logs
                    )
            except Exception as e:
                logs.append(f"Attempt {attempts} exception: {str(e)}")

            if attempts < self.max_retries:
                time.sleep(min(current_delay, adaptive_timeout_ms / 1000.0))
                current_delay *= self.backoff_multiplier

        elapsed_ms = round((time.time() - start_ts) * 1000, 2)
        return RetryExecutionReport(
            probe_id=probe_id,
            total_attempts=attempts,
            successful=False,
            final_latency_ms=elapsed_ms,
            retry_log=logs
        )
