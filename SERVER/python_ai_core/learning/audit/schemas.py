from pydantic import BaseModel
from typing import Optional
from datetime import datetime

class AuditLogSchema(BaseModel):
    correlation_id: str
    learning_id: str
    tenant_id: str
    engine: str
    evidence: str
    ground_truth: str
    decision: str
    confidence: float
    duration_ms: int
    timestamp: datetime
    version: str
