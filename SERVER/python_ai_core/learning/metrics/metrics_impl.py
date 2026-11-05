"""
LF-1 Learning Framework — Metrics Tracker (Concrete Implementation)
In-memory KPI tracking with Prometheus-compatible exposition format
and optional Redis flush for distributed metric aggregation.
"""
import logging
import os
import time
import json
from collections import defaultdict
from typing import Dict, List

from .interfaces import IMetricsTracker, LearningKPI

logger = logging.getLogger("LF1_METRICS")

_REDIS_HOST  = os.getenv("REDIS_HOST", "127.0.0.1")
_REDIS_PORT  = int(os.getenv("REDIS_PORT", "6379"))
_REDIS_DB    = int(os.getenv("REDIS_METRICS_DB", "1"))
_FLUSH_EVERY = int(os.getenv("LF1_METRICS_FLUSH_EVERY", "100"))  # records


class PrometheusMetricsTracker(IMetricsTracker):
    """
    Thread-safe in-memory KPI tracker for LF-1 Learning Framework.

    Stores:
        _counts:  dict[LearningKPI, int]    — number of observations
        _sums:    dict[LearningKPI, float]  — sum of values
        _history: dict[LearningKPI, list]   — last 500 samples per KPI

    Flush strategy:
        Every _FLUSH_EVERY records, flush aggregated stats to Redis
        (if available) for cross-process aggregation.

    Prometheus exposition:
        Call metrics_tracker.exposition() to get Prometheus text format.
    """

    def __init__(self):
        self._counts:  Dict[LearningKPI, int]         = defaultdict(int)
        self._sums:    Dict[LearningKPI, float]        = defaultdict(float)
        self._mins:    Dict[LearningKPI, float]        = {}
        self._maxs:    Dict[LearningKPI, float]        = {}
        self._history: Dict[LearningKPI, List[float]]  = defaultdict(list)
        self._total_records = 0
        self._redis = self._connect_redis()
        logger.info("[LF1-METRICS] PrometheusMetricsTracker initialized.")

    # ------------------------------------------------------------------
    # IMetricsTracker implementation
    # ------------------------------------------------------------------
    def record(self, kpi: LearningKPI, value: float) -> None:
        """
        Records a KPI observation.
        Thread-safe for single-process async context (GIL protects dicts).
        """
        self._counts[kpi] += 1
        self._sums[kpi]   += value

        if kpi not in self._mins or value < self._mins[kpi]:
            self._mins[kpi] = value
        if kpi not in self._maxs or value > self._maxs[kpi]:
            self._maxs[kpi] = value

        # Keep last 500 samples per KPI
        hist = self._history[kpi]
        hist.append(value)
        if len(hist) > 500:
            hist.pop(0)

        self._total_records += 1
        if self._total_records % _FLUSH_EVERY == 0:
            self._flush_to_redis()

        logger.debug("[LF1-METRICS] record: %s = %.4f (n=%d)",
                     kpi.value, value, self._counts[kpi])

    # ------------------------------------------------------------------
    # Additional utility methods (beyond IMetricsTracker contract)
    # ------------------------------------------------------------------
    def average(self, kpi: LearningKPI) -> float:
        """Returns rolling average for a KPI. Returns 0.0 if no observations."""
        count = self._counts.get(kpi, 0)
        return self._sums[kpi] / count if count > 0 else 0.0

    def summary(self) -> Dict[str, Dict[str, float]]:
        """Returns a dict of {kpi_name: {count, avg, min, max}} for all KPIs."""
        result = {}
        for kpi in LearningKPI:
            count = self._counts.get(kpi, 0)
            result[kpi.value] = {
                "count": count,
                "avg":   round(self._sums[kpi] / count, 6) if count > 0 else 0.0,
                "min":   round(self._mins.get(kpi, 0.0), 6),
                "max":   round(self._maxs.get(kpi, 0.0), 6),
            }
        return result

    def exposition(self) -> str:
        """
        Returns Prometheus text exposition format.
        Can be served on /metrics endpoint.
        """
        lines = []
        lines.append("# HELP lf1_learning_kpi LF-1 Learning Framework KPI Metrics")
        lines.append("# TYPE lf1_learning_kpi gauge")
        for kpi in LearningKPI:
            count = self._counts.get(kpi, 0)
            avg   = self._sums[kpi] / count if count > 0 else 0.0
            lines.append(f'lf1_learning_kpi{{kpi="{kpi.value}",stat="count"}} {count}')
            lines.append(f'lf1_learning_kpi{{kpi="{kpi.value}",stat="avg"}} {avg:.6f}')
            lines.append(f'lf1_learning_kpi{{kpi="{kpi.value}",stat="min"}} {self._mins.get(kpi, 0.0):.6f}')
            lines.append(f'lf1_learning_kpi{{kpi="{kpi.value}",stat="max"}} {self._maxs.get(kpi, 0.0):.6f}')
        return "\n".join(lines)

    def reset(self) -> None:
        """Resets all in-memory metrics (use with caution in production)."""
        self._counts.clear()
        self._sums.clear()
        self._mins.clear()
        self._maxs.clear()
        self._history.clear()
        self._total_records = 0
        logger.warning("[LF1-METRICS] All metrics RESET.")

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------
    def _connect_redis(self):
        try:
            import redis
            r = redis.Redis(host=_REDIS_HOST, port=_REDIS_PORT, db=_REDIS_DB,
                            socket_connect_timeout=2, decode_responses=True)
            r.ping()
            logger.info("[LF1-METRICS] Redis connected at %s:%d db=%d", _REDIS_HOST, _REDIS_PORT, _REDIS_DB)
            return r
        except Exception as e:
            logger.info("[LF1-METRICS] Redis unavailable (%s), using in-memory only.", e)
            return None

    def _flush_to_redis(self) -> None:
        """Flushes aggregated stats to Redis hash for cross-process aggregation."""
        if not self._redis:
            return
        try:
            pipe = self._redis.pipeline()
            ts = int(time.time())
            for kpi in LearningKPI:
                count = self._counts.get(kpi, 0)
                if count == 0:
                    continue
                key = f"lf1:metrics:{kpi.value}:{ts}"
                pipe.hset(key, mapping={
                    "count": count,
                    "sum":   round(self._sums[kpi], 6),
                    "min":   round(self._mins.get(kpi, 0.0), 6),
                    "max":   round(self._maxs.get(kpi, 0.0), 6),
                })
                pipe.expire(key, 86400)  # TTL 24h
            pipe.execute()
            logger.debug("[LF1-METRICS] Flushed %d KPIs to Redis.", len(self._counts))
        except Exception as e:
            logger.warning("[LF1-METRICS] Redis flush failed: %s", e)
