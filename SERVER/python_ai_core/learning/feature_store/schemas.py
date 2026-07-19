from pydantic import BaseModel
from typing import Optional, Dict, Any
from datetime import datetime

class FeatureSchema(BaseModel):
    feature_id: str
    tenant_id: str
    source: str
    category: str
    evidence: str
    confidence: float
    timestamp: datetime
    version: str
    checksum: str
    metadata: Dict[str, Any]
    status: str
    reuse_count: int = 0
    last_used: Optional[datetime] = None
