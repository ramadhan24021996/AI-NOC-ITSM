import logging
import json
import uuid
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, List, Optional

logger = logging.getLogger("LONG_TERM_MEMORY")

class LongTermMemoryManager:
    """
    Layer 2: Long-Term Memory Manager
    - Stores operator preferences, incident history, RCA, resolution, SOP success,
      approval history, HITL history, audit trail, recovery history, and verification history.
    - Uses PostgreSQL (table: jarvis_long_term_records).
    - Every record mandates: uuid, timestamp, source, version, confidence, author, last_updated.
    """

    def __init__(self):
        self.db_host = os.getenv("DB_HOST", "127.0.0.1")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_name = os.getenv("DB_NAME", "osi_system")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "SecurePassword_123!")

    def _get_connection(self):
        return psycopg2.connect(
            host=self.db_host,
            port=self.db_port,
            database=self.db_name,
            user=self.user,
            password=self.password
        )

    def record_event(
        self,
        record_type: str,
        entity_id: str,
        data: Dict[str, Any],
        confidence: float = 1.0,
        author: str = "JARVIS_ENGINE",
        source: str = "OSI_SYSTEM",
        version: int = 1
    ) -> Dict[str, Any]:
        """
        Inserts a structured long-term memory record into jarvis_long_term_records.
        """
        record_uuid = str(uuid.uuid4())
        record_type_upper = record_type.upper().strip()
        data_json = json.dumps(data)

        sql = """
            INSERT INTO jarvis_long_term_records (
                uuid, record_type, entity_id, author, confidence, source, version, data, timestamp, last_updated
            ) VALUES (
                %s::uuid, %s, %s, %s, %s, %s, %s, %s::jsonb, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP
            )
            RETURNING uuid, record_type, entity_id, author, confidence, source, version, data, timestamp, last_updated;
        """

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (
                    record_uuid, record_type_upper, entity_id, author,
                    confidence, source, version, data_json
                ))
                row = cur.fetchone()
            conn.commit()
            logger.info(f"[LONG_TERM_MEMORY] Inserted {record_type_upper} record UUID: {record_uuid}")
            return dict(row)
        except Exception as e:
            conn.rollback()
            logger.error(f"[LONG_TERM_MEMORY] Failed to record event: {e}")
            raise e
        finally:
            conn.close()

    def get_records_by_type(self, record_type: str, limit: int = 20) -> List[Dict[str, Any]]:
        sql = """
            SELECT uuid, record_type, entity_id, author, confidence, source, version, data, timestamp, last_updated
            FROM jarvis_long_term_records
            WHERE record_type = %s
            ORDER BY timestamp DESC
            LIMIT %s;
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (record_type.upper().strip(), limit))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[LONG_TERM_MEMORY] Error getting records by type: {e}")
            return []
        finally:
            conn.close()

    def get_records_for_entity(self, entity_id: str, limit: int = 20) -> List[Dict[str, Any]]:
        sql = """
            SELECT uuid, record_type, entity_id, author, confidence, source, version, data, timestamp, last_updated
            FROM jarvis_long_term_records
            WHERE entity_id = %s OR data->>'pc_name' = %s OR data->>'device_name' = %s
            ORDER BY timestamp DESC
            LIMIT %s;
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (entity_id, entity_id, entity_id, limit))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[LONG_TERM_MEMORY] Error getting entity records: {e}")
            return []
        finally:
            conn.close()
