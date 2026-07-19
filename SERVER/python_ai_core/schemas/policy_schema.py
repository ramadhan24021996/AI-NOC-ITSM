from pydantic import BaseModel, Field
from typing import List, Optional

class PolicySchema(BaseModel):
    policy_id: str = Field(..., description="Unique policy identifier")
    name: str = Field(..., description="Policy rule name")
    is_active: bool = Field(True, description="Whether policy is active")
    blocked_commands: List[str] = Field(default_factory=list, description="List of prohibited command substrings")
    max_risk_allowed: str = Field("low", description="Maximum risk allowed for auto execution")
    enforce_mfa: bool = Field(False, description="Whether MFA verification is required")
