"""
supervisor/dispatcher.py
------------------------
AI Supervisor Dispatcher — Safe Engine Execution dengan Error Boundary.

Ini adalah titik paling kritis untuk error isolation:
- Setiap panggilan engine dibungkus dengan safe_dispatch()
- Jika engine X gagal, hanya X yang terdampak
- Supervisor & NATS listener tetap berjalan (graceful degradation)
"""
import asyncio
import logging
from typing import Any, Callable, Optional

logger = logging.getLogger("AI_SUPERVISOR.dispatcher")


# ── Core Error Boundary ───────────────────────────────────────────────────────

async def safe_dispatch(
    engine_func: Callable,
    payload: Any,
    engine_name: str = "",
    fallback_data: Optional[dict] = None,
    timeout_seconds: float = 30.0
) -> dict:
    """
    Pembungkus aman untuk pemanggilan engine AI.

    Jika engine berhasil    → kembalikan hasil asli
    Jika engine timeout     → log WARNING, kembalikan degraded response
    Jika engine exception   → log ERROR, kembalikan degraded response
    TIDAK PERNAH raise exception ke atas (Zero Cascading Failure).

    Args:
        engine_func:      Fungsi async engine yang akan dipanggil
        payload:          Data yang diteruskan ke engine
        engine_name:      Nama engine untuk logging (opsional, default: nama fungsi)
        fallback_data:    Data default jika engine gagal
        timeout_seconds:  Batas waktu sebelum dianggap timeout

    Returns:
        dict: Hasil engine atau degraded response
    """
    name = engine_name or getattr(engine_func, "__name__", "UNKNOWN_ENGINE")

    try:
        result = await asyncio.wait_for(
            engine_func(payload),
            timeout=timeout_seconds
        )
        return result

    except asyncio.TimeoutError:
        logger.warning(
            f"[ENGINE_TIMEOUT] [{name}] Timeout setelah {timeout_seconds}s. "
            f"Returning degraded response."
        )
        return _degraded_response(name, "TimeoutError", fallback_data)

    except Exception as e:
        logger.error(
            f"[ENGINE_ERROR] [{name}] Gagal: {type(e).__name__}: {e}",
            exc_info=True
        )
        return _degraded_response(name, str(e), fallback_data)


def safe_dispatch_sync(
    engine_func: Callable,
    *args,
    engine_name: str = "",
    fallback_data: Optional[dict] = None,
    **kwargs
) -> dict:
    """
    Versi synchronous dari safe_dispatch untuk engine yang bukan async.
    """
    name = engine_name or getattr(engine_func, "__name__", "UNKNOWN_ENGINE")
    try:
        return engine_func(*args, **kwargs)
    except Exception as e:
        logger.error(
            f"[ENGINE_ERROR] [{name}] Gagal (sync): {type(e).__name__}: {e}",
            exc_info=True
        )
        return _degraded_response(name, str(e), fallback_data)


def _degraded_response(engine_name: str, error: str, fallback_data: Optional[dict]) -> dict:
    """Buat response standar saat engine mengalami kegagalan."""
    return {
        "status": "degraded",
        "engine": engine_name,
        "error": error,
        "data": fallback_data or {}
    }


# ── Circuit Breaker Integration ───────────────────────────────────────────────

class EngineCircuitBreaker:
    """
    Circuit Breaker sederhana per engine.
    - CLOSED  : Normal, engine bisa dipanggil
    - OPEN    : Engine terlalu sering gagal, ditangguhkan sementara
    - HALF    : Coba satu kali untuk pemulihan
    """
    _registry: dict = {}

    def __init__(self, engine_name: str, failure_threshold: int = 5, recovery_timeout: float = 60.0):
        self.engine_name = engine_name
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.failure_count = 0
        self.state = "CLOSED"
        self._open_since: Optional[float] = None

    @classmethod
    def get(cls, engine_name: str) -> "EngineCircuitBreaker":
        if engine_name not in cls._registry:
            cls._registry[engine_name] = cls(engine_name)
        return cls._registry[engine_name]

    def record_failure(self):
        import time
        self.failure_count += 1
        if self.failure_count >= self.failure_threshold:
            self.state = "OPEN"
            self._open_since = time.time()
            logger.warning(
                f"[CIRCUIT_BREAKER] [{self.engine_name}] CIRCUIT OPEN — "
                f"engine ditangguhkan selama {self.recovery_timeout}s"
            )

    def record_success(self):
        self.failure_count = 0
        self.state = "CLOSED"
        self._open_since = None

    def is_open(self) -> bool:
        import time
        if self.state == "OPEN":
            elapsed = time.time() - (self._open_since or 0)
            if elapsed > self.recovery_timeout:
                self.state = "HALF"
                logger.info(f"[CIRCUIT_BREAKER] [{self.engine_name}] HALF-OPEN — mencoba pemulihan...")
                return False
            return True
        return False


async def safe_dispatch_with_cb(
    engine_func: Callable,
    payload: Any,
    engine_name: str = "",
    fallback_data: Optional[dict] = None,
    timeout_seconds: float = 30.0
) -> dict:
    """
    safe_dispatch + Circuit Breaker.
    Gunakan ini untuk engine yang digunakan secara intensif (RAG, Critic, Causal).
    """
    name = engine_name or getattr(engine_func, "__name__", "UNKNOWN_ENGINE")
    cb = EngineCircuitBreaker.get(name)

    if cb.is_open():
        logger.warning(f"[CIRCUIT_BREAKER] [{name}] OPEN — melewati eksekusi engine.")
        return _degraded_response(name, "CircuitOpen", fallback_data)

    result = await safe_dispatch(engine_func, payload, engine_name=name,
                                  fallback_data=fallback_data, timeout_seconds=timeout_seconds)

    if result.get("status") == "degraded":
        cb.record_failure()
    else:
        cb.record_success()

    return result
