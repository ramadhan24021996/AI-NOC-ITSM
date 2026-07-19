"""
Enterprise Autonomous AI OS — Phase 6: Step 6.3
AI Health Monitor Service

Menyediakan API internal untuk AI OS health metrics:
  - Runtime states semua workers
  - Meta-cognition statistics
  - Knowledge freshness summary
  - Learning queue depth
  - Evolution proposals
  - System audit status

Dikonsumsi oleh Dashboard Server via NATS Request-Reply:
  Subject: "ai.health.status"
  Subject: "ai.health.cognition"
  Subject: "ai.health.knowledge"
  Subject: "ai.health.evolution"
"""

import asyncio
import json
import logging
import os

import nats

logger = logging.getLogger("AI_HEALTH_MONITOR")

NATS_URL = os.getenv("NATS_URL", "nats://nats:4222")
DB_HOST  = os.getenv("DB_HOST",  "postgres")
DB_PORT  = os.getenv("DB_PORT",  "5432")
DB_NAME  = os.getenv("DB_NAME",  "osi_system")
DB_USER  = os.getenv("DB_USER",  "postgres")
DB_PASS  = os.getenv("DB_PASSWORD", "postgres")


def _get_db():
    import psycopg2
    return psycopg2.connect(
        host=DB_HOST, port=DB_PORT, database=DB_NAME,
        user=DB_USER, password=DB_PASS
    )


async def handle_health_status(msg):
    """Worker runtime states from Redis."""
    try:
        from runtime.ai_runtime_state import AIRuntimeRegistry
        states = AIRuntimeRegistry.get_all_worker_states()
        events = AIRuntimeRegistry.get_recent_events(limit=10)
        await msg.respond(json.dumps({
            "status":  "ok",
            "workers": states,
            "recent_events": events,
        }).encode())
    except Exception as e:
        await msg.respond(json.dumps({"status": "error", "error": str(e)}).encode())


async def handle_cognition_metrics(msg):
    """Meta-cognition statistics."""
    try:
        conn = _get_db()
        from cognition.meta_cognition import MetaCognitionLayer
        mc = MetaCognitionLayer(db_conn=conn)
        metrics = mc.get_recent_metrics(limit=20)
        hallucination_rate = mc.get_hallucination_rate(last_n_days=7)
        conn.close()
        await msg.respond(json.dumps({
            "status":           "ok",
            "recent":           metrics,
            "hallucination_pct_7d": hallucination_rate,
        }).encode())
    except Exception as e:
        await msg.respond(json.dumps({"status": "error", "error": str(e)}).encode())


async def handle_knowledge_health(msg):
    """Knowledge freshness and gap report."""
    try:
        conn = _get_db()
        from knowledge.knowledge_fabric import KnowledgeFabric
        fabric = KnowledgeFabric(db_conn=conn)
        freshness = fabric.get_freshness_report()
        gaps = fabric.find_knowledge_gaps()
        conn.close()
        await msg.respond(json.dumps({
            "status":   "ok",
            "freshness": freshness,
            "gaps":      gaps[:10],
        }).encode())
    except Exception as e:
        await msg.respond(json.dumps({"status": "error", "error": str(e)}).encode())


async def handle_evolution_proposals(msg):
    """Pending evolution proposals."""
    try:
        conn = _get_db()
        from evolution.evolution_engine import EvolutionEngine
        engine = EvolutionEngine(db_conn=conn)
        proposals = engine.get_pending_proposals()
        conn.close()
        await msg.respond(json.dumps({
            "status":    "ok",
            "proposals": proposals,
        }).encode())
    except Exception as e:
        await msg.respond(json.dumps({"status": "error", "error": str(e)}).encode())


async def handle_goals(msg):
    """Active AI goals and progress."""
    try:
        conn = _get_db()
        from planning.goal_engine import GoalEngine
        ge = GoalEngine(db_conn=conn)
        goals = ge.get_active_goals()
        conn.close()
        await msg.respond(json.dumps({
            "status": "ok",
            "goals":  goals,
        }).encode())
    except Exception as e:
        await msg.respond(json.dumps({"status": "error", "error": str(e)}).encode())


async def handle_world_summary(msg):
    """Infrastructure world model summary."""
    try:
        conn = _get_db()
        from knowledge.world_model import WorldModel
        wm = WorldModel(db_conn=conn)
        summary = wm.get_infrastructure_summary()
        conn.close()
        await msg.respond(json.dumps({
            "status": "ok",
            "infrastructure": summary,
        }).encode())
    except Exception as e:
        await msg.respond(json.dumps({"status": "error", "error": str(e)}).encode())


async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger.info("[AI_HEALTH_MONITOR] Starting service, connecting to NATS at %s", NATS_URL)

    nc = await nats.connect(NATS_URL, max_reconnect_attempts=20, reconnect_time_wait=5)

    await nc.subscribe("ai.health.status",       cb=handle_health_status)
    await nc.subscribe("ai.health.cognition",    cb=handle_cognition_metrics)
    await nc.subscribe("ai.health.knowledge",    cb=handle_knowledge_health)
    await nc.subscribe("ai.health.evolution",    cb=handle_evolution_proposals)
    await nc.subscribe("ai.health.goals",        cb=handle_goals)
    await nc.subscribe("ai.health.world",        cb=handle_world_summary)

    logger.info("[AI_HEALTH_MONITOR] Subscribed to ai.health.* subjects")

    try:
        while True:
            await asyncio.sleep(1)
    finally:
        await nc.close()


if __name__ == "__main__":
    asyncio.run(main())
