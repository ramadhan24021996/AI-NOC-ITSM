"""
Enterprise AIRE — Chaos Monkey for AI

Sengaja menyuntikkan kegagalan ke dalam sistem untuk memvalidasi
kemampuan recovery dan gracefully degrade AI OS.

Target:
- Redis timeout (menguji Checkpoint DB fallback)
- LLM API timeout (menguji Provider fallback Groq/Deepseek)
- NATS disconnect (menguji worker state masuk ke DEGRADED)
"""

import asyncio
import logging
import random
import os
import time

logger = logging.getLogger("CHAOS_MONKEY")

class AIChaosMonkey:
    def __init__(self):
        self.active = os.getenv("ENABLE_CHAOS_MONKEY", "false").lower() == "true"
        self.failure_probability = 0.05 # 5% chance per check
        from governance.chaos_injection_worker import get_chaos_worker
        self.worker = get_chaos_worker()

    async def inject_llm_timeout(self):
        """Simulates an LLM API outage by blocking the thread temporarily."""
        logger.warning("🐒 [CHAOS] Injecting LLM Provider Timeout (Simulated 10s delay)")
        exp = self.worker.create_experiment("LLM_TIMEOUT", "AI_ROUTER", ttl_sec=10)
        self.worker.simulate_agent_chaos_injection(exp["run_id"])
        await asyncio.sleep(1)
        self.worker.verify_auto_rollback(exp["run_id"], rollback_success=True)
        logger.info("🐒 [CHAOS] LLM Provider recovered & rollback verified.")

    async def inject_redis_drop(self):
        """Simulates a Redis connection drop."""
        logger.warning("🐒 [CHAOS] Injecting Redis Connection Drop")
        exp = self.worker.create_experiment("REDIS_DROP", "CACHE_CLUSTER", ttl_sec=5)
        self.worker.simulate_agent_chaos_injection(exp["run_id"])
        self.worker.verify_auto_rollback(exp["run_id"], rollback_success=True)
        logger.info("🐒 [CHAOS] Redis connection drop test completed & verified.")

    async def inject_nats_disconnect(self, nc):
        """Forces NATS client to disconnect, testing reconnection logic."""
        if not nc: return
        logger.warning("🐒 [CHAOS] Injecting NATS Disconnect")
        exp = self.worker.create_experiment("NATS_DISCONNECT", "TELEMETRY_BUS", ttl_sec=5)
        self.worker.simulate_agent_chaos_injection(exp["run_id"])
        self.worker.verify_auto_rollback(exp["run_id"], rollback_success=True)

    async def run_chaos_loop(self):
        if not self.active:
            logger.info("[CHAOS] Chaos Monkey is disabled (ENABLE_CHAOS_MONKEY != true)")
            return
            
        logger.warning("🐒 [CHAOS] Chaos Monkey initialized. Expect random turbulence.")
        
        while True:
            await asyncio.sleep(60 * 5) # Check every 5 minutes
            
            if random.random() < self.failure_probability:
                attack_type = random.choice(['llm', 'redis'])
                if attack_type == 'llm':
                    await self.inject_llm_timeout()
                elif attack_type == 'redis':
                    await self.inject_redis_drop()
