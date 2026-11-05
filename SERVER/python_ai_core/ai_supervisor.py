"""
Enterprise AI OS — AI Supervisor (Refactored Modular Architecture)
Sprint: Architectural Debt Resolution (100% Modular Supervisor)

This module serves as the primary entry point for the AI Supervisor.
All business logic, handlers, and persistence helpers have been refactored
into single-responsibility sub-modules under the `supervisor/` package:

  - supervisor.core             : Runtime State, Config Utilities, Timestamp Parser
  - supervisor.nats_bridge        : Isolated NATS Connection, Streams & Messaging
  - supervisor.dispatcher         : Circuit-breaker wrapped Engine Execution
  - supervisor.pipeline_logger    : AI Audit Trail & Event Sourcing Persistence
  - supervisor.handlers.incident_handler : Telemetry Reasoning & Learning Handlers
  - supervisor.handlers.approval_handler : HITL Approval, Escalation & Verification
  - supervisor.handlers.background_loops: Daemon Loops (World Model, Retention, etc.)
"""

import asyncio
import json
import logging
import os
import sys

# ── Import public symbols from supervisor package for backward compatibility ──
from supervisor import (
    NATS_URL,
    NATSBridge,
    set_runtime_state,
    parse_rfc3339_or_unix,
    get_active_recovery_mode,
    get_active_consensus_pattern,
    log_ai_pipeline,
    log_event_sourced,
    execute_validated_llm,
    message_handler,
    learning_handler,
    reanalyze_handler,
    ai_retry_handler,
    handle_escalate_request,
    handle_approval_decision,
    run_background_verification,
    verification_handler,
    chat_compaction_handler,
    apply_incident_transition,
    autonomous_data_retention,
    heartbeat_loop,
    trust_evaluator_loop,
    sync_human_rejections_loop,
    world_model_loop_async,
    predictive_loop_async,
)

from nats.js.api import ConsumerConfig, AckPolicy, DeliverPolicy
from agents.incident_agent import IncidentAgent
from agents.security_agent import SecurityAgent
from agents.recovery_agent import RecoveryAgent
from agents.verification_agent import VerificationAgent
from engines.escalation_engine import AutoEscalationEngine
from engines.closure_engine import ClosureEnforcementEngine
from daemons.presence_daemon import OperatorPresenceEngine
from engines.blast_radius_engine import BlastRadiusEngine
from engines.replay_engine import ReplaySimulationEngine
from telemetry import telemetry

logger = logging.getLogger("AI_SUPERVISOR")


