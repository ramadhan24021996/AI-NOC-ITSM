from pydantic import BaseModel
from datetime import datetime
from enum import Enum

class FeatureAuditEvent(Enum):
    CREATED = "Feature Created"
    UPDATED = "Feature Updated"
    VALIDATED = "Feature Validated"
    REJECTED = "Feature Rejected"
    ARCHIVED = "Feature Archived"
    RESTORED = "Feature Restored"

class FeatureAuditLog(BaseModel):
    correlation_id: str
    tenant_id: str
    user_service: str
    timestamp: datetime
    version: str
    reason: str
    event: FeatureAuditEvent
