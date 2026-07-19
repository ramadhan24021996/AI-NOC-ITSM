from pydantic import BaseModel, Field
from typing import List, Optional, Any

class IncidentSchema(BaseModel):
    incident_id: str
    severity: str
    symptom: str
    root_cause: str
    timeline: List[str]
    confidence: float
    risk_level: str
    recommended_action: str
    requires_human_approval: bool

class IncidentReportSchema(BaseModel):
    # OUTPUT WAJIB 25 POIN SESUAI DIREKTIF ENTERPRISE
    executive_summary: str = Field(..., description="1. Executive Summary")
    incident_category: str = Field(..., description="2. Incident Category")
    severity: str = Field(..., description="3. Severity")
    confidence_score: float = Field(..., description="4. Confidence Score")
    evidence: List[str] = Field(default_factory=list, description="5. Evidence")
    timeline: List[str] = Field(default_factory=list, description="6. Timeline")
    root_cause_analysis: str = Field(..., description="7. Root Cause Analysis")
    possible_causes: List[str] = Field(default_factory=list, description="8. Kemungkinan Penyebab")
    dependency_analysis: str = Field(..., description="9. Dependency Analysis")
    business_impact: str = Field(..., description="10. Business Impact")
    blast_radius: str = Field(..., description="11. Blast Radius")
    risk_assessment: str = Field(..., description="12. Risk Assessment")
    immediate_recommendation: str = Field(..., description="13. Immediate Recommendation")
    detailed_handling_steps: List[str] = Field(default_factory=list, description="14. Detailed Step-by-Step Handling")
    validation_checklist: List[str] = Field(default_factory=list, description="15. Validation Checklist")
    verification_checklist: List[str] = Field(default_factory=list, description="16. Verification Checklist")
    rollback_recommendation: str = Field(..., description="17. Rollback Recommendation")
    prevention_recommendation: str = Field(..., description="18. Prevention Recommendation")
    related_sop: List[str] = Field(default_factory=list, description="19. Related SOP")
    related_playbook: List[str] = Field(default_factory=list, description="20. Related Playbook")
    related_historical_incident: List[str] = Field(default_factory=list, description="21. Related Historical Incident")
    lessons_learned: str = Field(..., description="22. Lessons Learned")
    monitoring_recommendation: str = Field(..., description="23. Monitoring Recommendation")
    future_prediction: str = Field(..., description="24. Future Prediction")
    overall_health_assessment: str = Field(..., description="25. Overall Health Assessment")
