"""
Enterprise AI OS — Duplicate Log Filter & Global Logging Manager
Suppresses duplicate log line spam across system daemons, services, and AI components.
"""

import time
import logging
from typing import Dict, Tuple, Optional

class DuplicateLogFilter(logging.Filter):
    """
    Suppresses identical log messages repeated within window_sec seconds.
    Tracks recent message hashes to eliminate log duplication.
    """

    def __init__(self, window_sec: float = 3.0):
        super().__init__()
        self.window_sec = window_sec
        self.last_seen: Dict[Tuple[str, str, int], float] = {}

    def filter(self, record: logging.LogRecord) -> bool:
        now = time.monotonic()
        try:
            msg_str = record.getMessage()
        except Exception:
            msg_str = str(record.msg)

        key = (record.name, msg_str, record.levelno)

        if key in self.last_seen:
            last_ts = self.last_seen[key]
            if now - last_ts < self.window_sec:
                return False  # Suppress duplicate message

        self.last_seen[key] = now

        # Prune stale entries if dict grows large
        if len(self.last_seen) > 2000:
            cutoff = now - self.window_sec
            self.last_seen = {k: ts for k, ts in self.last_seen.items() if ts > cutoff}

        return True


def get_deduplicated_logger(name: str, level: int = logging.INFO, window_sec: float = 3.0) -> logging.Logger:
    """
    Returns a logger configured with DuplicateLogFilter to prevent log duplication.
    """
    logger = logging.getLogger(name)
    logger.setLevel(level)

    has_dedup = any(isinstance(f, DuplicateLogFilter) for f in logger.filters)
    if not has_dedup:
        logger.addFilter(DuplicateLogFilter(window_sec=window_sec))

    return logger
