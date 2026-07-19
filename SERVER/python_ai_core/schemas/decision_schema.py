from pydantic import BaseModel, Field
from typing import List, Dict, Optional, Any

class RiskAssessment(BaseModel):
    operational: str = Field(..., description="Operational Risk assessment")
    security: str = Field(..., description="Security Risk assessment")
    availability: str = Field(..., description="Availability Risk assessment")
    compliance: str = Field(..., description="Compliance Risk assessment")
    overall: str = Field(..., description="Overall Risk assessment")

class AlternativeHypothesis(BaseModel):
    hypothesis: str
    confidence: float
    evidence: List[str]
    counter_evidence: List[str]
    accept_reason: str
    reject_reason: str

class EvidenceDetail(BaseModel):
    description: str
    source: str
    timestamp: str
    confidence: float
    reliability: str
    freshness: str
    weight: float

class RecommendedAction(BaseModel):
    action: str
    reason: str
    expected_result: str
    risk: str
    rollback_available: bool
    automation_allowed: bool
    requires_hitl: bool

class DecisionPackageSchema(BaseModel):
    incident_id: str
    hostname: str
    site: str
    severity: str
    osi_layer: str
    root_cause: str
    confidence: float
    summary: str
    
    alternative_hypotheses: List[AlternativeHypothesis]
    
    critical_evidence: List[EvidenceDetail]
    supporting_evidence: List[EvidenceDetail]
    counter_evidence: List[EvidenceDetail]
    missing_evidence: List[str]
    
    timeline: List[str]
    dependency_chain: List[str]
    
    blast_radius: Dict[str, Any]
    business_impact: Dict[str, Any]
    risk_assessment: RiskAssessment
    
    recommended_action: List[RecommendedAction]
    rollback_plan: List[str]
    verification_plan: List[str]
    
    knowledge_used: List[str]
    decision_trace: List[str]
    
    policy_result: str
    automation_allowed: bool
    requires_human: bool
    approval_level: str
