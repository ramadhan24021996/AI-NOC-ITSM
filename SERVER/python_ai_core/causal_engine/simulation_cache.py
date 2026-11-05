"""
Simulation Cache Module
Caches counterfactual simulation results to provide sub-millisecond lookup
during recurring incidents.
"""

from typing import Dict, Any, Optional, Tuple
import hashlib
import json
import time
from .counterfactual import CounterfactualResult


class SimulationCache:
    def __init__(self, ttl_seconds: float = 300.0):
        self.ttl_seconds = ttl_seconds
        # hash_key -> (timestamp, CounterfactualResult)
        self._cache: Dict[str, Tuple[float, CounterfactualResult]] = {}

    def get(self, target_variable: str, real_world_state: Dict[str, Any]) -> Optional[CounterfactualResult]:
        """
        Retrieves cached counterfactual result if present and not expired.
        """
        key = self._generate_key(target_variable, real_world_state)
        now = time.time()

        if key in self._cache:
            ts, result = self._cache[key]
            if now - ts <= self.ttl_seconds:
                return result

        return None

    def put(self, target_variable: str, real_world_state: Dict[str, Any], result: CounterfactualResult):
        """
        Stores counterfactual result into simulation cache.
        """
        key = self._generate_key(target_variable, real_world_state)
        self._cache[key] = (time.time(), result)

    def _generate_key(self, target_variable: str, real_world_state: Dict[str, Any]) -> str:
        state_str = json.dumps(real_world_state, sort_keys=True)
        raw = f"{target_variable}:{state_str}"
        return hashlib.sha256(raw.encode('utf-8')).hexdigest()[:16]

    def clear(self):
        self._cache.clear()
