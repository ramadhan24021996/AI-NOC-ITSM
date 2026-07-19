import json
import logging
import datetime
from typing import Any, Dict

logger = logging.getLogger("EVENT_STORE")

class EventStore:
    """
    Tahap 5: Event Sourcing & CQRS Pattern.
    Semua mutasi state harus melalui append-only log ini (incident_events).
    Read-model (tabel fleet_incidents / incidents) dikalkulasi ulang / diproyeksikan (Projection)
    secara deterministik dari history events ini.
    """
    
    def __init__(self, db_conn):
        self.db = db_conn

    def append_event(self, aggregate_id: str, event_type: str, payload: Dict[str, Any], actor: str = "system") -> bool:
        """
        Menyimpan event baru ke dalam log secara immutable, lalu memicu proyeksi ke read-model.
        """
        if not self.db:
            logger.error("[EVENT STORE] Database connection missing.")
            return False
            
        try:
            with self.db.cursor() as cur:
                # 1. Append Immutable Event
                cur.execute(
                    """
                    INSERT INTO incident_events (incident_id, event_type, payload)
                    VALUES (%s, %s, %s)
                    RETURNING event_id
                    """,
                    (aggregate_id, event_type, json.dumps(payload))
                )
                event_id = cur.fetchone()[0]
                
                # 2. Synchronous Projection (Update Read Model / State)
                self._project_state(cur, aggregate_id, event_type, payload)
                
            self.db.commit()
            logger.info(f"[EVENT STORE] Appended {event_type} for incident {aggregate_id} (Event ID: {event_id})")
            return True
        except Exception as e:
            self.db.rollback()
            logger.error(f"[EVENT STORE] Failed to append event {event_type} for {aggregate_id}: {e}")
            return False

    def _project_state(self, cur, aggregate_id: str, event_type: str, payload: Dict[str, Any]):
        """
        Read-Model Projections: Menerjemahkan event log menjadi state terkini di tabel `fleet_incidents`.
        """
        query_parts = []
        params = []
        
        if event_type == "INCIDENT_ACKNOWLEDGED":
            query_parts.append("acked_at = NOW()")
        elif event_type in ("INCIDENT_RESOLVED", "INCIDENT_CLOSED"):
            query_parts.append("resolved_at = NOW()")
            
        if "severity" in payload:
            query_parts.append("severity = %s")
            params.append(payload["severity"])
            
        if not query_parts:
            return
            
        query = "UPDATE fleet_incidents SET " + ", ".join(query_parts) + " WHERE incident_id = %s"
        params.append(aggregate_id)
        
        try:
            inc_id_int = int(aggregate_id)
            cur.execute(query, tuple(params))
            logger.debug(f"[PROJECTION] Projected non-status updates to incident {inc_id_int}")
        except ValueError:
            logger.warning(f"[PROJECTION] aggregate_id {aggregate_id} is not an integer. Skip fleet_incidents projection.")
            pass

def get_event_store(db_conn):
    return EventStore(db_conn)
