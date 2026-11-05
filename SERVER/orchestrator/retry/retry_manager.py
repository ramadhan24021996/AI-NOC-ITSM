"""
SERVER.orchestrator - Retry Manager
Manages retry policies for task execution steps.
"""
import time
import logging
from typing import Callable, Any, Type, Tuple

logger = logging.getLogger("orchestrator.retry")

class RetryManager:
    """Manages execution retries with exponential backoff."""
    def __init__(self, max_retries: int = 3, backoff_factor: float = 1.5):
        self.max_retries = max_retries
        self.backoff_factor = backoff_factor

    def execute_with_retry(
        self,
        func: Callable[[], Any],
        retry_exceptions: Tuple[Type[Exception], ...] = (Exception,)
    ) -> Any:
        attempts = 0
        delay = 0.5
        while attempts < self.max_retries:
            try:
                return func()
            except retry_exceptions as e:
                attempts += 1
                if attempts >= self.max_retries:
                    logger.error(f"Task failed after {attempts} attempts: {e}")
                    raise e
                logger.warning(f"Attempt {attempts} failed: {e}. Retrying in {delay}s...")
                time.sleep(delay)
                delay *= self.backoff_factor
