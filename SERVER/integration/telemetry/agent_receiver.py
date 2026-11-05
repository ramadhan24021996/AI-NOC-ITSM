"""
SERVER.integration.telemetry — Agent Receiver
=============================================
Tahap 2.6A — Telemetry Integration

Menerima payload L1-L7 Probe Telemetry dari Go Client PC Agent.
Menjalankan alur: Receiver → Validator → Normalizer → Correlation Engine → NATS EventBus.
"""
import logging
from typing import Dict, Any, Optional
from SERVER.integration.telemetry.telemetry_normalizer import TelemetryNormalizer, NormalizedTelemetryDTO
from SERVER.integration.telemetry.telemetry_validator import TelemetryValidator
from SERVER.integration.telemetry.telemetry_correlation_engine import TelemetryCorrelationEngine, CorrelatedIncidentDTO

logger = logging.getLogger("integration.telemetry.agent")


class AgentReceiver:
    """Receiver untuk payload L1-L7 Probe dari AI Agent PC Client."""

    def __init__(self, event_bus=None, correlation_engine=None):
        self.normalizer = TelemetryNormalizer()
        self.validator = TelemetryValidator()
        self.correlation_engine = correlation_engine or TelemetryCorrelationEngine()
        self.event_bus = event_bus

    def process_payload(self, raw_payload: Dict[str, Any]) -> Optional[CorrelatedIncidentDTO]:
        """
        Processing pipeline for Go Agent L1-L7 Probe payload.
        """
        # 1. Normalize
        normalized_dto = self.normalizer.normalize_agent(raw_payload)

        # 2. Validate
        is_valid, reason = self.validator.validate(normalized_dto)
        if not is_valid:
            logger.warning(f"[AgentReceiver] Dropped invalid probe payload: {reason}")
            return None

        # 3. Correlate
        correlated = self.correlation_engine.ingest_and_correlate(normalized_dto)

        # 4. Publish to NATS EventBus as Observer
        if self.event_bus:
            try:
                self.event_bus.publish("telemetry.agent.correlated", {
                    "incident_id": correlated.incident_id,
                    "host_name": correlated.host_name,
                    "severity": correlated.primary_severity,
                    "confidence": correlated.confidence_score,
                    "summary": correlated.summary_text,
                    "timestamp": correlated.timestamp,
                })
            except Exception as exc:
                logger.warning(f"[AgentReceiver] EventBus publish failed: {exc}")

        logger.info(f"[AgentReceiver] Processed PC Agent probe for host '{correlated.host_name}'")
        return correlated
