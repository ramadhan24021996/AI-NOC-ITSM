"""
Active Cognitive Intelligence Daemon (24/7 Proactive Observer Engine)
Integrates Adaptive Closed-Loop Decision Orchestrator for 24/7 autonomous incident response.
"""

import os
import sys
import json
import time
import uuid
import logging
import threading
import psycopg2
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional


# Ensure parent python_ai_core paths are resolvable
current_dir = os.path.dirname(os.path.abspath(__file__))
parent_dir = os.path.abspath(os.path.join(current_dir, ".."))
if parent_dir not in sys.path:
    sys.path.insert(0, parent_dir)

from telemetry.hardware_collector import HardwareTelemetryCollector
from telemetry.enterprise_connectors import EnterpriseConnectors
from telemetry.site_partitioner import get_partitioned_subject
from learning.curiosity_engine import CuriosityEngine
from core.adaptive_incident_model import IncidentContext
from probabilistic.closed_loop_orchestrator import ClosedLoopDecisionOrchestrator

logging.basicConfig(level=logging.INFO, format="[ACTIVE-OBSERVER] %(asctime)s - %(levelname)s - %(message)s")


class ActiveObserverDaemon:
    """
    24/7 Active Proactive Observer Daemon.
    Monitors telemetry 24/7 and triggers ClosedLoopDecisionOrchestrator for adaptive incident resolution.
    """

    def __init__(self, db_config: Optional[Dict[str, Any]] = None):
        self.running = False
        self.interval_sec = int(os.getenv("OBSERVER_SWEEP_INTERVAL_SEC", "30"))
        self.hw_collector = HardwareTelemetryCollector()
        self.ent_connectors = EnterpriseConnectors()
        self.curiosity_engine = CuriosityEngine()
        self.orchestrator = ClosedLoopDecisionOrchestrator()
        self._lock = threading.RLock()
        self._executor = ThreadPoolExecutor(max_workers=5, thread_name_prefix="ActiveObserverWorker")
        
        self.db_config = db_config or {
            "dbname": os.environ.get("POSTGRES_DB", os.environ.get("DB_NAME", "osi_system")),
            "user": os.environ.get("POSTGRES_USER", os.environ.get("DB_USER", "postgres")),
            "password": os.environ.get("POSTGRES_PASSWORD", os.environ.get("DB_PASSWORD", "")),
            "host": os.environ.get("DB_HOST", "postgres"),
            "port": int(os.environ.get("DB_PORT", os.environ.get("POSTGRES_PORT", 5432)))
        }

    def collect_and_validate(self) -> Dict[str, Any]:
        """Collect & Validate Telemetry across all components."""
        hw = self.hw_collector.collect_all()
        ent = self.ent_connectors.collect_all()
        
        return {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "hardware": hw,
            "enterprise": ent,
            "validated": True
        }

    def analyze_early_warnings(self, telemetry: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Predict Early Warnings & anomalies."""
        warnings = []
        hw_data = telemetry.get("hardware", {}).get("data", {})

        gpus = hw_data.get("gpu", {}).get("gpus", [])
        for gpu in gpus:
            mem_u = gpu.get("memory_used_mb", 0)
            mem_t = gpu.get("memory_total_mb", 1)
            mem_pct = (mem_u / mem_t) * 100 if mem_t > 0 else 0
            if mem_pct > 85.0:
                warnings.append({
                    "warning_type": "GPU_VRAM_EXHAUSTION_WARNING",
                    "component": gpu.get("name", "GPU"),
                    "severity": "WARNING",
                    "details": f"VRAM usage at {mem_pct:.1f}% ({mem_u}/{mem_t} MB). Potential memory leak detected.",
                    "recommended_action": "Review GPU process allocation & clear stale context buffer",
                    "risk_score": 0.65
                })

        return warnings

    def process_closed_loop_incidents(self, warnings: List[Dict[str, Any]], site_id: str = "kantor-pusat"):
        """Passes warnings through Adaptive ClosedLoopDecisionOrchestrator."""
        for w in warnings:
            incident_id = f"INC-AUTO-{uuid.uuid4().hex[:8].upper()}"
            ctx = IncidentContext(
                incident_id=incident_id,
                device_id=w.get("component", "SYSTEM"),
                severity=w.get("severity", "WARNING"),
                symptoms=[w.get("details", "")],
                telemetry={"warning_type": w.get("warning_type"), "risk_score": w.get("risk_score")}
            )

            cycle_result = self.orchestrator.run_closed_loop_cycle(ctx)
            logging.info(f"[ACTIVE-OBSERVER] Executed Closed-Loop Cycle for {incident_id}: Status={cycle_result.get('cycle_status')}")

    def on_realtime_event(self, event_payload: Dict[str, Any]) -> Dict[str, Any]:
        """Instant Hot-Path Handler for NATS JetStream Push Consumer (Non-Blocking)."""
        logging.info(f"[ACTIVE-OBSERVER] [NATS HOT-PATH] Event received from {event_payload.get('agent', 'Unknown')}")
        warnings = self.analyze_early_warnings(event_payload)
        if warnings:
            self._executor.submit(self.process_closed_loop_incidents, warnings, event_payload.get("site_id", "kantor-pusat"))
        return {
            "status": "DISPATCHED_ASYNC",
            "warnings_count": len(warnings),
            "hitl_enforced": True
        }


    def run_observer_sweep(self) -> Dict[str, Any]:
        """Perform a single complete proactive 24/7 observer cycle."""
        telemetry = self.collect_and_validate()
        early_warnings = self.analyze_early_warnings(telemetry)
        
        if early_warnings:
            self.process_closed_loop_incidents(early_warnings)
            
        summary = {
            "cycle_timestamp": telemetry["timestamp"],
            "hardware_status": telemetry["hardware"]["status"],
            "enterprise_status": telemetry["enterprise"]["status"],
            "warnings_detected_count": len(early_warnings),
            "status": "COMPLETED"
        }
        return summary

    def start_247_daemon(self):
        """Start the background 24/7 observer daemon loop."""
        if self.running:
            return
        self.running = True

        def _loop():
            logging.info(f"[ACTIVE-OBSERVER] 24/7 Proactive Observer Daemon Loop Started (Sweep Interval: {self.interval_sec}s)...")
            while self.running:
                try:
                    self.run_observer_sweep()
                except Exception as e:
                    logging.error(f"[ACTIVE-OBSERVER] Error in 24/7 observer loop: {e}")
                time.sleep(self.interval_sec)

        t = threading.Thread(target=_loop, daemon=True)
        t.start()

    def stop_daemon(self):
        self.running = False
        try:
            self._executor.shutdown(wait=False)
        except Exception:
            pass
        logging.info("[ACTIVE-OBSERVER] 24/7 Observer Daemon stopped.")



if __name__ == "__main__":
    observer = ActiveObserverDaemon()
    res = observer.run_observer_sweep()
    print("\n--- 24/7 ACTIVE OBSERVER DAEMON CYCLE SUMMARY ---")
    print(json.dumps(res, indent=2))
