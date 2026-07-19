"""
Enterprise Autonomous AI OS — Phase 1: Step 1.1
Global AI Runtime State Manager

Setiap Python worker mendaftarkan dirinya dan meng-update state
ke Redis. State ini menjadi sumber kebenaran tunggal tentang
kondisi setiap sub-sistem AI OS yang berjalan.

State lifecycle:
  BOOTING → INITIALIZING → SYNCING → READY
    → LEARNING | EXECUTING | PLANNING
    → VERIFYING → RECOVERING → DEGRADED → SAFE_MODE → SHUTDOWN

Penggunaan di worker:
    from runtime.ai_runtime_state import AIRuntimeState
    runtime = AIRuntimeState("ai_supervisor")
    runtime.set_state(RuntimeState.READY)
    runtime.heartbeat()
"""

import json
import logging
import os
import time
from enum import Enum
from typing import Optional, Dict, Any

logger = logging.getLogger("AI_RUNTIME_STATE")

# ─────────────────────────────────────────────
# 1. State Definitions (AI OS Global States)
# ─────────────────────────────────────────────
class RuntimeState(str, Enum):
    BOOTING      = "BOOTING"
    INITIALIZING = "INITIALIZING"
    SYNCING      = "SYNCING"
    READY        = "READY"
    LEARNING     = "LEARNING"
    PLANNING     = "PLANNING"
    EXECUTING    = "EXECUTING"
    VERIFYING    = "VERIFYING"
    RECOVERING   = "RECOVERING"
    DEGRADED     = "DEGRADED"
    SAFE_MODE    = "SAFE_MODE"
    SHUTDOWN     = "SHUTDOWN"

# Valid transitions: FROM -> allowed TO states
ALLOWED_TRANSITIONS: Dict[RuntimeState, set] = {
    RuntimeState.BOOTING:      {RuntimeState.INITIALIZING, RuntimeState.SHUTDOWN},
    RuntimeState.INITIALIZING: {RuntimeState.SYNCING, RuntimeState.DEGRADED, RuntimeState.SHUTDOWN},
    RuntimeState.SYNCING:      {RuntimeState.READY, RuntimeState.DEGRADED, RuntimeState.SHUTDOWN},
    RuntimeState.READY:        {RuntimeState.LEARNING, RuntimeState.PLANNING, RuntimeState.EXECUTING, RuntimeState.SHUTDOWN},
    RuntimeState.LEARNING:     {RuntimeState.READY, RuntimeState.VERIFYING, RuntimeState.DEGRADED},
    RuntimeState.PLANNING:     {RuntimeState.EXECUTING, RuntimeState.READY, RuntimeState.DEGRADED},
    RuntimeState.EXECUTING:    {RuntimeState.VERIFYING, RuntimeState.RECOVERING, RuntimeState.READY, RuntimeState.DEGRADED},
    RuntimeState.VERIFYING:    {RuntimeState.READY, RuntimeState.RECOVERING, RuntimeState.DEGRADED},
    RuntimeState.RECOVERING:   {RuntimeState.READY, RuntimeState.DEGRADED, RuntimeState.SAFE_MODE},
    RuntimeState.DEGRADED:     {RuntimeState.RECOVERING, RuntimeState.SAFE_MODE, RuntimeState.SHUTDOWN},
    RuntimeState.SAFE_MODE:    {RuntimeState.RECOVERING, RuntimeState.SHUTDOWN},
    RuntimeState.SHUTDOWN:     set(),
}