async def main():
    import re as _re
    _masked_nats = _re.sub(r"://[^@]+@", "://***@", str(NATS_URL))
    logger.info(f"Initializing AI Supervisor (Modular Architecture) - Connecting to NATS at {_masked_nats}...")

    # ── AI OS: Signal INITIALIZING ───────────────────────────────────────────
    set_runtime_state("INITIALIZING")

    try:
        bridge = NATSBridge()
        nc = await bridge.connect()
        js = bridge.js
        telemetry.nc = nc  # Bind Telemetry to NATS Adapter proxy
        set_runtime_state("SYNCING")

        # ── Start Autonomous Daemons ───────────────────────────────────────────
        asyncio.create_task(autonomous_data_retention())
        
        try:
            from api.rest_api_server import RestApiServer
            rest_server = RestApiServer(host="0.0.0.0", port=8088)
            rest_server.start_background()
        except Exception as rest_err:
            logger.error(f"[STARTUP] Failed to start RestApiServer: {rest_err}")

        # ── Preheat Embeddings Cache ──────────────────────────────────────────
        try:
            from engines.rag_engine import get_rag_engine
            from core.cache_manager import get_cache_manager
            temp_rag = get_rag_engine()
            temp_rag.connect()
            if temp_rag.conn:
                cache_mgr = get_cache_manager()
                preheated_count = cache_mgr.preheat_embeddings(temp_rag.conn)
                logger.info(f"[STARTUP] Preheated {preheated_count} knowledge vectors into Redis.")
                temp_rag.close()
        except Exception as preheat_err:
            logger.error(f"[STARTUP] Failed to preheat embeddings: {preheat_err}")

        # ── Start Isolated Autonomous Agents ─────────────────────────────────
        incident_agent = IncidentAgent(nc)
        security_agent = SecurityAgent(nc)
        recovery_agent = RecoveryAgent(nc)
        verification_agent = VerificationAgent(nc)

        await incident_agent.start()
        await security_agent.start()
        await recovery_agent.start()
        await verification_agent.start()

        # ── Phase 3-6 Cognitive Modules Initialization ─────────────────────────
        try:
            from knowledge.world_model import WorldModel
            from knowledge.knowledge_fabric import KnowledgeFabric
            from planning.goal_engine import GoalEngine
            from planning.decision_engine import DecisionEngine
            from evolution.evolution_engine import EvolutionEngine
            from evolution.arch_auditor import ArchAuditor

            world_model = WorldModel()
            knowledge_fabric = KnowledgeFabric()
            goal_engine = GoalEngine()
            decision_engine = DecisionEngine()
            evolution_engine = EvolutionEngine()
            arch_auditor = ArchAuditor()

            logger.info("[STARTUP] Phase 3-6 Cognitive Modules initialized successfully.")
        except Exception as cog_init_err:
            logger.warning(f"[STARTUP] Phase 3-6 Cognitive Modules not fully loaded: {cog_init_err}")

        # ── Setup JetStream Streams ────────────────────────────────────────────
        await bridge.ensure_stream(
            name="telemetry_stream_critical",
            subjects=["telemetry.critical", "telemetry.site.>", "telemetry.netdata"]
        )

        # ── Wrap handlers to bind nc ───────────────────────────────────────────
        async def _bound_msg_handler(msg):
            await message_handler(msg)

        async def _bound_escalate_handler(msg):
            await handle_escalate_request(nc, msg)

        async def _bound_approval_handler(msg):
            await handle_approval_decision(nc, msg)

        async def _bound_compact_handler(msg):
            await chat_compaction_handler(nc, msg)

        async def _bound_retry_handler(msg):
            await ai_retry_handler(msg, nc_client=nc)

        async def _bound_verify_handler(msg):
            await verification_handler(nc, msg)

        async def _bound_reanalyze_handler(msg):
            await reanalyze_handler(msg)

        # ── Subscriptions ─────────────────────────────────────────────────────
        active_subscriptions = {}

        async def subscribe_to_site(site_id):
            clean_site = site_id.lower().strip().replace(".", "_").replace(" ", "_")
            if clean_site in active_subscriptions:
                return

            subject = f"telemetry.site.{clean_site}.critical"
            durable_name = f"ai_supervisor_consumer_{clean_site}"

            config = ConsumerConfig(
                durable_name=durable_name,
                ack_policy=AckPolicy.EXPLICIT,
                max_deliver=5,
                max_ack_pending=128,
                deliver_policy=DeliverPolicy.ALL
            )

            try:
                sub = await js.subscribe(
                    subject,
                    durable=durable_name,
                    config=config,
                    cb=_bound_msg_handler
                )
                active_subscriptions[clean_site] = sub
                logger.info(f"[PARTITION ENGINE] Subscribed to '{subject}' with durable '{durable_name}'.")
            except Exception as sub_err:
                logger.error(f"[PARTITION ENGINE] Failed to subscribe to site {clean_site}: {sub_err}")

        # Legacy & Netdata telemetry subscriptions
        try:
            legacy_config = ConsumerConfig(
                durable_name="ai_supervisor_consumer_legacy",
                ack_policy=AckPolicy.EXPLICIT,
                max_deliver=5,
                max_ack_pending=128,
                deliver_policy=DeliverPolicy.ALL
            )
            legacy_sub = await js.subscribe("telemetry.critical", durable="ai_supervisor_consumer_legacy", config=legacy_config, cb=_bound_msg_handler)
            active_subscriptions["legacy"] = legacy_sub
        except Exception as legacy_err:
            logger.error(f"[PARTITION ENGINE] Failed legacy sub: {legacy_err}")

        try:
            netdata_config = ConsumerConfig(
                durable_name="ai_supervisor_consumer_netdata",
                ack_policy=AckPolicy.EXPLICIT,
                max_deliver=5,
                max_ack_pending=128,
                deliver_policy=DeliverPolicy.ALL
            )
            netdata_sub = await js.subscribe("telemetry.netdata", durable="ai_supervisor_consumer_netdata", config=netdata_config, cb=_bound_msg_handler)
            active_subscriptions["netdata"] = netdata_sub
        except Exception as netdata_err:
            logger.error(f"[PARTITION ENGINE] Failed netdata sub: {netdata_err}")

        await subscribe_to_site("global")

        # Dynamic site polling loop
        def dynamic_site_polling_loop_sync():
            from engines.rag_engine import get_rag_engine
            db = None
            try:
                db = get_rag_engine()
                db.connect()
                if db.conn:
                    with db.conn.cursor() as cur:
                        cur.execute("SELECT site_id FROM fleet_sites")
                        return [row[0] for row in cur.fetchall()]
            except Exception as loop_err:
                logger.error(f"[PARTITION ENGINE] DB polling failed: {loop_err}")
            finally:
                if db and db.conn:
                    try:
                        db.close()
                    except Exception:
                        pass
            return []

        async def dynamic_site_polling_loop_async():
            while True:
                db_sites = await asyncio.to_thread(dynamic_site_polling_loop_sync)
                for site in db_sites:
                    if site:
                        await subscribe_to_site(site)
                await asyncio.sleep(10)

        asyncio.create_task(dynamic_site_polling_loop_async())

        # Learning subscriber
        await nc.subscribe("rag.learn", queue="ai-learning-group", cb=learning_handler)
        logger.info("Subscribed to 'rag.learn' for dynamic Knowledge learning.")

        # Re-analyze subscriber
        await nc.subscribe("incident.reanalyze", queue="ai-reanalyze-group", cb=_bound_reanalyze_handler)

        # Escalation & Approval subscribers
        await nc.subscribe("incident.site.*.escalate.request", queue="escalate-engine-group", cb=_bound_escalate_handler)
        await nc.subscribe("approval.decision", queue="approval-engine-group", cb=_bound_approval_handler)

        # Chat Compaction & AI Retry subscribers
        await nc.subscribe("chat.compact", queue="chat-compactor-group", cb=_bound_compact_handler)
        await nc.subscribe("scheduler.ai.retry", queue="ai-retry-group", cb=_bound_retry_handler)

        # Verification scheduler subscriber
        await nc.subscribe("scheduler.verification", queue="verification-scheduler-group", cb=_bound_verify_handler)

        # ── Start Background Daemon Loops ─────────────────────────────────────
        asyncio.create_task(heartbeat_loop(nc))
        asyncio.create_task(trust_evaluator_loop())
        asyncio.create_task(sync_human_rejections_loop())
        asyncio.create_task(world_model_loop_async())
        asyncio.create_task(predictive_loop_async())

        # Start engines
        escalation_engine = AutoEscalationEngine(nc=nc, interval_sec=60)
        asyncio.create_task(escalation_engine.start())

        closure_engine = ClosureEnforcementEngine()
        await nc.subscribe("incident.site.*.close.request", queue="closure-engine-group", cb=closure_engine.handle_close_request)

        presence_engine = OperatorPresenceEngine(nc=nc, interval_sec=10)
        await presence_engine.start()

        blast_engine = BlastRadiusEngine(nc=nc)
        await blast_engine.start()

        replay_engine = ReplaySimulationEngine(nc=nc)
        await replay_engine.start()

        # Recovery Orchestrator & Post Verification Workers
        try:
            from engines.rag_engine import get_rag_engine
            db = get_rag_engine()
            db.connect()
            if db.conn:
                from governance.execution_orchestrator import GovernanceExecutionOrchestrator
                from governance.recovery_worker import RecoveryOrchestrator
                from verification.post_verification_engine import PostVerificationEngine

                orchestrator = GovernanceExecutionOrchestrator(nc, db.conn)
                recovery_worker = RecoveryOrchestrator(nc, db.conn, orchestrator)
                asyncio.create_task(recovery_worker.start_background_tasks())

                post_verification_engine = PostVerificationEngine(nc, db.conn)
                asyncio.create_task(post_verification_engine.start())
        except Exception as worker_err:
            logger.error(f"[WORKER INIT] Failed starting Recovery/Verification Workers: {worker_err}")

        set_runtime_state("READY")
        logger.info("[AI SUPERVISOR] Ready and actively processing events.")

        while True:
            await asyncio.sleep(1)

    except Exception as e:
        logger.error(f"NATS connection or runner exception: {e}")
        await asyncio.sleep(5)


if __name__ == "__main__":
    asyncio.run(main())
