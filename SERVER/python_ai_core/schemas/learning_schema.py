from pydantic import BaseModel, Field
from typing import Optional, List

class LearningSchema(BaseModel):
    incident_id: str = Field(..., description="Incident ID")
    root_cause: str = Field(..., description="Identified Root Cause")
    successful_action: str = Field(..., description="Successful resolution steps/action")
    verification_status: str = Field(..., description="Verification status: SUCCESS, FAILED, PARTIAL")
    human_confirmed: bool = Field(True, description="Human confirmation flag")
    confidence: float = Field(..., description="Feedback confidence score")
    learning_allowed: bool = Field(True, description="Whether learning is allowed based on gate conditions")
    
    # Optional fields for backward compatibility/vector store metadata
    title: Optional[str] = Field(None, description="Incident Title")
    symptoms: Optional[str] = Field(None, description="Incident Symptoms")
    vector_embedding: Optional[List[float]] = Field(None, description="Vector embedding array")
