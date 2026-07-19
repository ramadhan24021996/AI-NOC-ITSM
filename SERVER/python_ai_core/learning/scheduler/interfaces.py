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
