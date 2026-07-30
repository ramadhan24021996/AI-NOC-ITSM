"""
Layer 4 AI Core — Context Carry-Forward Engine (L4_ContextCarryForward)
Stores the last 5 incidents per device in Redis ('device:history:{pc_name}') with 7-day TTL
and injects carry-forward context to prevent repetitive blind actions.
"""

import os
import json
import logging
import time
from typing import Dict, Any, List, Optional
import redis

logger = logging.getLogger("CONTEXT_CARRY_FORWARD")

class ContextCarryForwardManager:
    def __init__(self, redis_client=None):
        self.redis = redis_client
        if not self.redis:
            try:
                redis_host = os.environ.get("REDIS_HOST", "localhost")
                redis_port = int(os.environ.get("REDIS_PORT", 6379))
                redis_pass = os.environ.get("REDIS_PASSWORD", os.environ.get("OSI_SECURITY_KEY", None))
                self.redis = redis.Redis(host=redis_host, port=redis_port, password=redis_pass, decode_responses=True)
            except Exception as e:
                logger.warning(f"[CONTEXT_CARRY_FORWARD] Redis connection fallback: {e}")

    def record_device_incident(self, pc_name: str, incident_data: Dict[str, Any]):
        """Records incident event to device history ring buffer (max 5 records) in Redis with 7-day TTL."""
        if not pc_name or pc_name == "UNKNOWN_HOST":
            return

        key = f"device:history:{pc_name.upper()}"
        record = {
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "event_type": incident_data.get("event_type", "ANOMALY"),
            "root_cause": incident_data.get("root_cause", "UNKNOWN"),
            "solution_applied": incident_data.get("solution_applied", "PENDING"),
            "status": incident_data.get("status", "RESOLVED")
        }

        if self.redis:
            try:
                self.redis.lpush(key, json.dumps(record))
                self.redis.ltrim(key, 0, 4) # Keep top 5 latest records
                self.redis.expire(key, 604800) # 7 days TTL (604800s)
                logger.info(f"[CONTEXT_CARRY_FORWARD] Recorded incident event for device '{pc_name}'.")
            except Exception as e:
                logger.warning(f"[CONTEXT_CARRY_FORWARD] Redis record failed: {e}")

    def get_device_context(self, pc_name: str) -> Dict[str, Any]:
        """Retrieves and formats last 5 incidents carry-forward summary for a device."""
        if not pc_name or pc_name == "UNKNOWN_HOST":
            return {"history_count": 0, "summary": "No previous device history."}

        key = f"device:history:{pc_name.upper()}"
        history_records = []

        if self.redis:
            try:
                raw_list = self.redis.lrange(key, 0, 4)
                for item in raw_list:
                    history_records.append(json.loads(item))
            except Exception as e:
                logger.warning(f"[CONTEXT_CARRY_FORWARD] Redis read failed: {e}")

        if not history_records:
            return {"history_count": 0, "summary": "First time anomaly or no history recorded in last 7 days."}

        # Format carry-forward text summary
        items_summary = []
        for idx, rec in enumerate(history_records, 1):
            items_summary.append(f"({idx}) {rec.get('timestamp')}: {rec.get('event_type')} -> Root: {rec.get('root_cause')} (Sol: {rec.get('solution_applied')})")

        summary_text = f"Device '{pc_name}' had {len(history_records)} incident(s) in last 7 days: " + " | ".join(items_summary) + ". Consider alternative root cause if recurring."

        return {
            "pc_name": pc_name,
            "history_count": len(history_records),
            "history_records": history_records,
            "summary": summary_text
        }

# Global instance
context_carry_forward_manager = ContextCarryForwardManager()
