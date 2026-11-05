"""
supervisor/handlers/incident_reanalyze.py
------------------------------------------
Stale Incident Re-evaluation & Dynamic Re-analysis Pipeline.
"""
import asyncio
import json
import logging
import os
import sys

logger = logging.getLogger("AI_SUPERVISOR.incident_reanalyze")


class syntheticMsg:
    def __init__(self, data: bytes, subject: str = ""):
        self.data = data
        self.subject = subject

    async def ack(self):
        pass


async def reanalyze_handler(msg, message_handler_fn=None):
    try:
        payload = json.loads(msg.data.decode())
        incident_id = payload.get("incident_id")
        if not incident_id:
            return
        logger.info(f"[REANALYZE] Triggered for incident {incident_id}")
        
        from engines.rag_engine import get_rag_engine
        db = get_rag_engine()
        db.connect()
        if not db.conn:
            return
        raw_data = None
        with db.conn.cursor() as cur:
            cur.execute("SELECT raw_data FROM incidents WHERE incident_id::text = %s", (str(incident_id),))
            row = cur.fetchone()
            if row and row[0]:
                raw_data = row[0]
            else:
                cur.execute("SELECT pc_name, severity, description FROM fleet_incidents WHERE incident_id::text = %s", (str(incident_id),))
                frow = cur.fetchone()
                if frow:
                    pc_name, severity, description = frow
                    raw_data = {
                        "agent": pc_name or "System",
                        "flag": f"{severity}_ALERT",
                        "evidence": description or "Fleet Watchdog Alert",
                        "incident_id": str(incident_id),
                        "status": "RETRY"
                    }
        db.close()
        
        if raw_data:
            if isinstance(raw_data, str):
                try:
                    raw_data = json.loads(raw_data)
                except:
                    import logging; logging.getLogger(__name__).debug('_ = None suppressed')
            if isinstance(raw_data, dict):
                raw_data["incident_id"] = incident_id
                synthetic_msg = syntheticMsg(json.dumps(raw_data).encode(), subject="incident.reanalyze")
                
                if message_handler_fn is None:
                    from supervisor.handlers.incident_triage import message_handler
                    message_handler_fn = message_handler
                    
                await message_handler_fn(synthetic_msg)
                logger.info(f"[REANALYZE] Re-analysis completed for {incident_id}")
    except Exception as e:
        logger.error(f"[REANALYZE] Failed: {e}")
