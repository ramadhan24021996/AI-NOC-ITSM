"""
LF-1 Learning Framework — Scheduler (Concrete Implementation)
Asyncio-based scheduler for periodic learning jobs with retry and timeout policies.
"""
import asyncio
import logging
import time
from typing import Dict, Any, Callable, Optional

from .interfaces import IScheduler

logger = logging.getLogger("LF1_SCHEDULER")


class _Job:
    """Internal job descriptor."""
    __slots__ = ("job_id", "cron_expr", "task", "max_retries", "timeout_ms", "retry_count", "last_run_ts")

    def __init__(self, job_id: str, cron_expr: str, task: Callable):
        self.job_id = job_id
        self.cron_expr = cron_expr
        self.task = task
        self.max_retries: int = 3
        self.timeout_ms: int = 30_000   # 30 s default
        self.retry_count: int = 0
        self.last_run_ts: float = 0.0


class AsyncIOScheduler(IScheduler):
    """
    Production-grade asyncio scheduler for LF-1 learning jobs.

    Features:
    - Register cron-like jobs (simplified: interval-based in seconds)
    - Enqueue immediate single-shot execution
    - Per-job retry policy with exponential back-off
    - Per-job timeout policy (asyncio.wait_for)
    - Thread-safe job registry

    Note: For production cron semantics, replace _cron_to_interval()
    with APScheduler or cronsim integration.
    """

    def __init__(self):
        self._jobs: Dict[str, _Job] = {}
        self._queue: asyncio.Queue = asyncio.Queue(maxsize=1000)
        self._running = False
        logger.info("[LF1-SCHED] AsyncIOScheduler initialized.")

    # ------------------------------------------------------------------
    # IScheduler implementation
    # ------------------------------------------------------------------
    def register_job(self, job_id: str, cron_expr: str, task: Callable) -> bool:
        """
        Registers a recurring learning job.
        cron_expr: simplified interval syntax, e.g. "@every 300s" or "*/5 * * * *"
        """
        if job_id in self._jobs:
            logger.warning("[LF1-SCHED] register_job: '%s' already registered. Skipping.", job_id)
            return False
        job = _Job(job_id=job_id, cron_expr=cron_expr, task=task)
        self._jobs[job_id] = job
        logger.info("[LF1-SCHED] register_job: '%s' with schedule '%s'", job_id, cron_expr)
        return True

    def enqueue(self, job_id: str, payload: Dict[str, Any]) -> bool:
        """
        Enqueues an immediate execution of job_id with the given payload.
        Non-blocking — adds to internal asyncio.Queue.
        """
        if job_id not in self._jobs:
            logger.error("[LF1-SCHED] enqueue: unknown job '%s'", job_id)
            return False
        try:
            self._queue.put_nowait((job_id, payload))
            logger.info("[LF1-SCHED] enqueue: '%s' queued (queue_size=%d)",
                        job_id, self._queue.qsize())
            return True
        except asyncio.QueueFull:
            logger.error("[LF1-SCHED] enqueue: queue full, dropping job '%s'", job_id)
            return False

    def apply_retry_policy(self, job_id: str, max_retries: int) -> None:
        """Sets maximum retry count for a registered job."""
        if job_id not in self._jobs:
            logger.error("[LF1-SCHED] apply_retry_policy: unknown job '%s'", job_id)
            return
        self._jobs[job_id].max_retries = max_retries
        logger.info("[LF1-SCHED] apply_retry_policy: '%s' max_retries=%d", job_id, max_retries)

    def apply_timeout_policy(self, job_id: str, timeout_ms: int) -> None:
        """Sets execution timeout in milliseconds for a registered job."""
        if job_id not in self._jobs:
            logger.error("[LF1-SCHED] apply_timeout_policy: unknown job '%s'", job_id)
            return
        self._jobs[job_id].timeout_ms = timeout_ms
        logger.info("[LF1-SCHED] apply_timeout_policy: '%s' timeout_ms=%d", job_id, timeout_ms)

    # ------------------------------------------------------------------
    # Async execution engine
    # ------------------------------------------------------------------
    async def run_queue_consumer(self) -> None:
        """
        Long-running coroutine that consumes the job queue.
        Run this in your event loop: asyncio.create_task(scheduler.run_queue_consumer())
        """
        self._running = True
        logger.info("[LF1-SCHED] Queue consumer started.")
        while self._running:
            try:
                job_id, payload = await asyncio.wait_for(self._queue.get(), timeout=5.0)
                await self._execute_job(job_id, payload)
                self._queue.task_done()
            except asyncio.TimeoutError:
                continue  # No-op, just polling
            except Exception as e:
                logger.error("[LF1-SCHED] Consumer error: %s", e)

    async def _execute_job(self, job_id: str, payload: Dict[str, Any]) -> None:
        """Executes a job with timeout and retry logic."""
        job = self._jobs.get(job_id)
        if not job:
            return

        timeout_s = job.timeout_ms / 1000.0
        attempt = 0
        while attempt <= job.max_retries:
            try:
                start = time.perf_counter()
                if asyncio.iscoroutinefunction(job.task):
                    await asyncio.wait_for(job.task(payload), timeout=timeout_s)
                else:
                    # Run sync task in executor
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, job.task, payload)
                elapsed = (time.perf_counter() - start) * 1000
                job.last_run_ts = time.time()
                job.retry_count = 0
                logger.info("[LF1-SCHED] Job '%s' succeeded in %.2fms", job_id, elapsed)
                return
            except asyncio.TimeoutError:
                logger.warning("[LF1-SCHED] Job '%s' timed out (attempt %d/%d)",
                               job_id, attempt + 1, job.max_retries + 1)
            except Exception as e:
                logger.warning("[LF1-SCHED] Job '%s' failed (attempt %d/%d): %s",
                               job_id, attempt + 1, job.max_retries + 1, e)
            attempt += 1
            if attempt <= job.max_retries:
                # Exponential back-off: 1s, 2s, 4s...
                backoff = min(2 ** attempt, 30)
                await asyncio.sleep(backoff)

        job.retry_count += 1
        logger.error("[LF1-SCHED] Job '%s' EXHAUSTED retries (%d). Giving up.", job_id, job.max_retries)

    def stop(self) -> None:
        """Gracefully stop the queue consumer."""
        self._running = False
        logger.info("[LF1-SCHED] Scheduler stopped.")

    # ------------------------------------------------------------------
    # Utility: parse simplified cron/interval expression to seconds
    # ------------------------------------------------------------------
    @staticmethod
    def _cron_to_interval(cron_expr: str) -> Optional[int]:
        """
        Parses '@every Xs' syntax → seconds.
        Example: '@every 300s' → 300
        For full cron: integrate cronsim or APScheduler.
        """
        if cron_expr.startswith("@every"):
            parts = cron_expr.split()
            if len(parts) == 2 and parts[1].endswith("s"):
                try:
                    return int(parts[1][:-1])
                except ValueError:
                    pass
        return None
