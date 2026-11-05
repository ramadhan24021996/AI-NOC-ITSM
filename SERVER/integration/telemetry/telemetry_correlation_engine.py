"""
SERVER.integration.telemetry — Telemetry Correlation Engine
============================================================
Tahap 2.6A — Telemetry Integration

Mengkorelasikan multiple telemetry events dari sumber berbeda (Netdata + PC Agent)
menjadi SATU Unified Incident Event dengan skor confidence dan composite severity,
sehingga AI tidak menerima duplikasi alert yang bising.
"""
import logging
import uuid
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional
from datetime import datetime, timezone
from SERVER.integration.telemetry.telemetry_normalizer import NormalizedTelemetryDTO

logger = logging.getLogger("integration.telemetry.correlation")


@dataclass
class CorrelatedIncidentDTO:
    incident_id: str
    host_name: str
    primary_severity: str       # "low" | "medium" | "high" | "critical"
    confidence_score: float     # 0.0 - 1.0
    summary_text: str
    correlated_sources: List[str]
    metrics_summary: Dict[str, Any]
    timestamp: str


class TelemetryCorrelationEngine:
    """
    Correlates individual NormalizedTelemetryDTO entries per host/device into a
    single unified incident alert with composite severity calculation.
    """

    def __init__(self):
        # Memory buffer for time-window correlation: host_name -> list of DTOs
        self._host_buffer: Dict[str, List[NormalizedTelemetryDTO]] = {}

    def ingest_and_correlate(
        self, telemetry_dto: NormalizedTelemetryDTO
    ) -> CorrelatedIncidentDTO:
        """
        Ingests a validated DTO and produces a CorrelatedIncidentDTO.
        """
        host = telemetry_dto.host_name
        if host not in self._host_buffer:
            self._host_buffer[host] = []

        self._host_buffer[host].append(telemetry_dto)
        # Retain last 10 entries per host
        if len(self._host_buffer[host]) > 10:
            self._host_buffer[host] = self._host_buffer[host][-10:]

        recent_dtos = self._host_buffer[host]
        sources = list({d.source_type for d in recent_dtos})

        # Calculate composite severity
        severities = [d.severity for d in recent_dtos]
        composite_severity = "low"
        if "critical" in severities:
            composite_severity = "critical"
        elif "high" in severities:
            composite_severity = "high"
        elif "medium" in severities:
            composite_severity = "medium"

        # Calculate confidence score based on multi-source confirmation
        confidence = 0.75  # Base confidence for single source
        if len(sources) > 1:
            confidence = 0.95  # High confidence when Netdata AND Agent confirm incident

        summary_parts = [f"{d.source_type}:{d.metric_name}={d.value}{d.unit}" for d in recent_dtos[-3:]]
        summary_text = f"Correlated Incident on {host} [{composite_severity.upper()}]: " + ", ".join(summary_parts)

        return CorrelatedIncidentDTO(
            incident_id=f"INC-{uuid.uuid4().hex[:8].upper()}",
            host_name=host,
            primary_severity=composite_severity,
            confidence_score=confidence,
            summary_text=summary_text,
            correlated_sources=sources,
            metrics_summary={d.metric_name: d.value for d in recent_dtos},
            timestamp=datetime.now(timezone.utc).isoformat(),
        )
