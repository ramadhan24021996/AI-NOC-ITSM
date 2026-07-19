from pydantic import BaseModel, Field
from typing import List

class CriticSchema(BaseModel):
    critic_score: int = Field(..., description="Risk score from 0 (no risk) to 100 (extreme danger)")
    critic_reason: str = Field(..., description="Summary of the critic evaluation and why the mitigation is assumed wrong")
    rollback_risk: str = Field(..., description="Rollback risk level (LOW, MEDIUM, HIGH)")
    dependency_risk: str = Field(..., description="Dependency coupling risk level (LOW, MEDIUM, HIGH)")
    missing_evidence: float = Field(..., description="Estimated percentage of missing evidence needed for this action (0.0 to 100.0)")
    attack_findings: List[str] = Field(default_factory=list, description="Specific findings highlighting why the mitigation could fail or cause issues")
    hidden_risks: List[str] = Field(default_factory=list, description="List of hidden coupling, data loss, or system instability risks")
    better_alternatives: List[str] = Field(default_factory=list, description="Suggested better, safer, or less risky alternative actions")
