"""
SERVER.python_ai_core.services.agentic_rag_service
==================================================
NATS Service Wrapper untuk Agentic RAG Engine.
Listens on subject: 'ai.engine.agentic_rag'
"""

import asyncio
import json
import logging
import os
import sys
import nats

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from engines.agentic_rag_engine import AgenticRAGEngine

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("AGENTIC_RAG_SERVICE")

import re

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")
_SAFE_NATS_URL = re.sub(r"://[^@]+@", "://***@", NATS_URL)


async def main():
    try:
        nc = await nats.connect(NATS_URL)
        logger.info(f"[AGENTIC_RAG_SERVICE] Connected to NATS at {_SAFE_NATS_URL}")
    except Exception as conn_err:
        logger.error(f"[AGENTIC_RAG_SERVICE] NATS connection failed: {conn_err}")
        return

    engine = AgenticRAGEngine()

    async def request_handler(msg):
        reply = msg.reply
        try:
            data = json.loads(msg.data.decode("utf-8"))
            query = data.get("query_text") or data.get("query") or data.get("incident_text") or ""
            device = data.get("device") or data.get("target_device") or ""
            site_id = data.get("site_id") or ""
            incident_id = data.get("incident_id") or ""
            severity = data.get("severity") or data.get("event_severity") or "INFO"

            logger.info(f"[AGENTIC_RAG_SERVICE] Processing query='{query}' device='{device}' severity='{severity}'")
            plan_dto = await engine.run_agentic_rag_async(
                query=query,
                device=device,
                site_id=site_id,
                incident_id=incident_id,
                severity=severity,
            )
            response = {"status": "success", "data": plan_dto.to_dict()}
        except Exception as e:
            logger.error(f"[AGENTIC_RAG_SERVICE] Error executing agentic RAG: {e}")
            response = {"status": "error", "error": str(e)}

        if reply:
            await nc.publish(reply, json.dumps(response).encode("utf-8"))

    await nc.subscribe("ai.engine.agentic_rag", queue="agentic-rag-group", cb=request_handler)
    logger.info("[AGENTIC_RAG_SERVICE] Active & listening on 'ai.engine.agentic_rag' (queue: agentic-rag-group).")

    while True:
        await asyncio.sleep(3600)


if __name__ == "__main__":
    asyncio.run(main())
