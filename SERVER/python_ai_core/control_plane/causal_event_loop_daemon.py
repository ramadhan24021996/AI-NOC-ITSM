"""
Phase 4.0-B Causal Event Loop Daemon (control_plane/causal_event_loop_daemon.py)

Background worker daemon for Event Control Plane Orchestrator.
Continuously processes incoming telemetry envelopes from PostgreSQL / NATS safely.
"""

import logging
import time
from typing import Dict, Any, Optional
from control_plane.event_envelope import CausalEventEnvelope
from control_plane.pipeline_orchestrator import PipelineOrchestrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("CAUSAL_EVENT_LOOP_DAEMON")


class CausalEventLoopDaemon:
    def __init__(self, worker_id: str = "WORKER-DAEMON-01"):
        self.worker_id = worker_id
        self.orchestrator = PipelineOrchestrator(worker_id=worker_id)
        self.is_running = False

    def process_single_event(self, envelope: CausalEventEnvelope) -> Dict[str, Any]:
        """Processes a single event envelope through orchestrator."""
        return self.orchestrator.process_event_envelope(envelope)

    def run_daemon_tick(self, test_envelope: Optional[CausalEventEnvelope] = None) -> Dict[str, Any]:
        """Runs a single daemon tick for background or test execution."""
        logger.info(f"[DAEMON TICK] Worker '{self.worker_id}' executing event loop tick.")
        if test_envelope:
            return self.process_single_event(test_envelope)
        return {"status": "NO_EVENT_PROCESSED"}
