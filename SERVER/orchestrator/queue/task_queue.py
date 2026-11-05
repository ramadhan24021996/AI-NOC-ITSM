"""
SERVER.orchestrator - Task Queue
In-memory queue for task execution management.
"""
from typing import List, Any, Optional
import queue

class TaskQueue:
    """In-memory task queue manager."""
    def __init__(self, max_size: int = 1000):
        self._queue: queue.Queue[Any] = queue.Queue(maxsize=max_size)

    def enqueue(self, task: Any) -> bool:
        try:
            self._queue.put_nowait(task)
            return True
        except queue.Full:
            return False

    def dequeue(self) -> Optional[Any]:
        try:
            return self._queue.get_nowait()
        except queue.Empty:
            return None

    def size(self) -> int:
        return self._queue.qsize()
