import logging
from datetime import datetime, timedelta

logger = logging.getLogger("APPROVAL_QUEUE")

class ApprovalQueue:
    def __init__(self, db_conn=None):
        self.db_conn = db_conn

    def enqueue_for_approval(self, incident_id: int, action_name: str, risk_level: str) -> int:
        if not self.db_conn:
            logger.warning("No database connection. Simulating approval enqueue.")
            return -1

        try:
            with self.db_conn.cursor() as cur:
                # Resolve incidents foreign key constraint safely
                if incident_id is None:
                    cur.execute("""
                        INSERT INTO incidents (device_name, layer, flag, evidence, confidence, rag_status)
                        VALUES (NULL, 1, 'HITL_GATE', 'Human approval required', 100.0, 'GREEN')
                        RETURNING incident_id
                    """)
                    row = cur.fetchone()
                    if row:
                        incident_id = row[0]
                else:
                    cur.execute("SELECT incident_id FROM incidents WHERE incident_id = %s", (incident_id,))
                    if not cur.fetchone():
                        try:
                            cur.execute("""
                                INSERT INTO incidents (incident_id, device_name, layer, flag, evidence, confidence, rag_status)
                                VALUES (%s, NULL, 1, 'HITL_GATE', 'Human approval required', 100.0, 'GREEN')
                            """, (incident_id,))
                        except Exception:
                            self.db_conn.rollback()
                            cur.execute("""
                                INSERT INTO incidents (device_name, layer, flag, evidence, confidence, rag_status)
                                VALUES (NULL, 1, 'HITL_GATE', 'Human approval required', 100.0, 'GREEN')
                                RETURNING incident_id
                            """)
                            row = cur.fetchone()
                            if row:
                                incident_id = row[0]
                
                expiry = datetime.utcnow() + timedelta(hours=1)
                
                cur.execute("""
                    INSERT INTO ai_approval_logs (incident_id, risk_level, action_name, approval_status, approval_expiry)
                    VALUES (%s, %s, %s, 'PENDING', %s)
                    RETURNING id
                """, (incident_id, risk_level, action_name, expiry))
                row = cur.fetchone()
                self.db_conn.commit()
                if row:
                    logger.info(f"Enqueued action '{action_name}' for Incident {incident_id} (ID: {row[0]}) in Approval Queue.")
                    return row[0]
        except Exception as e:
            logger.error(f"Failed to enqueue action for approval: {e}")
            if self.db_conn:
                self.db_conn.rollback()
        return -1

    def check_approval_status(self, approval_id: int) -> str:
        if not self.db_conn or approval_id == -1:
            return "PENDING"

        try:
            with self.db_conn.cursor() as cur:
                cur.execute("SELECT approval_status FROM ai_approval_logs WHERE id = %s", (approval_id,))
                row = cur.fetchone()
                if row:
                    return row[0]
        except Exception as e:
            logger.error(f"Failed to query approval status: {e}")
        return "PENDING"
