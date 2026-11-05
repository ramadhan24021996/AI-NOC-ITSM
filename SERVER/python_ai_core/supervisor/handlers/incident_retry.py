"""
supervisor/handlers/incident_retry.py
-------------------------------------
Automated Retry Handler and Pending Task Poller.
"""
import asyncio
import json
import logging
import os
import sys

logger = logging.getLogger("AI_SUPERVISOR.incident_retry")


async def ai_retry_handler(msg, nc_client=None):
    try:
        from engines.rag_engine import get_rag_engine
    except ImportError:
        from SERVER.python_ai_core.engines.rag_engine import get_rag_engine
    try:
        db = get_rag_engine()
        db.connect()
        if not db.conn:
            return
        try:
            def _fetch_pending():
                if not (db and db.conn):
                    return []
                with db.conn.cursor() as cur:
                    cur.execute("""
                        SELECT i.incident_id, i.device_name, i.evidence 
                        FROM incidents i
                        JOIN incident_states ist ON i.incident_id = ist.incident_id
                        WHERE ist.status IN ('PENDING', 'TRIGGERED') AND i.timestamp < NOW() - INTERVAL '5 minutes'
                        ORDER BY i.timestamp DESC LIMIT 5
                    """)
                    return cur.fetchall()
            
            pending = await asyncio.to_thread(_fetch_pending)
            for row in pending:
                inc_id, device, evidence = row
                logger.warning(f"[SCHEDULER RETRY] Retrying AI Consensus for Incident ID {inc_id} on {device}")
                payload = {
                    "agent": device,
                    "flag": "RETRY_TRIGGER",
                    "evidence": evidence,
                    "incident_id": inc_id,
                    "status": "RETRY",
                    "pc_name": device
                }
                if nc_client:
                    await nc_client.publish(f"telemetry.site.global.critical", json.dumps(payload).encode())
        except Exception as db_err:
            logger.error(f"[SCHEDULER RETRY] Error in DB query: {db_err}")
        finally:
            if db and db.conn:
                db.close()
    except Exception as e:
        logger.error(f"[SCHEDULER RETRY] Exception: {e}")
