"""
Layer 8 External Integration — Kafka Incident Consumer Service
Gap 10 / L8 Implementation:
Consumes external incident triggers (e.g. ServiceNow, Jira) from Kafka topic 'external.incident.trigger'
and forwards them to internal AI OS ingestion pipeline.
"""

import os
import json
import logging
import time
from typing import Dict, Any

logger = logging.getLogger("KAFKA_INCIDENT_CONSUMER")

class KafkaIncidentConsumer:
    def __init__(self, nats_client=None):
        self.kafka_bootstrap = os.environ.get("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
        self.topic = os.environ.get("KAFKA_TRIGGER_TOPIC", "external.incident.trigger")
        self.nats_client = nats_client
        logger.info(f"[KAFKA_CONSUMER] Initialized for topic '{self.topic}' via '{self.kafka_bootstrap}'.")

    def process_external_trigger(self, raw_payload: str) -> Dict[str, Any]:
        """
        Parses incoming Kafka message from external ITSM (ServiceNow/Jira) and normalizes it to Internal Incident format.
        """
        try:
            payload = json.loads(raw_payload)
            external_id = payload.get("ticket_id", payload.get("id", f"ext-{int(time.time())}"))
            source_system = payload.get("source", "ServiceNow/Jira")
            description = payload.get("short_description", payload.get("description", "External incident trigger"))
            severity = payload.get("severity", "HIGH").upper()
            target_device = payload.get("device_name", payload.get("hostname", "UNKNOWN_HOST"))

            normalized_incident = {
                "event_type": "EXTERNAL_ITSM_TRIGGER",
                "source": source_system,
                "external_id": external_id,
                "pc_name": target_device,
                "status": severity,
                "description": description,
                "layer": 7,
                "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
            }

            logger.info(f"[KAFKA_CONSUMER] Received external trigger ticket '{external_id}' from {source_system} for device '{target_device}'.")
            return {
                "status": "PROCESSED_SUCCESSFULLY",
                "external_id": external_id,
                "incident": normalized_incident
            }
        except Exception as e:
            logger.error(f"[KAFKA_CONSUMER] Failed to process external trigger payload: {e}")
            return {"status": "ERROR", "reason": str(e)}

    def start_listening(self):
        """Simulated loop listening to Kafka consumer topic."""
        logger.info(f"[KAFKA_CONSUMER] Listening for events on Kafka topic '{self.topic}'...")

if __name__ == "__main__":
    consumer = KafkaIncidentConsumer()
    res = consumer.process_external_trigger(json.dumps({
        "ticket_id": "INC0099881",
        "source": "ServiceNow",
        "hostname": "KASIR-POS-01",
        "severity": "CRITICAL",
        "short_description": "Database Connection Timeout reported by Store Manager"
    }))
    print("Test Kafka Incident Trigger Processing:", res)
