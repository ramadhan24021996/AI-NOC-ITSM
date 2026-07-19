from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field

class KnowledgeDocumentSchema(BaseModel):
    title: str
    content_type: str = Field(description="SOP, PLAYBOOK, VENDOR_DOC, POST_MORTEM, etc")
    domain: str = Field(description="NETWORK, SERVER, WINDOWS, LINUX, etc")
    osi_layer: List[str] = Field(description="List of OSI Layers, e.g. ['Layer3 Network', 'Layer7 Application']")
    device_types: List[str] = Field(description="List of devices, e.g. ['Switch', 'Router', 'PC']")

class RootCauseSchema(BaseModel):
    primary_root_cause: str
    secondary_cause: Optional[str] = None
    trigger: Optional[str] = None
    symptom: Optional[str] = None
    noise: Optional[str] = None
    false_symptom: Optional[str] = None
    failure_signature: str = Field(description="Unique signature, e.g. PRINT_SPOOLER_CRASH")

class EvidenceItemSchema(BaseModel):
    description: str
    source: str = "UNKNOWN"
    confidence: float = 0.0
    weight: float = 0.0
    timestamp_relevance: str = "UNKNOWN"

class KnowledgeEvidenceSchema(BaseModel):
    supporting_evidence: List[EvidenceItemSchema] = []
    contradicting_evidence: List[EvidenceItemSchema] = []
    missing_evidence: List[str] = []
    required_evidence: List[str] = []

class DependencySchema(BaseModel):
    depends_on: List[str] = []
    affects: List[str] = []
    caused_by: List[str] = []
    blocks: List[str] = []
    requires: List[str] = []
    impacts: List[str] = []

class RemediationSchema(BaseModel):
    immediate_action: str = "UNKNOWN"
    permanent_fix: str = "UNKNOWN"
    rollback: str = "UNKNOWN"
    verification: str = "UNKNOWN"
    escalation: str = "UNKNOWN"
    automation_allowed: bool = False
    automation_risk: str = "HIGH"
    human_approval_required: bool = True

class KnowledgeVersionSchema(BaseModel):
    version: str = "1.0"
    effective_date: str = "UNKNOWN"
    expiry_date: str = "UNKNOWN"
    vendor: str = "UNKNOWN"
    firmware: str = "UNKNOWN"
    os: str = "UNKNOWN"
    software: str = "UNKNOWN"
    driver: str = "UNKNOWN"

class KnowledgePayloadSchema(BaseModel):
    document: KnowledgeDocumentSchema
    metadata: Dict[str, Any] = {}
    root_cause: RootCauseSchema
    evidence: KnowledgeEvidenceSchema
    counter_evidence: List[str] = []
    dependency: DependencySchema
    blast_radius: str = "Single Device"
    verification: List[str] = []
    remediation: RemediationSchema
    confidence: float = Field(default=80.0, description="Overall confidence of this knowledge 0-100")
    knowledge_weight: float = 1.0
    version: KnowledgeVersionSchema
    embedding_payload: str = Field(description="A clean, concise string that summarizes everything, specifically designed to be embedded by a Vector model.")
