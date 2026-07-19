from pydantic import BaseModel, Field
from typing import List, Optional

class ActionSchema(BaseModel):
    action_id: Optional[str] = Field(None, description="Action ID")
    action_type: str = Field(..., description="Type of remediation action")
    recommended_action: str = Field(..., description="Mitigation command or task details")
    risk_level: str = Field(..., description="Risk level classification")
    requires_human_approval: bool = Field(True, description="Human approval flag")
    rollback_command: Optional[str] = Field(None, description="Command to execute for rollback")
    execution_steps: List[str] = Field(default_factory=list, description="Individual execution steps")
