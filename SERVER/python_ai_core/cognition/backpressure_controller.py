"""
Enterprise AI OS — Anti-Surge Backpressure Controller
Sprint Q: Resilience & Flow Control Layer

Modul ini mengimplementasikan Token Bucket Algorithm untuk mencegah surge
(lonjakan traffic tiba-tiba) yang dapat membebani Python AI Core.
P1 / CRITICAL incidents selalu diproses (bypass throttle).
Stats diterbitkan ke NATS topic 'dashboard.backpressure' setiap 10 detik.

Architecture:
  [NATS Stream] → [BackpressureController] → [AI Processing Pipeline]
                         ↓
               [Adaptive Token Bucket]
               [Priority Bypass (P1)]
               [Circuit Breaker Link]
               [NATS Stats Publisher]
"""

import asyncio
import logging
import time
import json
from collections import deque
from typing import Dict, Any, Optional
from dataclasses import dataclass, field

logger = logging.getLogger("BACKPRESSURE_CTRL")


@dataclass
class TokenBucket:
    """
    Token Bucket implementation untuk rate limiting per channel.
    Tokens diisi ulang dengan rate `refill_rate` per detik.
    Burst capacity mengizinkan lonjakan sementara.
    """
    capacity: int
    refill_rate: float
    tokens: float = field(init=False)
    last_refill: float = field(init=False)

    def __post_init__(self):
        self.tokens = float(self.capacity)
        self.last_refill = time.monotonic()

    def consume(self, amount: int = 1) -> bool:
        """Coba konsumsi `amount` token. Return True jika diizinkan."""
        self._refill()
        if self.tokens >= amount:
            self.tokens -= amount
            return True
        return False

    def _refill(self):
        now = time.monotonic()
        elapsed = now - self.last_refill
        self.tokens = min(self.capacity, self.tokens + elapsed * self.refill_rate)
        self.last_refill = now

    @property
    def fill_ratio(self) -> float:
        self._refill()
        return self.tokens / self.capacity


