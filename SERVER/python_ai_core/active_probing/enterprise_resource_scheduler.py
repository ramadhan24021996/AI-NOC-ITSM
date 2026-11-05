"""
Enterprise Resource Scheduler Module
Manages priority queues and worker pool scheduling across 10,000+ simultaneous endpoints:
Priority ranking: CRITICAL > HIGH > MEDIUM > LOW
Worker Pool concurrency limit (Max 50 active worker tasks) to prevent probe storms.
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
from enum import Enum, auto
import heapq
import time


class IncidentPriority(Enum):
    CRITICAL = 1
    HIGH = 2
    MEDIUM = 3
    LOW = 4


@dataclass(order=True)
class ScheduledProbingTask:
    priority_level: int
    created_timestamp: float
    incident_id: str = field(compare=False)
    asset_id: str = field(compare=False)
    probe_id: str = field(compare=False)
    action: str = field(compare=False)


@dataclass
class SchedulerPoolStatus:
    active_workers: int
    max_worker_capacity: int
    queued_tasks_count: int
    processed_tasks_count: int


class EnterpriseResourceScheduler:
    """Manages priority task scheduling and worker pool throttling across enterprise endpoints."""

    def __init__(self, max_worker_capacity: int = 50):
        self.max_worker_capacity = max_worker_capacity
        self.active_workers_count = 0
        self.processed_tasks_count = 0
        self.task_queue: List[ScheduledProbingTask] = []

    def enqueue_task(
        self,
        incident_id: str,
        asset_id: str,
        probe_id: str,
        action: str,
        priority: IncidentPriority = IncidentPriority.MEDIUM
    ) -> ScheduledProbingTask:

        task = ScheduledProbingTask(
            priority_level=priority.value,
            created_timestamp=time.time(),
            incident_id=incident_id,
            asset_id=asset_id,
            probe_id=probe_id,
            action=action
        )
        heapq.heappush(self.task_queue, task)
        return task

    def acquire_worker_slot(self) -> Optional[ScheduledProbingTask]:
        """Dispatches highest-priority queued task if worker pool capacity is available."""
        if self.active_workers_count >= self.max_worker_capacity or not self.task_queue:
            return None

        task = heapq.heappop(self.task_queue)
        self.active_workers_count += 1
        return task

    def release_worker_slot(self):
        """Releases an active worker slot back to the scheduler pool."""
        if self.active_workers_count > 0:
            self.active_workers_count -= 1
            self.processed_tasks_count += 1

    def pool_status(self) -> SchedulerPoolStatus:
        return SchedulerPoolStatus(
            active_workers=self.active_workers_count,
            max_worker_capacity=self.max_worker_capacity,
            queued_tasks_count=len(self.task_queue),
            processed_tasks_count=self.processed_tasks_count
        )
