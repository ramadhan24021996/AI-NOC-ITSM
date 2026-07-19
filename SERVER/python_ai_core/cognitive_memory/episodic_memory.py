from typing import Dict, Any, List, Optional
from datetime import datetime

import os
import json
import psycopg2

class EpisodicMemory:
    def __init__(self):
        self.db_host = os.environ.get("DB_HOST", "postgres")
        self.db_port = os.environ.get("DB_PORT", "5432")
        self.db_name = os.environ.get("DB_NAME", "osi_system")
        self.db_user = os.environ.get("DB_USER", "postgres")
        self.db_password = os.environ.get("DB_PASSWORD", "postgres")

    def _get_conn(self):
        try:
            return psycopg2.connect(
                host=self.db_host, port=self.db_port, dbname=self.db_name, 
                user=self.db_user, password=self.db_password
            )
        except Exception:
            return None

    def record_event(self, incident_id: str, timestamp: datetime, description: str, telemetry: Optional[Dict[str, Any]] = None):
        conn = self._get_conn()
        if not conn: return
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO incident_events (incident_id, event_type, timestamp, description, data)
                    VALUES (%s, %s, %s, %s, %s)
                """, (
                    incident_id, 
                    "MEMORY_RECORD", 
                    timestamp, 
                    description, 
                    json.dumps(telemetry) if telemetry else "{}"
                ))
            conn.commit()
        except Exception:
            conn.rollback()
        finally:
            conn.close()

    def get_timeline(self, incident_id: str) -> List[Dict[str, Any]]:
        timeline = []
        conn = self._get_conn()
        if not conn: return timeline
        try:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT event_type, timestamp, description, data 
                    FROM incident_events 
                    WHERE incident_id = %s
                    ORDER BY timestamp ASC
                """, (incident_id,))
                
                for row in cur.fetchall():
                    data_val = row[3]
                    if isinstance(data_val, str):
                        try:
                            data_val = json.loads(data_val)
                        except Exception:
                            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
                            
                    timeline.append({
                        "event_type": row[0],
                        "timestamp": row[1].isoformat() if hasattr(row[1], 'isoformat') else row[1],
                        "description": row[2],
                        "data": data_val
                    })
        except Exception:
            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
        finally:
            conn.close()
        return timeline