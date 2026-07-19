import json
import logging
import time
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger("TelemetryAPI")

class TelemetryAPI:
    """
    Facade layer for AIOps Observability.
    Decouples AI Supervisor from the actual telemetry backends (Redis/NATS/Prometheus).
    Emits raw events with Trace IDs and forwards aggregations to LearningDashboard.
    """
    def __init__(self, nats_client=None):
        self.nc = nats_client
        self._dashboard = None
        # Debounce mechanism: only publish aggregates every X seconds
        self._last_aggregate_publish = 0.0
        self.PUBLISH_INTERVAL_SEC = 2.0
        
    def _get_dashboard(self):
        if self._dashboard is None:
            try:
                from cognitive_memory.learning_dashboard import LearningDashboard
                self._dashboard = LearningDashboard()
            except Exception as e:
                logger.error(f"Failed to load LearningDashboard backend: {e}")
        return self._dashboard

    async def _publish_raw_event(self, topic: str, payload: dict):
        if not self.nc:
            return
        try:
            # Enforce schema versioning and UTC timestamps globally
            payload["schema_version"] = 1
            payload["timestamp"] = datetime.now(timezone.utc).isoformat()
            await self.nc.publish(topic, json.dumps(payload).encode('utf-8'))
        except Exception as e:
            logger.error(f"[Best-Effort Telemetry] Failed to publish raw event to {topic}: {e}")

    async def _debounce_publish_aggregate(self):
        """Prevent NATS flooding by rate-limiting aggregate snapshot publishing."""
        now = time.time()
        if (now - self._last_aggregate_publish) >= self.PUBLISH_INTERVAL_SEC:
            self._last_aggregate_publish = now
            dashboard = self._get_dashboard()
            if dashboard:
                try:
                    await dashboard.publish_metrics(self.nc)
                except Exception as e:
                    logger.error(f"[Best-Effort Telemetry] Failed to publish aggregates: {e}")

    async def record_incident_lifecycle(self, event_type: str, incident_id: str, trace_id: str, extra_data: dict = None):
        """
        Emit standard lifecycle events: 
        incident_received, retrieval_started, llm_request_started, decision_generated, etc.
        """
        payload = {
            "event": event_type,
            "incident_id": incident_id,
            "trace_id": trace_id
        }
        if extra_data:
            payload.update(extra_data)
            
        await self._publish_raw_event(f"telemetry.raw.lifecycle", payload)

    async def record_incident_resolved(self, incident_id: str, trace_id: str, confidence: float, latencies: dict, is_false_positive: bool = False):
        """
        Emit when AI completes incident analysis.
        latencies dict should contain: retrieval_ms, embedding_ms, llm_ms, total_latency_ms.
        """
        await self._publish_raw_event("telemetry.raw.incident_resolved", {
            "event": "incident_resolved",
            "incident_id": incident_id,
            "trace_id": trace_id,
            "confidence": confidence,
            "latencies_ms": latencies,
            "is_false_positive": is_false_positive
        })
        
        dashboard = self._get_dashboard()
        if dashboard:
            total_ms = latencies.get("total_latency_ms", 0.0)
            dashboard.record_incident_resolved(confidence, total_ms, is_false_positive)
            await self._debounce_publish_aggregate()

    async def record_feedback(self, incident_id: str, trace_id: str, is_human_override: bool):
        """Emit when a human overrides or approves an AI decision."""
        await self._publish_raw_event("telemetry.raw.human_feedback", {
            "event": "human_feedback",
            "incident_id": incident_id,
            "trace_id": trace_id,
            "is_override": is_human_override
        })
        
        dashboard = self._get_dashboard()
        if dashboard:
            dashboard.record_feedback(is_human_override)
            await self._debounce_publish_aggregate()

    async def record_knowledge_added(self, playbook_id: str, trace_id: str):
        """Emit when a new memory vector is embedded into pgvector."""
        await self._publish_raw_event("telemetry.raw.knowledge_added", {
            "event": "knowledge_added",
            "playbook_id": playbook_id,
            "trace_id": trace_id
        })
        
        dashboard = self._get_dashboard()
        if dashboard:
            dashboard.record_knowledge_added()
            await self._debounce_publish_aggregate()
