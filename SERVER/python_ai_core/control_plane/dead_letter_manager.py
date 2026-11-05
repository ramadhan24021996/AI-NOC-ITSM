"""
Phase 4.0-B Dead Letter Manager (control_plane/dead_letter_manager.py)

Manages Dead Letter Queue (DLQ) persistence and auditing.
Ensures ZERO SILENT FAILURES by persisting unhandled/unretryable events to PostgreSQL system_audits.
"""

import logging
import psycopg2
import json
import hashlib
from typing import Dict, Any
from control_plane.event_envelope import CausalEventEnvelope

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("DEAD_LETTER_MANAGER")

DB_CONFIG = {
    "host": "127.0.0.1",
    "port": 5433,
    "dbname": "osi_system",
    "user": "postgres",
    "password": "[REDACTED_DB_PASS]"
}


class DeadLetterManager:
    def __init__(self, db_config: Dict[str, Any] = None):
        self.db_config = db_config or DB_CONFIG

    def move_to_dead_letter_queue(self, envelope: CausalEventEnvelope, failure_reason: str, last_state: str, exc: Exception = None) -> Dict[str, Any]:
        """
        Persists failed event to PostgreSQL system_audits table as DEAD_LETTER disposition.
        """
        exc_name = type(exc).__name__ if exc else "None"
        exc_msg = str(exc) if exc else "No exception provided"

        meta = {
            "event_id": envelope.event_id,
            "incident_id": envelope.incident_id,
            "trace_id": envelope.trace_id,
            "failure_reason": failure_reason,
            "attempt_count": envelope.attempt_count,
            "last_state": last_state,
            "exception_class": exc_name,
            "exception_message": exc_msg,
            "idempotency_key": envelope.calculate_idempotency_key()
        }

        meta_str = json.dumps(meta, sort_keys=True)
        integrity_hash = hashlib.sha256(meta_str.encode("utf-8")).hexdigest()
        meta["integrity_hash"] = integrity_hash

        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()

            query_insert = """
                INSERT INTO system_audits (audit_type, component, action, status, details, metadata)
                VALUES (%s, %s, %s, %s, %s, %s);
            """
            cur.execute(query_insert, (
                "DEAD_LETTER_QUEUE",
                "DEAD_LETTER_MANAGER",
                "ROUTE_TO_DLQ",
                "DEAD_LETTER",
                f"Event '{envelope.event_id}' moved to DLQ: {failure_reason}",
                json.dumps(meta)
            ))
            conn.commit()
            conn.close()

            logger.error(f"[DLQ PERSISTED] Event '{envelope.event_id}' routed to DLQ! Reason: '{failure_reason}' (Hash: '{integrity_hash[:8]}...')")

        except Exception as e:
            logger.error(f"[DLQ PERSISTENCE ERROR] Failed to persist to system_audits DB: {e}")

        return {
            "status": "DEAD_LETTER",
            "event_id": envelope.event_id,
            "failure_reason": failure_reason,
            "integrity_hash": integrity_hash
        }
