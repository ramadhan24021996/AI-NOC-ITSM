"""
Domain DTO Models for Enterprise AI Operations Platform
"""
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional
from datetime import datetime
from SERVER.shared.enums import IncidentSeverity, ExecutionTrack, TrustRating

@dataclass
class KnowledgeChunkDTO:
    chunk_id: str
    title: str
    content: str
    source_url: str
    trust_rating: TrustRating
    similarity_score: float = 0.0
    coverage_score: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

@dataclass
class EvidenceScoreDTO:
    similarity: float
    coverage: float
    freshness: float
    source_trust: float
    consensus: float
    composite_score: float

    @property
    def is_sufficient(self) -> bool:
        return self.composite_score >= 0.70

@dataclass
class DecisionTraceEntryDTO:
    """Full observability trace entry for a single pipeline step.
    Required fields satisfy Milestone M4-OBS exit criteria.
    """
    step_name: str
    agent_id: str
    input_summary: str
    output_summary: str
    evidence_score: float
    duration_ms: float
    # Legacy-compatible optional fields (kept for backward compatibility)
    timestamp: str = ""
    input_data: Dict[str, Any] = field(default_factory=dict)
    output_data: Dict[str, Any] = field(default_factory=dict)
    execution_time_ms: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            from datetime import timezone
            self.timestamp = datetime.now(timezone.utc).isoformat()
