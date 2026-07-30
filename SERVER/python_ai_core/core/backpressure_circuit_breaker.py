"""
BACKPRESSURE & THROTTLING CONCURRENCY CONTROL (ITEM 13)
Protects Python AI Core from Out-Of-Memory (OOM) during Thundering Herd (Mass Reboot Surge):
- ConcurrencySemaphoreManager: Strict worker concurrency limit (Max 10 active AI cycles).
- NATSQueueBackpressureMonitor: When NATS queue > 100 messages, triggers Circuit Breaker to drop non-critical low/med anomalies and prioritize CRITICAL/HIGH incidents first.
"""

import logging
import asyncio
import time
import os
from typing import Dict, List, Any, Optional

logger = logging.getLogger("BACKPRESSURE_CIRCUIT_BREAKER")

class BackpressureCircuitBreaker:
    def __init__(self, max_concurrent_cycles: int = 10, queue_threshold: int = 100):
        self.max_concurrent_cycles = int(os.getenv("AI_MAX_CONCURRENT_CYCLES", str(max_concurrent_cycles)))
        self.queue_threshold = int(os.getenv("NATS_QUEUE_BACKPRESSURE_THRESHOLD", str(queue_threshold)))
        self._semaphore = asyncio.Semaphore(self.max_concurrent_cycles)
        self.active_cycle_count = 0
        self.circuit_breaker_active = False

    def evaluate_backpressure(self, nats_queue_length: int, severity_score: int) -> Dict[str, Any]:
        """
        Evaluates backpressure and decides whether an incoming incident telemetry can enter AI processing.
        """
        self.circuit_breaker_active = nats_queue_length > self.queue_threshold

        decision = {
            "nats_queue_length": nats_queue_length,
            "queue_threshold": self.queue_threshold,
            "circuit_breaker_active": self.circuit_breaker_active,
            "severity_score": severity_score,
            "allow_ai_processing": True,
            "action": "PROCESS_NORMAL",
            "reason": "Queue length within normal capacity limits."
        }

        # Circuit Breaker Active: Queue overloaded (> 100 msgs)
        if self.circuit_breaker_active:
            if severity_score < 60: # Non-Critical Low/Medium anomaly
                decision["allow_ai_processing"] = False
                decision["action"] = "THROTTLE_NON_CRITICAL"
                decision["reason"] = (
                    f"⚠️ BACKPRESSURE ACTIVE (NATS Queue={nats_queue_length} > {self.queue_threshold})! "
                    f"Throttled non-critical anomaly (Severity={severity_score}). Prioritizing CRITICAL incidents."
                )
                logger.warning(decision["reason"])
            else: # CRITICAL or HIGH incident (Severity >= 60)
                decision["allow_ai_processing"] = True
                decision["action"] = "PRIORITY_CRITICAL_BYPASS"
                decision["reason"] = (
                    f"🚨 BACKPRESSURE ACTIVE (NATS Queue={nats_queue_length}), but Severity={severity_score} >= 60. "
                    f"Bypassing throttling for CRITICAL incident!"
                )
                logger.info(decision["reason"])

        return decision

    async def acquire_concurrency_slot(self):
        """Acquires a concurrency slot (Max 10 active cycles). Waits if full."""
        await self._semaphore.acquire()
        self.active_cycle_count += 1
        logger.debug(f"[BACKPRESSURE] Concurrency slot acquired ({self.active_cycle_count}/{self.max_concurrent_cycles})")

    def release_concurrency_slot(self):
        """Releases the concurrency slot."""
        self.active_cycle_count = max(0, self.active_cycle_count - 1)
        self._semaphore.release()
        logger.debug(f"[BACKPRESSURE] Concurrency slot released ({self.active_cycle_count}/{self.max_concurrent_cycles})")


# Demo test run
async def main_demo():
    breaker = BackpressureCircuitBreaker(max_concurrent_cycles=5, queue_threshold=100)
    print("=== UJI BACKPRESSURE & THROTTLING CIRCUIT BREAKER (ITEM 13) ===")

    print("\n1. Skenario Normal (Antrean NATS = 15):")
    res1 = breaker.evaluate_backpressure(nats_queue_length=15, severity_score=45)
    print(f"Allow: {res1['allow_ai_processing']} | Action: {res1['action']} | Reason: {res1['reason']}")

    print("\n2. Skenario Mass Reboot Surge (Antrean NATS = 350, Severity Non-Kritis = 40):")
    res2 = breaker.evaluate_backpressure(nats_queue_length=350, severity_score=40)
    print(f"Allow: {res2['allow_ai_processing']} | Action: {res2['action']} | Reason: {res2['reason']}")

    print("\n3. Skenario Mass Reboot Surge (Antrean NATS = 350, Severity KRITIS = 90):")
    res3 = breaker.evaluate_backpressure(nats_queue_length=350, severity_score=90)
    print(f"Allow: {res3['allow_ai_processing']} | Action: {res3['action']} | Reason: {res3['reason']}")

if __name__ == "__main__":
    asyncio.run(main_demo())
