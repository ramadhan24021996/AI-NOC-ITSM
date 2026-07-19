import asyncio
import logging
import time
from functools import wraps
from typing import Callable, Any, TypeVar

logger = logging.getLogger("RESILIENCE")

T = TypeVar('T')

class CircuitBreakerError(Exception):
    """Exception raised when the circuit breaker is OPEN."""
    pass

class CircuitBreaker:
    def __init__(self, failure_threshold: int = 3, recovery_timeout_sec: int = 30):
        self.failure_threshold = failure_threshold
        self.recovery_timeout_sec = recovery_timeout_sec
        self.failures = 0
        self.state = "CLOSED"  # CLOSED, OPEN, HALF_OPEN
        self.last_failure_time = 0.0

    def _evaluate_state(self):
        if self.state == "OPEN":
            if time.time() - self.last_failure_time > self.recovery_timeout_sec:
                logger.info(f"[CircuitBreaker] Transitioning from OPEN to HALF_OPEN")
                self.state = "HALF_OPEN"

    def record_success(self):
        if self.state != "CLOSED":
            logger.info(f"[CircuitBreaker] Success recorded. Transitioning to CLOSED")
        self.state = "CLOSED"
        self.failures = 0

    def record_failure(self):
        self.failures += 1
        self.last_failure_time = time.time()
        
        if self.state == "HALF_OPEN":
            logger.warning(f"[CircuitBreaker] Failure in HALF_OPEN. Transitioning back to OPEN")
            self.state = "OPEN"
        elif self.failures >= self.failure_threshold:
            if self.state == "CLOSED":
                logger.error(f"[CircuitBreaker] Failure threshold ({self.failure_threshold}) reached. Transitioning to OPEN")
            self.state = "OPEN"

    def check(self):
        self._evaluate_state()
        if self.state == "OPEN":
            raise CircuitBreakerError(f"Circuit is OPEN. Fast-failing request (failures={self.failures}).")

def with_circuit_breaker(cb: CircuitBreaker):
    """Decorator to apply a shared circuit breaker to an async function."""
    def decorator(func: Callable[..., Any]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            cb.check()
            try:
                result = await func(*args, **kwargs)
                cb.record_success()
                return result
            except Exception as e:
                cb.record_failure()
                raise e
        return wrapper
    return decorator

def retry_with_backoff(max_retries: int = 3, initial_delay: float = 1.0, backoff_factor: float = 2.0, exception_types: tuple = (Exception,)):
    """Decorator for exponential backoff retries on async functions."""
    def decorator(func: Callable[..., Any]):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            delay = initial_delay
            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except exception_types as e:
                    if isinstance(e, CircuitBreakerError):
                        # Do not retry if the circuit is open
                        raise e
                    
                    if attempt == max_retries:
                        logger.error(f"[Retry] Max retries ({max_retries}) reached for {func.__name__}. Error: {e}")
                        raise e
                    
                    logger.warning(f"[Retry] Attempt {attempt + 1} failed for {func.__name__} ({e}). Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    delay *= backoff_factor
        return wrapper
    return decorator
