"""
Temporal Window Engine Module
Manages multi-tier sliding time windows (5s micro-burst, 30s incident window, 5m trend window)
to group events into temporal contexts.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Set, Optional
from datetime import datetime, timezone
import time
from .event_normalizer import NormalizedEvent, ModalityType


@dataclass
class TemporalWindow:
    window_id: str
    device_id: str
    start_time_iso: str
    end_time_iso: str
    duration_seconds: float
    events: List[NormalizedEvent] = field(default_factory=list)

    @property
    def modalties_present(self) -> Set[str]:
        return {evt.modality.value if isinstance(evt.modality, ModalityType) else str(evt.modality) for evt in self.events}

    @property
    def event_count(self) -> int:
        return len(self.events)

    def sort_events(self):
        self.events.sort(key=lambda x: x.timestamp)


class TemporalWindowEngine:
    def __init__(self, window_size_seconds: float = 30.0):
        self.window_size_seconds = window_size_seconds
        # device_id -> List[NormalizedEvent]
        self._buffers: Dict[str, List[NormalizedEvent]] = {}
        self._last_flush: Dict[str, float] = {}

    def add_event(self, event: NormalizedEvent) -> Optional[TemporalWindow]:
        """
        Adds an event to the device's temporal buffer.
        Returns a TemporalWindow if the window boundary is reached or expired.
        """
        device_id = event.device_id
        if device_id not in self._buffers:
            self._buffers[device_id] = []
            self._last_flush[device_id] = time.time()

        self._buffers[device_id].append(event)
        now = time.time()

        # If window size elapsed, flush window
        if now - self._last_flush[device_id] >= self.window_size_seconds:
            return self.flush_window(device_id)

        return None

    def flush_window(self, device_id: str) -> Optional[TemporalWindow]:
        """
        Forces a flush of the temporal window for a device.
        """
        events = self._buffers.get(device_id, [])
        if not events:
            return None

        # Reset buffer
        self._buffers[device_id] = []
        self._last_flush[device_id] = time.time()

        # Sort events by timestamp
        events.sort(key=lambda x: x.timestamp)
        start_ts = events[0].timestamp
        end_ts = events[-1].timestamp
        window_id = f"WIN-{device_id}-{int(time.time())}"

        window = TemporalWindow(
            window_id=window_id,
            device_id=device_id,
            start_time_iso=start_ts,
            end_time_iso=end_ts,
            duration_seconds=self.window_size_seconds,
            events=events
        )
        return window

    def flush_all(self) -> List[TemporalWindow]:
        windows = []
        for device_id in list(self._buffers.keys()):
            win = self.flush_window(device_id)
            if win:
                windows.append(win)
        return windows