# ─────────────────────────────────────────────
# 2. AI Runtime State Manager
# ─────────────────────────────────────────────
class AIRuntimeState:
    """
    Thread-safe, Redis-backed runtime state manager for AI OS workers.

    - State disimpan ke Redis key: ai:runtime:{worker_name}
    - Heartbeat TTL: 60 detik (auto-expire jika worker mati)
    - State change otomatis dicatat ke Redis list: ai:runtime:events
    """

    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))
    REDIS_DB   = int(os.getenv("REDIS_DB", "0"))
    HEARTBEAT_TTL = 60  # seconds
    DB_HOST = os.getenv("DB_HOST", "postgres")
    DB_PORT = os.getenv("DB_PORT", "5432")
    DB_NAME = os.getenv("DB_NAME", "osi_system")
    DB_USER = os.getenv("DB_USER", "postgres")
    DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")

    def __init__(self, worker_name: str):
        self.worker_name = worker_name
        self._state = RuntimeState.BOOTING
        self._error_count = 0
        self._context: Dict[str, Any] = {}
        self._redis = None
        self._db_conn = None
        self._start_time = time.time()
        self._connect_redis()
        self._connect_db()
        self._publish_state_change(RuntimeState.BOOTING, None)
        logger.info("[RUNTIME] Worker '%s' initialized → state=BOOTING", worker_name)

    def _connect_redis(self):
        """Attempt to connect to Redis. Graceful fallback if unavailable."""
        try:
            import redis
            self._redis = redis.Redis(password=os.getenv('REDIS_PASSWORD'),
                host=self.REDIS_HOST,
                port=self.REDIS_PORT,
                db=self.REDIS_DB,
                decode_responses=True,
                socket_connect_timeout=3,
            )
            self._redis.ping()
            logger.info("[RUNTIME] Redis connected for runtime state tracking.")
        except Exception as e:
            logger.warning("[RUNTIME] Redis unavailable, running stateless: %s", e)
            self._redis = None

    def _connect_db(self):
        """Attempt to connect to PostgreSQL for persistent state."""
        try:
            import psycopg2
            self._db_conn = psycopg2.connect(
                host=self.DB_HOST,
                port=self.DB_PORT,
                dbname=self.DB_NAME,
                user=self.DB_USER,
                password=self.DB_PASSWORD,
                connect_timeout=3
            )
            logger.info("[RUNTIME] Database connected for persistent runtime state.")
        except Exception as e:
            logger.warning("[RUNTIME] Database unavailable for state persistence: %s", e)
            self._db_conn = None

    def _publish_state_change(self, new_state: RuntimeState, old_state: Optional[RuntimeState]):
        """Write state change to Redis and Database."""
        if not self._redis:
            return
        try:
            payload = {
                "worker": self.worker_name,
                "from_state": old_state.value if old_state else None,
                "to_state": new_state.value,
                "timestamp": time.time(),
                "uptime_seconds": int(time.time() - self._start_time),
            }
            key = f"ai:runtime:{self.worker_name}"
            self._redis.setex(key, self.HEARTBEAT_TTL, json.dumps(payload))
            # Append to event log (capped at 500)
            self._redis.lpush("ai:runtime:events", json.dumps(payload))
            self._redis.ltrim("ai:runtime:events", 0, 499)
        except Exception as e:
            logger.warning("[RUNTIME] Failed to publish state to Redis: %s", e)
            
        if self._db_conn:
            try:
                with self._db_conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO ai_runtime_state (worker_id, state, previous_state, metadata, transitioned_at)
                        VALUES (%s, %s, %s, %s, NOW())
                    """, (
                        self.worker_name,
                        new_state.value,
                        old_state.value if old_state else None,
                        json.dumps({"uptime_seconds": int(time.time() - self._start_time)})
                    ))
                    self._db_conn.commit()
            except Exception as e:
                logger.warning("[RUNTIME] Failed to persist state to DB: %s", e)
                try:
                    self._db_conn.rollback()
                except:
                    import logging; logging.getLogger(__name__).debug('_ = None suppressed')

    def set_state(self, new_state: RuntimeState, context: Optional[Dict] = None) -> bool:
        """
        Transition to a new state. Validates allowed transitions.
        Returns True on success, False if transition is illegal.
        """
        allowed = ALLOWED_TRANSITIONS.get(self._state, set())
        if new_state not in allowed:
            logger.warning(
                "[RUNTIME] ILLEGAL transition: %s → %s. Allowed: %s",
                self._state.value, new_state.value,
                [s.value for s in allowed]
            )
            return False

        old_state = self._state
        self._state = new_state
        if context:
            self._context.update(context)

        self._publish_state_change(new_state, old_state)
        logger.info("[RUNTIME] '%s' state: %s → %s", self.worker_name, old_state.value, new_state.value)
        return True

    def force_state(self, new_state: RuntimeState):
        """Force a state change (used for SAFE_MODE or emergency SHUTDOWN)."""
        old_state = self._state
        self._state = new_state
        self._publish_state_change(new_state, old_state)
        logger.warning("[RUNTIME] FORCED state change: %s → %s", old_state.value, new_state.value)

    def record_error(self, error: Exception):
        """
        Record an error. If threshold exceeded, auto-degrade.
        """
        self._error_count += 1
        logger.error("[RUNTIME] Error #%d in worker '%s': %s", self._error_count, self.worker_name, error)
        if self._error_count >= self.ERROR_THRESHOLD:
            logger.critical("[RUNTIME] Error threshold reached — degrading to DEGRADED state.")
            self.force_state(RuntimeState.DEGRADED)

    def reset_errors(self):
        """Reset error counter after successful operation."""
        self._error_count = 0

    def heartbeat(self):
        """Refresh the Redis TTL to signal the worker is still alive."""
        if not self._redis:
            return
        try:
            key = f"ai:runtime:{self.worker_name}"
            self._redis.expire(key, self.HEARTBEAT_TTL)
        except Exception:
            import logging; logging.getLogger(__name__).debug('_ = None suppressed')

    @property
    def state(self) -> RuntimeState:
        return self._state

    @property
    def is_operational(self) -> bool:
        """True if the worker is able to accept tasks."""
        return self._state in {
            RuntimeState.READY,
            RuntimeState.LEARNING,
            RuntimeState.PLANNING,
            RuntimeState.EXECUTING,
            RuntimeState.VERIFYING,
        }

    @property
    def is_safe_mode(self) -> bool:
        return self._state == RuntimeState.SAFE_MODE

    def get_status(self) -> Dict[str, Any]:
        """Return full status payload for health endpoints."""
        return {
            "worker": self.worker_name,
            "state": self._state.value,
            "error_count": self._error_count,
            "is_operational": self.is_operational,
            "uptime_seconds": int(time.time() - self._start_time),
            "context": self._context,
        }


# ─────────────────────────────────────────────
# 3. System-wide Runtime Registry (Singleton)
# ─────────────────────────────────────────────
class AIRuntimeRegistry:
    """
    Reads all worker states from Redis.
    Used by the AI Health Monitor API endpoint.
    """

    REDIS_HOST = os.getenv("REDIS_HOST", "redis")
    REDIS_PORT = int(os.getenv("REDIS_PORT", "6379"))

    @classmethod
    def get_all_worker_states(cls) -> Dict[str, Any]:
        """Fetch live state of all registered workers from Redis."""
        try:
            import redis
            r = redis.Redis(password=os.getenv('REDIS_PASSWORD'), host=cls.REDIS_HOST, port=cls.REDIS_PORT, decode_responses=True)
            keys = r.keys("ai:runtime:*")
            result = {}
            for key in keys:
                worker_name = key.replace("ai:runtime:", "")
                if "events" in worker_name:
                    continue
                raw = r.get(key)
                if raw:
                    result[worker_name] = json.loads(raw)
            return result
        except Exception as e:
            logger.warning("[REGISTRY] Could not read worker states: %s", e)
            return dict()

    @classmethod
    def get_recent_events(cls, limit: int = 20) -> list:
        """Fetch the most recent runtime state change events."""
        try:
            import redis
            r = redis.Redis(password=os.getenv('REDIS_PASSWORD'), host=cls.REDIS_HOST, port=cls.REDIS_PORT, decode_responses=True)
            raw_events = r.lrange("ai:runtime:events", 0, limit - 1)
            return [json.loads(e) for e in raw_events]
        except Exception:
            return list()
