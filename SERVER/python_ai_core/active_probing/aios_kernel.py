"""
Minimal AIOS Micro-Kernel Module
Stripped Micro-Kernel focusing strictly on core OS responsibilities:
- Agent Lifecycle Management
- Task & Workload Scheduling
- Process Isolation & Sandboxing
- Resource Quotas & Allocation
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import time


@dataclass
class KernelProcessState:
    process_id: str
    agent_name: str
    cpu_quota_pct: float
    memory_limit_mb: float
    status: str       # "RUNNING", "SUSPENDED", "TERMINATED"
    allocated_time: float


class AIOSKernel:
    """Minimal Micro-Kernel managing agent lifecycles, scheduling, isolation, and resources."""

    def __init__(self, default_memory_limit_mb: float = 512.0):
        self.default_memory_limit_mb = default_memory_limit_mb
        self.active_processes: Dict[str, KernelProcessState] = {}

    def spawn_agent_process(
        self,
        agent_name: str,
        cpu_quota_pct: float = 25.0,
        memory_limit_mb: Optional[float] = None
    ) -> KernelProcessState:

        pid = f"PID-{agent_name.upper()}-{int(time.time() * 1000) % 100000}"
        mem = memory_limit_mb if memory_limit_mb is not None else self.default_memory_limit_mb

        state = KernelProcessState(
            process_id=pid,
            agent_name=agent_name,
            cpu_quota_pct=cpu_quota_pct,
            memory_limit_mb=mem,
            status="RUNNING",
            allocated_time=time.time()
        )
        self.active_processes[pid] = state
        return state

    def terminate_process(self, process_id: str) -> bool:
        if process_id in self.active_processes:
            self.active_processes[process_id].status = "TERMINATED"
            return True
        return False

    def kernel_status(self) -> Dict[str, Any]:
        return {
            "active_processes_count": len([p for p in self.active_processes.values() if p.status == "RUNNING"]),
            "total_spawned": len(self.active_processes),
            "isolation_mode": "SANDBOXED_MICROKERNEL"
        }
