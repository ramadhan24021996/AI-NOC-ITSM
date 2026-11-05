"""
Event Deduplicator Module
Filters and aggregates high-frequency repetitive event bursts within configurable sliding windows.
"""

from typing import Dict, List, Tuple
from datetime import datetime, timezone
import time
from .event_normalizer import NormalizedEvent


class EventDeduplicator:
    def __init__(self, window_seconds: float = 1.5):
        self.window_seconds = window_seconds
        # hash_key -> (last_seen_timestamp_epoch, count, NormalizedEvent)
        self._cache: Dict[str, Tuple[float, int, NormalizedEvent]] = {}

    def is_duplicate(self, event: NormalizedEvent) -> Tuple[bool, int]:
        """
        Checks if the event is a duplicate within the sliding deduplication window.
        Returns (is_duplicate: bool, total_count: int).
        """
        key = event.generate_hash()
        now = time.time()

        if key in self._cache:
            last_ts, count, prev_evt = self._cache[key]
            if now - last_ts <= self.window_seconds:
                # Update cache entry
                new_count = count + 1
                self._cache[key] = (now, new_count, event)
                return True, new_count

        # Clean up stale cache keys if cache exceeds 10,000 items
        if len(self._cache) > 10000:
            self._cleanup(now)

        self._cache[key] = (now, 1, event)
        return False, 1

    def process_batch(self, events: List[NormalizedEvent]) -> List[Tuple[NormalizedEvent, int]]:
        """
        Deduplicates a batch of events and returns unique events with their occurrence counts.
        """
        unique_events: List[Tuple[NormalizedEvent, int]] = []
        for event in events:
            is_dup, count = self.is_duplicate(event)
            if not is_dup:
                unique_events.append((event, count))
        return unique_events

    def _cleanup(self, current_time: float):
        keys_to_remove = [
            k for k, (ts, _, _) in self._cache.items()
            if current_time - ts > self.window_seconds * 2
        ]
        for k in keys_to_remove:
            del self._cache[k]
