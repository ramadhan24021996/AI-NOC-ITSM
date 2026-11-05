"""
Domain Event Contracts for Enterprise AI Operations Platform
"""
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from datetime import datetime

@dataclass
class DomainEventContract:
    event_id: str
    event_type: str
    timestamp: str
    payload: Dict[str, Any]
    version: str = "v1.0"

@dataclass
class IncidentCreatedEvent(DomainEventContract):
    def __post_init__(self):
        self.event_type = "IncidentCreated"

@dataclass
class KnowledgeApprovedEvent(DomainEventContract):
    def __post_init__(self):
        self.event_type = "KnowledgeApproved"
