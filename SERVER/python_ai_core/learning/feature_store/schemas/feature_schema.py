from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
from datetime import datetime
from enum import Enum

class FeatureLifecycle(Enum):
    CREATED = "CREATED"
    VALIDATED = "VALIDATED"
    ACTIVE = "ACTIVE"
    REUSED = "REUSED"
    DEPRECATED = "DEPRECATED"
    ARCHIVED = "ARCHIVED"

class FeatureQualityScore(BaseModel):
    completeness: float = Field(..., ge=0.0, le=1.0)
    consistency: float = Field(..., ge=0.0, le=1.0)
    freshness: float = Field(..., ge=0.0, le=1.0)
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence_score: float = Field(..., ge=0.0, le=1.0)
    reuse_score: float = Field(..., ge=0.0, le=1.0)

class FeatureLineage(BaseModel):
    telemetry_id: str
    collector_id: str
    normalizer_version: str
    extractor_version: str
    validator_version: str

class Feature(BaseModel):
    feature_id: str
    tenant_id: str
    source: str
    device_id: str
    category: str
    feature_name: str
    feature_value: Any
    unit: str
    timestamp: datetime
    confidence: float = Field(..., ge=0.0, le=1.0)
    evidence: str
    checksum: str
    version: str
    metadata: Dict[str, Any]
    status: FeatureLifecycle
    quality: FeatureQualityScore
    lineage: FeatureLineage
