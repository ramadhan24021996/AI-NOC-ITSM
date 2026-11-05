"""
AI Kernel - Task Scheduler Abstraction
Provides job scheduling interface abstraction.
"""
from abc import ABC, abstractmethod
from typing import Callable, Any

class SchedulerInterface(ABC):
    """Abstract scheduler interface."""
    @abstractmethod
    def schedule_interval(self, job_id: str, interval_seconds: int, func: Callable[[], None]) -> None:
        pass

    @abstractmethod
    def cancel_job(self, job_id: str) -> bool:
        pass


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 8.2 (P1-3 Persisted with Redis)
# ══════════════════════════════════════════════════════════════════════════════
import json
import threading
import logging
import time
from typing import Callable, Any, Dict
from datetime import datetime, timezone
from SERVER.shared.db_pool import get_redis

_sklog = logging.getLogger("ai_kernel.scheduler")

class ThreadSchedulerBackend(SchedulerInterface):
    """
    Thread-based task scheduler with Redis state tracking.
    Runs interval jobs in daemon threads with configurable cancellation and Redis persistence.
    """
    REDIS_KEY_PREFIX = "ai_kernel:sched_jobs"

    def __init__(self):
        self._jobs: Dict[str, dict] = {}
        self._stop_events: Dict[str, threading.Event] = {}
        self._lock = threading.Lock()

    def _sync_job_to_redis(self, job_id: str, data: dict):
        try:
            r = get_redis()
            meta = {k: v for k, v in data.items() if k != "func"}
            r.hset(self.REDIS_KEY_PREFIX, job_id, json.dumps(meta, default=str))
        except Exception as e:
            _sklog.warning("[Scheduler] Failed to sync job '%s' to Redis: %s", job_id, e)

    def _remove_job_from_redis(self, job_id: str):
        try:
            r = get_redis()
            r.hdel(self.REDIS_KEY_PREFIX, job_id)
        except Exception as e:
            _sklog.warning("[Scheduler] Failed to remove job '%s' from Redis: %s", job_id, e)

    def schedule_interval(self, job_id: str, interval_seconds: int, func: Callable[[], None]) -> None:
        """Schedule func() to run every interval_seconds in a daemon thread."""
        if job_id in self._stop_events:
            _sklog.warning("[Scheduler] Job '%s' already scheduled. Cancel first to reschedule.", job_id)
            return

        stop_event = threading.Event()
        with self._lock:
            self._stop_events[job_id] = stop_event
            job_info = {
                "job_id": job_id,
                "interval_seconds": interval_seconds,
                "func": func,
                "scheduled_at": datetime.now(timezone.utc).isoformat(),
                "run_count": 0,
            }
            self._jobs[job_id] = job_info
            self._sync_job_to_redis(job_id, job_info)

        def runner():
            _sklog.info("[Scheduler] Job '%s' started — interval=%ds", job_id, interval_seconds)
            while not stop_event.is_set():
                try:
                    func()
                    with self._lock:
                        if job_id in self._jobs:
                            self._jobs[job_id]["run_count"] += 1
                            self._jobs[job_id]["last_run"] = datetime.now(timezone.utc).isoformat()
                            self._sync_job_to_redis(job_id, self._jobs[job_id])
                except Exception as e:
                    _sklog.error("[Scheduler] Job '%s' execution error: %s", job_id, e, exc_info=True)
                stop_event.wait(timeout=interval_seconds)
            _sklog.info("[Scheduler] Job '%s' stopped.", job_id)


        t = threading.Thread(target=runner, daemon=True, name=f"sched-{job_id}")
        t.start()
        _sklog.info("[Scheduler] Scheduled job '%s' every %ds", job_id, interval_seconds)

    def cancel_job(self, job_id: str) -> bool:
        with self._lock:
            stop_event = self._stop_events.pop(job_id, None)
            self._jobs.pop(job_id, None)
            self._remove_job_from_redis(job_id)
        if stop_event:
            stop_event.set()
            _sklog.info("[Scheduler] Cancelled job: %s", job_id)
            return True
        _sklog.warning("[Scheduler] Job '%s' not found for cancellation", job_id)
        return False

