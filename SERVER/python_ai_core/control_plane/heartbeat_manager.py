"""
Phase 4.0-B Heartbeat Manager & Recovery Controller (control_plane/heartbeat_manager.py)

Manages worker heartbeat registration and crash recovery.
Membantu RecoveryController mendeteksi worker yang terhenti di tengah jalan.
"""

import logging
import time
from typing import Dict, Any, Tuple, Optional

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("HEARTBEAT_MANAGER")


class HeartbeatManager:
    def __init__(self, timeout_seconds: float = 30.0):
        self.timeout_seconds = timeout_seconds
        self.active_workers = {}  # {worker_id: last_heartbeat_timestamp}

    def register_heartbeat(self, worker_id: str):
        self.active_workers[worker_id] = time.time()
        logger.debug(f"[HEARTBEAT] Worker '{worker_id}' registered heartbeat.")

    def is_worker_alive(self, worker_id: str) -> bool:
        if worker_id not in self.active_workers:
            return False
        return (time.time() - self.active_workers[worker_id]) <= self.timeout_seconds
