"""
Phase 3 Governance Framework: AI System Service Level Objectives (SLO) & Error Budget Engine.

Enforces strict operational SLO targets:
1. Availability Target: >= 99.9%
2. Median Latency Target: < 700 ms
3. P95 Latency Target: < 1,500 ms (1.5s)
4. P99 Latency Target: < 3,000 ms (3.0s)
5. Fallback Rate Target: < 5.0%
6. Hallucination Rate Target: < 3.0%
7. Human Review Rate Target: < 10.0%

Tracks Error Budget consumption and triggers automated alerts upon threshold breach.
"""

import logging
import math
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

logger = logging.getLogger("AISloEngine")


@dataclass
class SloTarget:
    availability_pct: float = 99.9
    median_latency_ms: float = 700.0
    p95_latency_ms: float = 1500.0
    p99_latency_ms: float = 3000.0
    max_fallback_rate_pct: float = 5.0
    max_hallucination_rate_pct: float = 3.0
    max_human_review_rate_pct: float = 10.0


@dataclass
class SloStatusReport:
    total_requests: int
    availability_pct: float
    median_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    fallback_rate_pct: float
    hallucination_rate_pct: float
    human_review_rate_pct: float
    error_budget_remaining_pct: float
    slo_met: bool
    breached_slos: List[str] = field(default_factory=list)


class AISloEngine:
    """Enterprise AI Service Level Objectives (SLO) & Error Budget Engine."""

    def __init__(self, target: Optional[SloTarget] = None):
        self.target = target or SloTarget()

    def evaluate_slo(
        self,
        latencies_ms: List[float],
        total_requests: int,
        failed_requests: int,
        fallback_count: int,
        hallucination_count: int,
        human_review_count: int
    ) -> SloStatusReport:
        if total_requests == 0:
            return SloStatusReport(
                total_requests=0,
                availability_pct=100.0,
                median_latency_ms=0.0,
                p95_latency_ms=0.0,
                p99_latency_ms=0.0,
                fallback_rate_pct=0.0,
                hallucination_rate_pct=0.0,
                human_review_rate_pct=0.0,
                error_budget_remaining_pct=100.0,
                slo_met=True
            )

        # 1. Availability
        successful_requests = max(0, total_requests - failed_requests)
        avail_pct = round((successful_requests / total_requests) * 100.0, 3)

        # 2. Latencies
        sorted_lat = sorted(latencies_ms) if latencies_ms else [0.0]
        n = len(sorted_lat)
        median_lat = sorted_lat[int(n * 0.50)] if n > 0 else 0.0
        p95_lat = sorted_lat[min(n - 1, int(n * 0.95))] if n > 0 else 0.0
        p99_lat = sorted_lat[min(n - 1, int(n * 0.99))] if n > 0 else 0.0

        # 3. Rates
        fallback_rate = round((fallback_count / total_requests) * 100.0, 2)
        hallucination_rate = round((hallucination_count / total_requests) * 100.0, 2)
        human_review_rate = round((human_review_count / total_requests) * 100.0, 2)

        # 4. Check Breaches
        breaches = []
        if avail_pct < self.target.availability_pct:
            breaches.append(f"Availability below {self.target.availability_pct}%: {avail_pct}%")
        if median_lat > self.target.median_latency_ms:
            breaches.append(f"Median Latency above {self.target.median_latency_ms}ms: {median_lat}ms")
        if p95_lat > self.target.p95_latency_ms:
            breaches.append(f"P95 Latency above {self.target.p95_latency_ms}ms: {p95_lat}ms")
        if p99_lat > self.target.p99_latency_ms:
            breaches.append(f"P99 Latency above {self.target.p99_latency_ms}ms: {p99_lat}ms")
        if fallback_rate > self.target.max_fallback_rate_pct:
            breaches.append(f"Fallback Rate above {self.target.max_fallback_rate_pct}%: {fallback_rate}%")
        if hallucination_rate > self.target.max_hallucination_rate_pct:
            breaches.append(f"Hallucination Rate above {self.target.max_hallucination_rate_pct}%: {hallucination_rate}%")
        if human_review_rate > self.target.max_human_review_rate_pct:
            breaches.append(f"Human Review Rate above {self.target.max_human_review_rate_pct}%: {human_review_rate}%")

        # 5. Error Budget Remaining (%)
        # Allowed un-availability = 100% - 99.9% = 0.1%
        allowed_error_pct = max(0.001, 100.0 - self.target.availability_pct)
        actual_error_pct = max(0.0, 100.0 - avail_pct)
        error_budget_remaining = max(0.0, round(((allowed_error_pct - actual_error_pct) / allowed_error_pct) * 100.0, 2))

        slo_met = len(breaches) == 0

        if not slo_met:
            logger.warning(f"[AISloEngine] SLO BREACH DETECTED: {breaches}")

        return SloStatusReport(
            total_requests=total_requests,
            availability_pct=avail_pct,
            median_latency_ms=round(median_lat, 2),
            p95_latency_ms=round(p95_lat, 2),
            p99_latency_ms=round(p99_lat, 2),
            fallback_rate_pct=fallback_rate,
            hallucination_rate_pct=hallucination_rate,
            human_review_rate_pct=human_review_rate,
            error_budget_remaining_pct=error_budget_remaining,
            slo_met=slo_met,
            breached_slos=breaches
        )
