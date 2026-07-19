from pydantic import BaseModel, Field
from typing import Optional

class VerificationSchema(BaseModel):
    incident_id: Optional[str] = Field(None, description="Incident ID")
    verification_status: str = Field(..., description="Status: SUCCESS, RESOLVED, FAILED, PARTIAL")
    service_alive: bool = Field(True, description="Whether target service is running")
    port_open: bool = Field(True, description="Whether port is listening")
    cpu_normalized: bool = Field(True, description="Whether CPU utilization is normal")
    memory_normalized: bool = Field(True, description="Whether memory utilization is normal")
    logs_clean: bool = Field(True, description="Whether logs are clean and error-free")
    rollback_needed: bool = Field(False, description="Whether rollback action is required")
    metrics: Optional[dict] = Field(default_factory=dict, description="Captured telemetry metrics")
