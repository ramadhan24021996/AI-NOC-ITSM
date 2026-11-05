"""
Phase 3.1-A & 3.1-B: Canonical Evidence Schema & Reliability/Independence Engine (phase3/causal/canonical_evidence_schema.py)

1. Canonical Evidence Schema: Standardized machine-verifiable evidence object with provenance binding.
2. Evidence Reliability Weigher: Deterministic reliability weights (Kernel: 0.95, SNMP: 0.90, Log: 0.85, User: 0.60, LLM: 0.00).
3. Evidence Independence Engine: Deduplicates multiple observations originating from the same physical sensor into 1 effective independent source.
"""

import logging
import hashlib
import json
from dataclasses import dataclass, field, asdict
from typing import Dict, Any, List, Optional
from datetime import datetime, UTC

logger = logging.getLogger("CANONICAL_EVIDENCE_SCHEMA")

RELIABILITY_WEIGHT_TABLE = {
    "OS_KERNEL_PROCESS": 0.95,
    "NODE_EXPORTER": 0.95,
    "SNMP_HARDWARE": 0.90,
    "APPLICATION_LOG": 0.85,
    "SYSTEMD_JOURNAL": 0.85,
    "USER_REPORT_TICKET": 0.60,
    "HISTORICAL_PATTERN": 0.00,
    "LLM_INFERENCE": 0.00,
    "VECTOR_SIMILARITY": 0.00
}


@dataclass
class CanonicalEvidenceObject:
    evidence_id: str
    incident_id: str
    source_type: str
    source_instance: str
    source_record_id: str
    observed_at: str
    collected_at: str
    entity_id: str
    signal: str
    value: Any
    unit: str
    reliability: float
    independence_group: str
    provenance: Dict[str, Any]
    derived_from: Optional[str] = None
    integrity_hash: str = field(init=False)

    def __post_init__(self):
        # Calculate integrity hash over critical evidence fields
        raw_str = f"{self.evidence_id}:{self.incident_id}:{self.source_type}:{self.source_instance}:{self.source_record_id}:{self.observed_at}:{self.value}"
        self.integrity_hash = hashlib.sha256(raw_str.encode("utf-8")).hexdigest()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


class EvidenceReliabilityWeigher:
    @staticmethod
    def get_reliability_weight(source_type: str) -> float:
        st_upper = source_type.upper().strip()
        weight = RELIABILITY_WEIGHT_TABLE.get(st_upper)
        if weight is None:
            # Fallback for unknown sources -> Treat as 0.00 physical weight
            logger.warning(f"[EVIDENCE RELIABILITY] Unknown source type '{source_type}'. Assigning 0.00 physical weight.")
            return 0.00
        return weight


class EvidenceIndependenceEngine:
    """
    Groups observations by physical source/origin (independence_group).
    Calculates the Effective Independent Evidence Count to prevent false confidence inflation.
    """
    @staticmethod
    def calculate_effective_independent_sources(evidence_list: List[CanonicalEvidenceObject]) -> Dict[str, Any]:
        groups: Dict[str, List[CanonicalEvidenceObject]] = {}
        physical_count = 0

        for ev in evidence_list:
            if ev.reliability > 0.0:
                physical_count += 1
                grp = ev.independence_group
                if grp not in groups:
                    groups[grp] = []
                groups[grp].append(ev)

        effective_independent_count = len(groups)

        return {
            "total_evidence_items": len(evidence_list),
            "physical_evidence_items": physical_count,
            "unique_independence_groups": list(groups.keys()),
            "effective_independent_sources": effective_independent_count,
            "deduplication_ratio": round(len(evidence_list) / max(1, effective_independent_count), 2)
        }
