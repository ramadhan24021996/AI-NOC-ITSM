"""
Incident Cluster Module
Groups multi-device and multi-modal temporal events into unified Incident Clusters.
"""

from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Set, Any, Optional
from datetime import datetime, timezone
import time
from .event_normalizer import NormalizedEvent, SeverityLevel, ModalityType
from .temporal_window import TemporalWindow


@dataclass
class IncidentCluster:
    cluster_id: str
    primary_device_id: str
    affected_devices: List[str]
    max_severity: SeverityLevel
    modalities: List[str]
    event_sequence: List[NormalizedEvent]
    summary: str = ""
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "cluster_id": self.cluster_id,
            "primary_device_id": self.primary_device_id,
            "affected_devices": self.affected_devices,
            "max_severity": self.max_severity.value if isinstance(self.max_severity, Enum) else str(self.max_severity),
            "modalities": self.modalities,
            "event_count": len(self.event_sequence),
            "events": [e.to_dict() for e in self.event_sequence],
            "summary": self.summary,
            "created_at": self.created_at
        }


class IncidentClusterEngine:
    def __init__(self):
        self._active_clusters: Dict[str, IncidentCluster] = {}

    def cluster_window(self, window: TemporalWindow) -> IncidentCluster:
        """
        Clusters events within a temporal window into a structured IncidentCluster.
        """
        events = sorted(window.events, key=lambda x: x.timestamp)
        devices = list({e.device_id for e in events})

        # Determine max severity
        severity_order = [SeverityLevel.INFO, SeverityLevel.LOW, SeverityLevel.WARNING, SeverityLevel.HIGH, SeverityLevel.CRITICAL]
        max_sev = SeverityLevel.INFO
        for e in events:
            if severity_order.index(e.severity) > severity_order.index(max_sev):
                max_sev = e.severity

        modalities = list({e.modality.value if isinstance(e.modality, Enum) else str(e.modality) for e in events})

        cluster_id = f"INC-{window.device_id}-{int(time.time())}"
        summary = f"Multi-Modal Incident ({len(events)} events) across [{', '.join(modalities)}] on {window.device_id}"

        cluster = IncidentCluster(
            cluster_id=cluster_id,
            primary_device_id=window.device_id,
            affected_devices=devices,
            max_severity=max_sev,
            modalities=modalities,
            event_sequence=events,
            summary=summary
        )
        self._active_clusters[cluster_id] = cluster
        return cluster

    def get_cluster(self, cluster_id: str) -> Optional[IncidentCluster]:
        return self._active_clusters.get(cluster_id)
