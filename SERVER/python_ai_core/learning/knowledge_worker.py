"""
Enterprise Autonomous AI OS — Phase 3: Step 3.3
Knowledge Worker Daemon

Background service yang mendengarkan antrian pembelajaran dari NATS
dan memproses pengetahuan baru (parsing, embedding, penyimpanan DRAFT).

NATS Subject: learning.knowledge.ingest
Payload: {"source": "RFC|VENDOR_DOC|INCIDENT|OPERATOR", "url": "...", "topic": "...", "content": "..."}

Pipeline:
  Receive -> Validate -> Embed -> Store DRAFT -> Notify -> Done
"""

import asyncio
import json
import logging
import os
import time
import uuid
from typing import Dict, Any, Optional

import nats

from cognition.osi_taxonomy import classify_incident_layer
try:
    from shared.db_pool import PGConnection
except ImportError:
    from SERVER.shared.db_pool import PGConnection

logger = logging.getLogger("KNOWLEDGE_WORKER")

NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
DB_HOST  = os.getenv("DB_HOST",  "postgres")
DB_PORT  = os.getenv("DB_PORT",  "5432")
DB_NAME  = os.getenv("DB_NAME",  "osi_system")
DB_USER  = os.getenv("DB_USER",  "postgres")
DB_PASS  = os.getenv("DB_PASSWORD", "")


def _get_db():
    return PGConnection()


def _generate_embedding(text: str) -> list:
    """Generate 768-dim embedding via decrypted multi-key LLMRouter. Falls back to deterministic TF-IDF vector."""
    try:
        try:
            from engines.llm_router import get_router
        except ImportError:
            from SERVER.python_ai_core.engines.llm_router import get_router
        emb = get_router().embed_text_768(text)
        if emb and len(emb) == 768:
            return emb
    except Exception as e:
        logger.debug("[KNOWLEDGE_WORKER] Gemini embedding via router unavailable: %s", e)

    try:
        try:
            from engines.rag_engine import get_rag_engine
        except ImportError:
            from SERVER.python_ai_core.engines.rag_engine import get_rag_engine
        return get_rag_engine()._local_embedding_fallback(text)
    except Exception:
        return [0.0] * 768


def _store_draft_knowledge(conn, topic: str, content: str, embedding: list,
                            source_type: str, source_url: str, tags: Optional[list] = None) -> str:
    """
    Store a new DRAFT knowledge vector in knowledge_vectors and record provenance.
    Returns the new vector_id.
    """
    import uuid
    vector_id = str(uuid.uuid4())
    
    with conn.cursor() as cur:
        cur.execute("""
            INSERT INTO knowledge_vectors
                (incident_id, title, symptoms, root_cause, resolution, embedding, tags, status, source_doc, freshness_score, last_validated, created_at)
            VALUES (%s, %s, %s, 'unknown', 'unknown', %s::vector, %s, 'DRAFT', %s, 1.0, NOW(), NOW())
            RETURNING incident_id
        """, (
            vector_id,
            topic,
            content,
            "[" + ",".join(str(v) for v in embedding) + "]",
            tags or ["auto_learned"],
            source_url or "unknown",
        ))
        returned_id = cur.fetchone()[0]

        # Record provenance
        cur.execute("""
            INSERT INTO knowledge_provenance
                (vector_id, source_type, source_url, ingested_by, status, created_at)
            VALUES (%s, %s, %s, 'knowledge_worker', 'DRAFT', NOW())
        """, (returned_id, source_type, source_url or ""))

    conn.commit()
    return returned_id


