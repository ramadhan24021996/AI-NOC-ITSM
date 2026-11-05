"""
SERVER.integration - Webhook Receiver
Receives Alertmanager & N8N webhook alerts and converts them into DTOs.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any
from SERVER.contracts.schemas import IncidentQueryContract

class WebhookReceiver(ABC):
    """Abstract Webhook Alert Receiver."""
    @abstractmethod
    def parse_webhook_alert(self, payload: Dict[str, Any]) -> IncidentQueryContract:
        pass
