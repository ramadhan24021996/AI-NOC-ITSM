"""
Enterprise Autonomous AI OS — Day 2 Daemons Launcher
Starts all background processes for Evaluation, Governance, and Reliability.
"""

import asyncio
import logging
from verification.benchmark_engine import run_benchmark_daemon
from verification.chaos_monkey import AIChaosMonkey
from learning.curiosity_engine import daemon as curiosity_daemon
from evolution.arch_auditor import daemon as auditor_daemon
from services.ai_health_service import main as health_service_main
from learning.knowledge_worker import main as knowledge_worker_main
from evaluation.cognitive_kpi_engine import daemon as cognitive_kpi_daemon
from evaluation.baseline_builder import daemon as baseline_daemon
from evaluation.drift_detector import daemon as drift_daemon
from cognition.active_cognitive_engine import daemon_main as active_cognitive_daemon
from evaluation.timeline_kpi_engine import daemon as timeline_kpi_daemon
from cognition.enterprise_watch_officer import daemon_main as watch_officer_daemon
from services.planning_service import daemon as planning_daemon
from services.dlq_service import daemon as dlq_daemon
from services.multi_agent_service import daemon as multi_agent_daemon
from services.knowledge_graph_service import daemon as kg_daemon
from services.learning_plane_service import daemon as learning_plane_daemon
from daemons.observer_daemon import ActiveObserverDaemon

logger = logging.getLogger("AI_DAEMONS")

async def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
    logger.info("Starting all Day 2 AI Daemons (Evaluation, Governance, Chaos, 24/7 Active Observer)...")
    
    # Start 24/7 Active Proactive Observer Daemon
    observer = ActiveObserverDaemon()
    observer.start_247_daemon()
    
    # Start background scheduled tasks
    asyncio.create_task(run_benchmark_daemon(interval_hours=24))
    asyncio.create_task(curiosity_daemon(interval_hours=12))
    asyncio.create_task(auditor_daemon(interval_hours=6))
    asyncio.create_task(cognitive_kpi_daemon(interval_hours=12))
    asyncio.create_task(baseline_daemon(interval_hours=24))
    asyncio.create_task(drift_daemon(interval_hours=24))
    asyncio.create_task(timeline_kpi_daemon(interval_seconds=60))
    
    # Start Sprint K+ Active Cognitive Engine
    asyncio.create_task(active_cognitive_daemon())
    
    # Start Sprint N: Enterprise Watch Officer (berjalan setiap 60 detik)
    asyncio.create_task(watch_officer_daemon(interval_seconds=60))
    
    # Start Chaos Monkey (if ENABLE_CHAOS_MONKEY=true)
    chaos = AIChaosMonkey()
    asyncio.create_task(chaos.run_chaos_loop())
    
    # Start JetStream consumers
    asyncio.create_task(knowledge_worker_main())
    
    # Start Sprint 3 Planning Service inside daemon
    asyncio.create_task(planning_daemon())
    
    # Start DLQ Daemon (Sprint P4)
    asyncio.create_task(dlq_daemon())
    
    # Start Tahap 4: Multi-Agent Debate Daemon
    asyncio.create_task(multi_agent_daemon())
    
    # Start Tahap 6: Knowledge Graph Daemon
    asyncio.create_task(kg_daemon())
    
    # Start Tahap 8: Learning Plane Daemon
    asyncio.create_task(learning_plane_daemon(interval_hours=24))
    
    # Start Health NATS Responder (blocks main thread)
    await health_service_main()

if __name__ == "__main__":
    asyncio.run(main())
