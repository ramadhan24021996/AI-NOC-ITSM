import logging
import json
import os
import time
from typing import Any, Dict, List, Optional
import redis

logger = logging.getLogger("SHORT_TERM_MEMORY")

class ShortTermMemoryManager:
    """
    Layer 1: Short-Term Memory Manager
    - RAM / Redis based storage for active conversation context, incident states,
      troubleshooting steps, active device under analysis, and workflow contexts.
    - Enforces TTL (default 3600 seconds).
    - Automatically expires after session completion.
    """

    def __init__(self, default_ttl: int = 3600):
        self.default_ttl = default_ttl
        self.redis_host = os.getenv("REDIS_HOST", "127.0.0.1")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self._redis = None
        self._ram_store: Dict[str, Dict[str, Any]] = {}
        self._connect_redis()

    def _connect_redis(self):
        try:
            r = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                db=0,
                decode_responses=True,
                socket_timeout=2.0
            )
            r.ping()
            self._redis = r
            logger.info(f"[SHORT_TERM_MEMORY] Connected to Redis at {self.redis_host}:{self.redis_port}")
        except Exception as e:
            logger.warning(f"[SHORT_TERM_MEMORY] Redis unavailable ({e}). Fallback to in-memory RAM store.")
            self._redis = None

    def _get_key(self, session_id: str) -> str:
        return f"jarvis:short_term:{session_id}"

    def set_session_context(
        self,
        session_id: str,
        user_id: str = "system_operator",
        active_device: Optional[str] = None,
        incident_id: Optional[int] = None,
        conversation_state: Optional[Dict[str, Any]] = None,
        troubleshooting_steps: Optional[List[Dict[str, Any]]] = None,
        workflow_context: Optional[Dict[str, Any]] = None,
        ttl: Optional[int] = None
    ) -> bool:
        ttl_val = ttl if ttl is not None else self.default_ttl
        key = self._get_key(session_id)
        payload = {
            "session_id": session_id,
            "user_id": user_id,
            "active_device": active_device,
            "incident_id": incident_id,
            "conversation_state": conversation_state or {},
            "troubleshooting_steps": troubleshooting_steps or [],
            "workflow_context": workflow_context or {},
            "updated_at": time.time(),
            "expires_at": time.time() + ttl_val
        }

        if self._redis:
            try:
                self._redis.setex(key, ttl_val, json.dumps(payload))
                return True
            except Exception as e:
                logger.error(f"[SHORT_TERM_MEMORY] Redis set error: {e}")

        self._ram_store[key] = {
            "payload": payload,
            "expires_at": time.time() + ttl_val
        }
        return True

    def get_session_context(self, session_id: str) -> Optional[Dict[str, Any]]:
        key = self._get_key(session_id)
        if self._redis:
            try:
                data = self._redis.get(key)
                if data:
                    return json.loads(data)
            except Exception as e:
                logger.error(f"[SHORT_TERM_MEMORY] Redis get error: {e}")

        if key in self._ram_store:
            entry = self._ram_store[key]
            if time.time() > entry["expires_at"]:
                del self._ram_store[key]
                return None
            return entry["payload"]

        return None

    def add_troubleshooting_step(self, session_id: str, step: Dict[str, Any]) -> bool:
        ctx = self.get_session_context(session_id)
        if not ctx:
            ctx = {"session_id": session_id, "troubleshooting_steps": []}

        steps = ctx.get("troubleshooting_steps", [])
        step["timestamp"] = time.time()
        steps.append(step)
        ctx["troubleshooting_steps"] = steps

        return self.set_session_context(
            session_id=session_id,
            user_id=ctx.get("user_id", "system_operator"),
            active_device=ctx.get("active_device"),
            incident_id=ctx.get("incident_id"),
            conversation_state=ctx.get("conversation_state"),
            troubleshooting_steps=steps,
            workflow_context=ctx.get("workflow_context")
        )

    def set_active_device(self, session_id: str, device_name: str) -> bool:
        ctx = self.get_session_context(session_id) or {"session_id": session_id}
        ctx["active_device"] = device_name
        return self.set_session_context(
            session_id=session_id,
            user_id=ctx.get("user_id", "system_operator"),
            active_device=device_name,
            incident_id=ctx.get("incident_id"),
            conversation_state=ctx.get("conversation_state"),
            troubleshooting_steps=ctx.get("troubleshooting_steps"),
            workflow_context=ctx.get("workflow_context")
        )

    def clear_session(self, session_id: str) -> bool:
        key = self._get_key(session_id)
        if self._redis:
            try:
                self._redis.delete(key)
            except Exception as e:
                logger.error(f"[SHORT_TERM_MEMORY] Redis delete error: {e}")

        if key in self._ram_store:
            del self._ram_store[key]
        return True