class AntiSurgeBackpressureController:
    """
    Anti-Surge Backpressure Controller untuk Enterprise AI Core.
    Token Bucket + Priority Bypass + Circuit Breaker + Adaptive Threshold.
    """

    PRIORITY_BYPASS_SUBJECTS = {
        "incident.p1", "incident.critical", "alert.critical",
        "governance.hitl.urgent", "telemetry.spike.critical",
    }

    SUBJECT_BUCKETS = {
        "telemetry.": {"capacity": 200, "refill_rate": 100.0},
        "incident.":  {"capacity": 50,  "refill_rate": 20.0},
        "alert.":     {"capacity": 100, "refill_rate": 50.0},
        "dashboard.": {"capacity": 300, "refill_rate": 150.0},
        "governance.":{"capacity": 30,  "refill_rate": 10.0},
        "default":    {"capacity": 100, "refill_rate": 50.0},
    }

    def __init__(self, nc=None, max_rps: int = 500, burst_capacity: int = 200,
                 adaptive_enabled: bool = True, stats_interval_sec: int = 10):
        self.nc = nc
        self.max_rps = max_rps
        self.burst_capacity = burst_capacity
        self.adaptive_enabled = adaptive_enabled
        self.stats_interval = stats_interval_sec
        self._buckets: Dict[str, TokenBucket] = {}
        self._init_buckets()
        self._stats = {
            "total_allowed": 0, "total_throttled": 0, "total_p1_bypass": 0,
            "current_rps": 0.0, "throttle_ratio": 0.0,
            "adaptive_adjustments": 0, "circuit_breaker_trips": 0,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        }
        self._request_timestamps: deque = deque(maxlen=1000)
        self._queue_depth: int = 0
        self._queue_depth_threshold: int = 500
        self._circuit_open: bool = False
        self._circuit_open_until: float = 0.0
        self._consecutive_drops: int = 0
        self._circuit_trip_threshold: int = 50
        logger.info(
            f"[BACKPRESSURE] Initialized | max_rps={max_rps} | "
            f"burst={burst_capacity} | adaptive={adaptive_enabled}"
        )

    def _init_buckets(self):
        for prefix, cfg in self.SUBJECT_BUCKETS.items():
            self._buckets[prefix] = TokenBucket(
                capacity=cfg["capacity"], refill_rate=cfg["refill_rate"]
            )

    def _get_bucket(self, subject: str) -> TokenBucket:
        for prefix in self.SUBJECT_BUCKETS:
            if prefix != "default" and subject.startswith(prefix):
                return self._buckets[prefix]
        return self._buckets["default"]

    def _is_priority_bypass(self, subject: str, priority: Optional[str] = None) -> bool:
        if priority in ("P1", "CRITICAL", "p1", "critical"):
            return True
        return any(subject.startswith(s) for s in self.PRIORITY_BYPASS_SUBJECTS)

    def _calculate_current_rps(self) -> float:
        now = time.monotonic()
        return float(sum(1 for t in self._request_timestamps if t > now - 1.0))

    def _check_circuit_breaker(self) -> bool:
        if not self._circuit_open:
            return True
        if time.monotonic() > self._circuit_open_until:
            self._circuit_open = False
            self._consecutive_drops = 0
            logger.info("[BACKPRESSURE] Circuit breaker → HALF-OPEN")
            return True
        return False

    def _maybe_open_circuit(self):
        self._consecutive_drops += 1
        if self._consecutive_drops >= self._circuit_trip_threshold:
            self._circuit_open = True
            self._circuit_open_until = time.monotonic() + 30.0
            self._stats["circuit_breaker_trips"] += 1
            logger.warning(
                f"[BACKPRESSURE] ⚡ CIRCUIT BREAKER TRIPPED! "
                f"Blocking 30s. drops={self._consecutive_drops}"
            )

    async def check_and_throttle(
        self, subject: str, priority: Optional[str] = None,
        queue_depth: Optional[int] = None,
    ) -> bool:
        """
        Gate utama backpressure.
        Returns True = ALLOWED, False = THROTTLED (kirim ke dead-letter / retry)
        """
        self._request_timestamps.append(time.monotonic())
        self._stats["current_rps"] = round(self._calculate_current_rps(), 1)
        if queue_depth is not None:
            self._queue_depth = queue_depth

        # 1. Priority Bypass (P1 / CRITICAL)
        if self._is_priority_bypass(subject, priority):
            self._stats["total_p1_bypass"] += 1
            self._stats["total_allowed"] += 1
            self._consecutive_drops = 0
            return True

        # 2. Circuit Breaker
        if not self._check_circuit_breaker():
            self._stats["total_throttled"] += 1
            return False

        # 3. Adaptive multiplier berdasarkan queue depth
        adaptive_multiplier = 1
        if self.adaptive_enabled and self._queue_depth > self._queue_depth_threshold:
            depth_ratio = self._queue_depth / self._queue_depth_threshold
            adaptive_multiplier = max(1, min(3, int(depth_ratio)))
            self._stats["adaptive_adjustments"] += 1

        # 4. Token Bucket
        bucket = self._get_bucket(subject)
        if bucket.consume(adaptive_multiplier):
            self._stats["total_allowed"] += 1
            self._consecutive_drops = 0
            return True
        else:
            self._stats["total_throttled"] += 1
            self._maybe_open_circuit()
            total = self._stats["total_allowed"] + self._stats["total_throttled"]
            self._stats["throttle_ratio"] = round(
                self._stats["total_throttled"] / max(1, total) * 100, 1
            )
            return False

    async def update_queue_depth(self, depth: int):
        self._queue_depth = depth

    async def get_stats(self) -> Dict[str, Any]:
        stats = dict(self._stats)
        stats["queue_depth"] = self._queue_depth
        stats["circuit_breaker_open"] = self._circuit_open
        stats["bucket_fill_ratios"] = {
            prefix: round(bucket.fill_ratio * 100, 1)
            for prefix, bucket in self._buckets.items()
        }
        return stats

    async def _publish_stats_to_nats(self):
        if not self.nc:
            return
        try:
            stats = await self.get_stats()
            stats["timestamp"] = time.strftime("%Y-%m-%dT%H:%M:%S")
            await self.nc.publish("dashboard.backpressure", json.dumps(stats).encode())
        except Exception as e:
            logger.error(f"[BACKPRESSURE] NATS publish failed: {e}")

    async def start_monitor_loop(self):
        """Background monitoring & stats publishing loop."""
        logger.info(f"[BACKPRESSURE] Monitor loop started (interval={self.stats_interval}s)")
        while True:
            await asyncio.sleep(self.stats_interval)
            await self._publish_stats_to_nats()
            stats = await self.get_stats()
            logger.info(
                f"[BACKPRESSURE] 📊 allowed={stats['total_allowed']} | "
                f"throttled={stats['total_throttled']} | "
                f"p1_bypass={stats['total_p1_bypass']} | "
                f"rps={stats['current_rps']} | "
                f"throttle={stats['throttle_ratio']}% | "
                f"circuit={'OPEN ⚡' if stats['circuit_breaker_open'] else 'CLOSED ✅'}"
            )

    def reset_stats(self):
        self._stats.update({
            "total_allowed": 0, "total_throttled": 0, "total_p1_bypass": 0,
            "current_rps": 0.0, "throttle_ratio": 0.0,
            "adaptive_adjustments": 0, "circuit_breaker_trips": 0,
            "started_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        })
        self._consecutive_drops = 0
        self._circuit_open = False


# ── Singleton Factory ──────────────────────────────────────────────────────────
_instance: Optional[AntiSurgeBackpressureController] = None

def get_backpressure_controller(
    nc=None, max_rps: int = 500
) -> AntiSurgeBackpressureController:
    """
    Singleton factory. Gunakan ini di seluruh codebase untuk dapatkan instance yang sama.
    
    from cognition.backpressure_controller import get_backpressure_controller
    ctrl = get_backpressure_controller(nc=nats_conn)
    """
    global _instance
    if _instance is None:
        _instance = AntiSurgeBackpressureController(nc=nc, max_rps=max_rps)
    elif nc is not None and _instance.nc is None:
        _instance.nc = nc
    return _instance
