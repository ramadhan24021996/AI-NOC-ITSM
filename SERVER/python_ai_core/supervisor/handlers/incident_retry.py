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
                    # 1. Quarantine orphan incidents lacking a valid device_name to prevent zombie retry loops
                    cur.execute("""
                        UPDATE incident_states ist
                        SET status = 'ABANDONED_NO_DEVICE', last_updated = NOW()
                        FROM incidents i
                        WHERE ist.incident_id = i.incident_id
                          AND ist.status IN ('PENDING', 'TRIGGERED')
                          AND (i.device_name IS NULL OR TRIM(i.device_name) = '' OR LOWER(TRIM(i.device_name)) = 'none')
                    """)
                    # 2. Fetch valid stalled incidents within the last 24h
                    cur.execute("""
                        SELECT i.incident_id, i.device_name, i.evidence 
                        FROM incidents i
                        JOIN incident_states ist ON i.incident_id = ist.incident_id
                        WHERE ist.status IN ('PENDING', 'TRIGGERED')
                          AND i.device_name IS NOT NULL
                          AND TRIM(i.device_name) != ''
                          AND LOWER(TRIM(i.device_name)) != 'none'
                          AND i.timestamp < NOW() - INTERVAL '5 minutes'
                          AND i.timestamp > NOW() - INTERVAL '24 hours'
                        ORDER BY i.timestamp DESC LIMIT 5
                    """)
                    rows = cur.fetchall()
                    if rows and nc_client is not None:
                        inc_ids = [r[0] for r in rows]
                        cur.execute(
                            "UPDATE incident_states SET status = 'ANALYZING', last_updated = NOW() WHERE incident_id = ANY(%s)",
                            (inc_ids,)
                        )
                    db.conn.commit()
                    return rows
            
            pending = await asyncio.to_thread(_fetch_pending)
            for row in pending:
                inc_id, device, evidence = row
                if not nc_client:
                    logger.debug(f"[SCHEDULER RETRY] Skipping retry for Incident ID {inc_id}: NATS client not bound")
                    continue
                logger.warning(f"[SCHEDULER RETRY] Retrying AI Consensus for Incident ID {inc_id} on {device}")
                payload = {
                    "agent": device,
                    "flag": "RETRY_TRIGGER",
                    "evidence": evidence,
                    "incident_id": inc_id,
                    "status": "RETRY",
                    "pc_name": device
                }
                await nc_client.publish("telemetry.site.global.critical", json.dumps(payload).encode())
        except Exception as db_err:
            logger.error(f"[SCHEDULER RETRY] Error in DB query: {db_err}")
        finally:
            if db and db.conn:
                db.close()
    except Exception as e:
        logger.error(f"[SCHEDULER RETRY] Exception: {e}")
