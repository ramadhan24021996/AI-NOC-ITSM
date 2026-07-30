import asyncio
import json
import logging
import os
import sys
import nats

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from rag_engine import RAGEngine

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("RAG_SERVICE")

NATS_URL = os.environ.get("NATS_URL", "nats://nats:4222")

async def main():
    nc = await nats.connect(NATS_URL)
    logger.info(f"Connected to NATS at {NATS_URL}.")

    engine = RAGEngine()
    engine.connect()

    async def request_handler(msg):
        subject = msg.subject
        reply = msg.reply
        try:
            data = json.loads(msg.data.decode())
            logger.info("Processing RAG query for similar incidents...")
            
            # Ensure DB connection is active
            if not engine.conn or engine.conn.closed:
                engine.connect()

            query_text = data.get("incident_text") or data.get("symptoms") or data.get("title") or data.get("description") or ""
            if not query_text and data.get("embedding_vector"):
                # Direct vector query
                results = engine.query_similar_incidents(
                    embedding_vector=data.get("embedding_vector"),
                    limit=data.get("limit", 3)
                )
                response = {"status": "success", "results": results}
            else:
                if not query_text:
                    query_text = json.dumps(data)
                result_data = engine.embed_and_query(
                    incident_text=query_text,
                    limit=data.get("limit", 3)
                )
                response = {
                    "status": "success",
                    "results": result_data["results"],
                    "embedding_vector": result_data["embedding_vector"],
                    "metadata": result_data["metadata"]
                }
        except Exception as e:
            logger.error(f"Error processing RAG request: {e}")
            response = {"status": "error", "error": str(e)}

        await nc.publish(reply, json.dumps(response).encode())

    # Subscribe to target subject with queue group
    await nc.subscribe("ai.engine.rag", queue="rag-service-group", cb=request_handler)
    logger.info("RAG Service is active and listening on 'ai.engine.rag' (group: rag-service-group).")

    while True:
        await asyncio.sleep(3600)

if __name__ == '__main__':
    asyncio.run(main())
