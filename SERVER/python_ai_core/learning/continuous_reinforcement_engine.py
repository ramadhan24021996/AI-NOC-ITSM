"""
Layer 4 AI Core — Continuous Feedback Reinforcement & Performance Decay Engine (L4_ContinuousFeedbackReinforcement)
Tracks historical remediation performance decay. Applies negative reinforcement penalties if a previously successful
solution experiences > 20% failure rate over the last 10 incidents, forcing alternative plan discovery.
"""

import os
import json
import logging
import time
from typing import Dict, List, Any
import redis

logger = logging.getLogger("CONTINUOUS_REINFORCEMENT")

class ContinuousFeedbackReinforcementEngine:
    def __init__(self, redis_client=None):
        self.redis = redis_client
        if not self.redis:
            try:
                redis_host = os.environ.get("REDIS_HOST", "localhost")
                redis_port = int(os.environ.get("REDIS_PORT", 6379))
                redis_pass = os.environ.get("REDIS_PASSWORD", os.environ.get("OSI_SECURITY_KEY", None))
                self.redis = redis.Redis(host=redis_host, port=redis_port, password=redis_pass, decode_responses=True)
            except Exception as e:
                logger.warning(f"[CONTINUOUS_REINFORCEMENT] Redis connection fallback: {e}")

    def record_remediation_outcome(self, action_name: str, success: bool):
        """Records outcome (success/fail) to a 10-item sliding window in Redis."""
        key = f"action:decay:{action_name.upper()}"
        outcome_val = "PASS" if success else "FAIL"

        if self.redis:
            try:
                self.redis.lpush(key, outcome_val)
                self.redis.ltrim(key, 0, 9) # Keep 10 latest outcomes
                self.redis.expire(key, 2592000) # 30 days TTL
                logger.info(f"[CONTINUOUS_REINFORCEMENT] Recorded outcome '{outcome_val}' for action '{action_name}'.")
            except Exception as e:
                logger.warning(f"[CONTINUOUS_REINFORCEMENT] Failed to record outcome: {e}")

    def evaluate_action_performance_decay(self, action_name: str) -> Dict[str, Any]:
        """
        Evaluates sliding 10-window failure rate.
        If fail_rate > 0.20 (20%) -> Applies Negative Reinforcement Penalty (weight * 0.50).
        """
        key = f"action:decay:{action_name.upper()}"
        outcomes = []

        if self.redis:
            try:
                outcomes = self.redis.lrange(key, 0, 9)
            except Exception as e:
                logger.warning(f"[CONTINUOUS_REINFORCEMENT] Failed to fetch outcomes: {e}")

        if not outcomes:
            return {"action_name": action_name, "fail_rate": 0.0, "penalty_multiplier": 1.0, "status": "STABLE_NO_DECAY"}

        fail_count = sum(1 for o in outcomes if o == "FAIL")
        total = len(outcomes)
        fail_rate = round(fail_count / total, 4)

        has_decay = fail_rate > 0.20
        penalty_multiplier = 0.50 if has_decay else 1.0

        result = {
            "action_name": action_name,
            "window_size": total,
            "fail_count": fail_count,
            "fail_rate": fail_rate,
            "has_performance_decay": has_decay,
            "penalty_multiplier": penalty_multiplier,
            "status": "PERFORMANCE_DECAY_PENALIZED" if has_decay else "HEALTHY_STABLE",
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        if has_decay:
            logger.warning(f"[CONTINUOUS_REINFORCEMENT] PERFORMANCE DECAY DETECTED for '{action_name}' (Fail Rate: {fail_rate*100:.1f}% > 20%). Penalty 0.5x applied!")

        return result

# Global instance
continuous_reinforcement_engine = ContinuousFeedbackReinforcementEngine()