async def process_ingest_message(msg):
    """Handle a single learning.knowledge.ingest message."""
    data: Dict[str, Any] = {}
    conn = None
    try:
        data = json.loads(msg.data.decode())
        topic       = data.get("topic", "unknown")
        content     = data.get("content", "")
        source_type = data.get("source", "OPERATOR")
        source_url  = data.get("url", "")

        if not content or len(content) < 10:
            logger.warning("[KNOWLEDGE_WORKER] Skipping empty/short content for topic: %s", topic)
            await msg.ack()
            return

        logger.info("[KNOWLEDGE_WORKER] Processing knowledge: topic=%s source=%s", topic, source_type)

        # 1. Embed
        embedding = _generate_embedding(f"{topic}: {content}")

        # 1.5 Classify OSI Layer — uses probabilistic EnterpriseLayerProfile
        layer_profile = classify_incident_layer(topic + " " + content)
        primary_layer = getattr(layer_profile, "primary_layer", 7)
        primary_name = getattr(layer_profile, "primary_name", "Application")
        secondary_layers = getattr(layer_profile, "secondary_layers", [])
        conf_score = getattr(layer_profile, "confidence_score", 0.5)
        tags = [f"L{primary_layer}_{str(primary_name).upper().replace(' ', '_')}"]
        for sl in secondary_layers:
            from cognition.osi_taxonomy import OSI_LAYERS
            sl_name = OSI_LAYERS.get(sl, {}).get("name", f"L{sl}").upper().replace(" ", "_")
            tags.append(f"L{sl}_{sl_name}")
        logger.info(
            "[KNOWLEDGE_WORKER] OSI Profile: primary=L%s confidence=%.0f%% tags=%s",
            primary_layer, float(conf_score) * 100.0, tags
        )

        # 2. Check for duplicates via Cosine Distance (< 0.15 distance == > 0.85 similarity)
        embedding_str = "[" + ",".join(str(v) for v in embedding) + "]"
        is_duplicate = False
        with PGConnection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    SELECT incident_id, (embedding <=> %s::vector) as distance
                    FROM knowledge_vectors
                    WHERE embedding IS NOT NULL
                    ORDER BY embedding <=> %s::vector ASC
                    LIMIT 1
                """, (embedding_str, embedding_str))
                row = cur.fetchone()
                if row and row[1] < 0.15:  # Distance < 0.15 means Similarity > 0.85
                    is_duplicate = True
                    dup_id = row[0]
                    cur.execute("""
                        UPDATE knowledge_vectors
                        SET freshness_score = 1.0, last_validated = NOW()
                        WHERE incident_id = %s
                    """, (dup_id,))
                    conn.commit()
                    logger.info("[KNOWLEDGE_WORKER] Duplicate knowledge detected (similarity %.2f > 0.85). Refreshed vector_id=%s", 1.0 - row[1], dup_id)

            if not is_duplicate:
                # Store DRAFT
                vector_id = _store_draft_knowledge(conn, topic, content, embedding, source_type, source_url, tags)
                logger.info("[KNOWLEDGE_WORKER] Stored DRAFT vector_id=%s for topic='%s'", vector_id, topic)

        await msg.ack()

    except Exception as e:
        logger.error("[KNOWLEDGE_WORKER] Failed to process ingest: %s | data=%s", e, data)
        try:
            await msg.nak()
        except Exception:
            import logging; logging.getLogger(__name__).debug('_ = None suppressed')
    finally:
        pass


async def run_freshness_daemon(interval_hours: int = 6):
    """
    Background coroutine: periodically checks for stale knowledge vectors
    and marks them for revalidation.
    Staleness threshold: 30 days since last_validated or freshness_score < 0.3.
    """
    while True:
        try:
            with PGConnection() as conn:
                with conn.cursor() as cur:
                    cur.execute("""
                        UPDATE knowledge_vectors
                        SET freshness_score = GREATEST(0.0,
                            freshness_score - (
                                EXTRACT(DAY FROM (NOW() - last_validated)) / 30.0 * 0.2
                            )
                        )
                        WHERE status = 'GOLDEN'
                          AND last_validated < NOW() - INTERVAL '7 days'
                    """)
                    updated = cur.rowcount
                    if updated > 0:
                        logger.info("[FRESHNESS_DAEMON] Decayed freshness for %d stale vectors.", updated)
        except Exception as e:
            logger.warning("[FRESHNESS_DAEMON] Error: %s", e)

        await asyncio.sleep(interval_hours * 3600)


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger.info("[KNOWLEDGE_WORKER] Starting daemon, connecting to NATS at %s", NATS_URL)

    nc = await nats.connect(NATS_URL, max_reconnect_attempts=20, reconnect_time_wait=3)
    js = nc.jetstream()

    # Subscribe to learning queue
    try:
        await js.add_stream(name="learning_stream", subjects=["learning.>"])
        logger.info("[KNOWLEDGE_WORKER] JetStream 'learning_stream' initialized.")
    except Exception as e:
        logger.warning("[KNOWLEDGE_WORKER] Stream may already exist: %s", e)

    await js.subscribe("learning.knowledge.ingest", cb=process_ingest_message, durable="knowledge-worker")
    logger.info("[KNOWLEDGE_WORKER] Subscribed to learning.knowledge.ingest")

    # Start freshness daemon as background task
    asyncio.create_task(run_freshness_daemon(interval_hours=6))
    logger.info("[KNOWLEDGE_WORKER] Freshness daemon started (interval=6h)")

    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
