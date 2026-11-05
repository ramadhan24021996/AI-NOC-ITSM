"""
Evidence Trust Scorer Module
Applies weighted trust scores per telemetry source:
- Packet Capture: 0.98 (Very High)
- SNMP Counter: 0.90 (High)
- Windows EventLog / Syslog: 0.88 (High)
- Browser Console Log: 0.75 (Medium)
- User Incident Report: 0.60 (Low-Medium)
Used to calculate source-weighted RCA confidence scores.
"""

from dataclasses import dataclass
from typing import Dict, List, Any
from enum import Enum


class EvidenceSourceType(Enum):
    PACKET_CAPTURE = "PACKET_CAPTURE"
    SNMP_COUNTER = "SNMP_COUNTER"
    EVENT_LOG = "EVENT_LOG"
    BROWSER_CONSOLE = "BROWSER_CONSOLE"
    USER_REPORT = "USER_REPORT"


@dataclass
class EvidenceTrustScore:
    source_type: EvidenceSourceType
    trust_weight: float
    description: str


class EvidenceTrustScorer:
    """Calculates weighted trust scores across evidence sources."""

    def __init__(self):
        self.trust_weights = {
            EvidenceSourceType.PACKET_CAPTURE: 0.98,
            EvidenceSourceType.SNMP_COUNTER: 0.90,
            EvidenceSourceType.EVENT_LOG: 0.88,
            EvidenceSourceType.BROWSER_CONSOLE: 0.75,
            EvidenceSourceType.USER_REPORT: 0.60
        }

    def get_source_weight(self, source_type: EvidenceSourceType) -> float:
        return self.trust_weights.get(source_type, 0.75)

    def calculate_composite_evidence_trust(
        self,
        evidence_sources: List[EvidenceSourceType]
    ) -> float:
        if not evidence_sources:
            return 0.75
        weights = [self.get_source_weight(s) for s in evidence_sources]
        return round(sum(weights) / len(weights), 3)
