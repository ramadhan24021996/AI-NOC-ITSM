"""
Temporal Learning Manager — Production-hardened (pool-backed connections).
"""
import logging
from typing import Dict, Any, List
from datetime import datetime, time

from SERVER.shared.db_pool import PGConnection

_log = logging.getLogger("learning.temporal.manager")


class TemporalLearningManager:
    """Manages temporal learning lifecycle backed by PostgreSQL connection pool."""

    def extract_time_features(self, dt: datetime) -> Dict[str, Any]:
        """Converts a raw timestamp into rich Temporal Features."""
        is_weekend = dt.weekday() >= 5
        hour = dt.hour
        is_business_hour = not is_weekend and (9 <= hour < 17)
        return {
            "timestamp": dt.isoformat(),
            "weekday": dt.strftime("%A"),
            "week_number": dt.isocalendar()[1],
            "month": dt.month,
            "quarter": (dt.month - 1) // 3 + 1,
            "business_hour": is_business_hour,
            "working_day": not is_weekend,
        }

    def register_device(
        self, temporal_id: str, device_id: str, tenant_id: str, tz: str = "UTC"
    ) -> None:
        with PGConnection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO temporal_registry (temporal_id, tenant_id, device_id, timezone)
                    VALUES (%s, %s, %s, %s)
                    ON CONFLICT (temporal_id) DO NOTHING
                """, (temporal_id, tenant_id, device_id, tz))

    def set_calendar(
        self, temporal_id: str, is_working_day: bool, is_holiday: bool,
        bus_start: time, bus_end: time, maint_start: time, maint_end: time,
    ) -> None:
        with PGConnection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO temporal_calendar
                    (temporal_id, is_working_day, is_holiday, business_start_time,
                     business_end_time, maintenance_start_time, maintenance_end_time)
                    VALUES (%s, %s, %s, %s, %s, %s, %s)
                """, (temporal_id, is_working_day, is_holiday, bus_start, bus_end, maint_start, maint_end))
                cur.execute(
                    "INSERT INTO temporal_audit (temporal_id, event, reason) VALUES (%s, %s, %s)",
                    (temporal_id, "CALENDAR_UPDATED", "Device calendar schedule assigned"),
                )

    def set_peak_baseline(
        self, temporal_id: str, peak_start: time, peak_end: time, confidence: float
    ) -> None:
        with PGConnection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO temporal_baseline (temporal_id, peak_start_time, peak_end_time, confidence)
                    VALUES (%s, %s, %s, %s)
                """, (temporal_id, peak_start, peak_end, confidence))
                cur.execute(
                    "INSERT INTO temporal_audit (temporal_id, event, reason) VALUES (%s, %s, %s)",
                    (temporal_id, "BASELINE_UPDATED", f"Peak defined from {peak_start} to {peak_end}"),
                )

    def log_seasonality(
        self, temporal_id: str, pattern_type: str, description: str, confidence: float
    ) -> None:
        with PGConnection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO temporal_patterns (temporal_id, pattern_type, description, confidence)
                    VALUES (%s, %s, %s, %s)
                """, (temporal_id, pattern_type, description, confidence))

    def build_timeline(self, temporal_id: str, events: List[Dict[str, Any]]) -> None:
        """Inserts a sequence of events to form a historical timeline."""
        with PGConnection() as conn:
            with conn.cursor() as cur:
                for idx, evt in enumerate(events):
                    cur.execute("""
                        INSERT INTO temporal_timeline
                        (temporal_id, sequence_order, event_time, event_type, metric_value, context)
                        VALUES (%s, %s, %s, %s, %s, %s)
                    """, (
                        temporal_id, idx + 1,
                        evt["event_time"], evt["event_type"],
                        evt.get("metric_value", 0.0), evt.get("context", ""),
                    ))
                cur.execute(
                    "INSERT INTO temporal_audit (temporal_id, event, reason) VALUES (%s, %s, %s)",
                    (temporal_id, "TIMELINE_BUILT", f"Sequence of {len(events)} events recorded"),
                )
