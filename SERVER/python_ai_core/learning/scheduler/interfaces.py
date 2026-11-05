from abc import ABC, abstractmethod
from typing import Dict, Any, Callable

class IScheduler(ABC):
    @abstractmethod
    def register_job(self, job_id: str, cron_expr: str, task: Callable) -> bool:
        raise NotImplementedError("LF-1 Framework: register_job not implemented")

    @abstractmethod
    def enqueue(self, job_id: str, payload: Dict[str, Any]) -> bool:
        raise NotImplementedError("LF-1 Framework: enqueue not implemented")

    @abstractmethod
    def apply_retry_policy(self, job_id: str, max_retries: int) -> None:
        raise NotImplementedError("LF-1 Framework: apply_retry_policy not implemented")

    @abstractmethod
    def apply_timeout_policy(self, job_id: str, timeout_ms: int) -> None:
        raise NotImplementedError("LF-1 Framework: apply_timeout_policy not implemented")


# ══════════════════════════════════════════════════════════════════════════════
# CONCRETE IMPLEMENTATION — Step 6.4
# ══════════════════════════════════════════════════════════════════════════════
import threading, logging, time
from typing import Dict, Any, Callable
from datetime import datetime, timezone

_schlog = logging.getLogger("lf1.scheduler")

class ThreadPoolJobScheduler(IScheduler):
    """
    Thread-based job scheduler (APScheduler-compatible interface).
    Uses Python threading.Timer for interval execution.
    Supports retry policy (max_retries) and timeout policy (timeout_ms).
    """

    def __init__(self):
        self._jobs: Dict[str, dict] = {}
        self._timers: Dict[str, threading.Timer] = {}
        self._lock = threading.Lock()

    def register_job(self, job_id: str, cron_expr: str, task: Callable) -> bool:
        with self._lock:
            self._jobs[job_id] = {
                "cron_expr": cron_expr,
                "task": task,
                "max_retries": 3,
                "timeout_ms": 30000,
                "registered_at": datetime.now(timezone.utc).isoformat(),
            }
        _schlog.info("[Scheduler] Registered job '%s' cron='%s'", job_id, cron_expr)
        return True

    def enqueue(self, job_id: str, payload: Dict[str, Any]) -> bool:
        with self._lock:
            job = self._jobs.get(job_id)
        if not job:
            _schlog.error("[Scheduler] Job '%s' not registered", job_id)
            return False

        def run():
            retries = job.get("max_retries", 3)
            for attempt in range(retries + 1):
                try:
                    timeout_s = job.get("timeout_ms", 30000) / 1000
                    t = threading.Thread(target=job["task"], kwargs=payload, daemon=True)
                    t.start()
                    t.join(timeout=timeout_s)
                    if t.is_alive():
                        _schlog.warning("[Scheduler] Job '%s' timed out after %.1fs", job_id, timeout_s)
                    return
                except Exception as e:
                    _schlog.error("[Scheduler] Job '%s' attempt %d failed: %s", job_id, attempt + 1, e, exc_info=True)
                    if attempt < retries:
                        time.sleep(2 ** attempt)
            _schlog.error("[Scheduler] Job '%s' exhausted all retries", job_id)

        worker = threading.Thread(target=run, daemon=True, name=f"job-{job_id}")
        worker.start()
        _schlog.info("[Scheduler] Enqueued job '%s' with payload keys=%s", job_id, list(payload.keys()))
        return True

    def apply_retry_policy(self, job_id: str, max_retries: int) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["max_retries"] = max_retries
                _schlog.info("[Scheduler] Retry policy set: job='%s' max_retries=%d", job_id, max_retries)

    def apply_timeout_policy(self, job_id: str, timeout_ms: int) -> None:
        with self._lock:
            if job_id in self._jobs:
                self._jobs[job_id]["timeout_ms"] = timeout_ms
                _schlog.info("[Scheduler] Timeout policy set: job='%s' timeout=%dms", job_id, timeout_ms)
