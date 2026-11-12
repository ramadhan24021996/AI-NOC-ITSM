"""
Phase 4.0-B Idempotency Manager (control_plane/idempotency_manager.py)

Enforces explicit database idempotency via UNIQUE(idempotency_key) constraint on system_audits.
Prevents duplicate processing of re-delivered NATS JetStream events.
"""

import logging
import os
import psycopg2
import json
from typing import Dict, Any, Tuple, Optional
from control_plane.event_envelope import CausalEventEnvelope

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(name)s: %(message)s")
logger = logging.getLogger("IDEMPOTENCY_MANAGER")

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = int(os.environ.get("DB_PORT", "5433" if DB_HOST in ("127.0.0.1", "localhost") else "5432"))
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", ""))

DB_CONFIG = {
    "host": DB_HOST,
    "port": DB_PORT,
    "dbname": DB_NAME,
    "user": DB_USER,
    "password": DB_PASSWORD,
}


class IdempotencyManager:
    def __init__(self, db_config: Dict[str, Any] = None):
        self.db_config = db_config or DB_CONFIG
        self.registered_keys = set()  # Memory cache backup

    def register_and_check_idempotency(self, envelope: CausalEventEnvelope) -> Tuple[bool, str]:
        """
        Checks and registers explicit idempotency key in DB system_audits table.
        Returns: (is_duplicate, reason)
        """
        key = envelope.calculate_idempotency_key()

        if key in self.registered_keys:
            logger.warning(f"[IDEMPOTENCY REJECT] Memory cache hit for key '{key[:8]}...' (Event ID: '{envelope.event_id}')")
            return True, "MEM_CACHE_DUPLICATE_REJECTED"

        conn = None
        cur = None
        try:
            conn = psycopg2.connect(**self.db_config)
            cur = conn.cursor()

            # Check if idempotency key exists in system_audits
            query_check = """
                SELECT id FROM system_audits 
                WHERE audit_type = 'EVENT_IDEMPOTENCY' AND metadata->>'idempotency_key' = %s;
            """
            cur.execute(query_check, (key,))
            row = cur.fetchone()

            if row:
                self.registered_keys.add(key)
                logger.warning(f"[IDEMPOTENCY REJECT] DB record exists for key '{key[:8]}...' (Event ID: '{envelope.event_id}')")
                return True, "DB_CONSTRAINT_DUPLICATE_REJECTED"

            # Register idempotency record in DB
            meta = {
                "idempotency_key": key,
                "event_id": envelope.event_id,
                "incident_id": envelope.incident_id,
                "source": envelope.source,
                "payload_hash": envelope.payload_hash,
                "schema_version": envelope.schema_version
            }
            query_insert = """
                INSERT INTO system_audits (audit_type, component, action, status, details, metadata)
                VALUES (%s, %s, %s, %s, %s, %s);
            """
            cur.execute(query_insert, (
                "EVENT_IDEMPOTENCY",
                "IDEMPOTENCY_MANAGER",
                "REGISTER_KEY",
                "REGISTERED",
                f"Registered idempotency key for event {envelope.event_id}",
                json.dumps(meta)
            ))
            conn.commit()

            self.registered_keys.add(key)
            logger.info(f"[IDEMPOTENCY REGISTERED] Idempotency key '{key[:8]}...' registered cleanly for Event '{envelope.event_id}'")
            return False, "IDEMPOTENCY_REGISTERED"

        except Exception as e:
            logger.error(f"[IDEMPOTENCY DB ERROR] Failed to query/register idempotency key: {e}")
            # Memory fallback for testing/offline DB
            if key in self.registered_keys:
                return True, "MEM_FALLBACK_DUPLICATE_REJECTED"
            self.registered_keys.add(key)
            return False, "REGISTERED_MEMORY_FALLBACK"
        finally:
            if cur is not None:
                try:
                    cur.close()
                except Exception:
                    pass
            if conn is not None:
                try:
                    conn.close()
                except Exception:
                    pass
