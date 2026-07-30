import asyncio
import json
import logging
import time
from datetime import datetime, timezone
import uuid

import redis

logger = logging.getLogger("RECOVERY_WORKER")

class RecoveryOrchestrator:
    def __init__(self, nc, db_conn, orchestrator):
        """
        Initializes the Recovery Orchestrator (Offline Queue Worker).
        :param nc: NATS connection
        :param db_conn: psycopg2 Database Connection
        :param orchestrator: GovernanceExecutionOrchestrator instance
        """
        self.nc = nc
        self.conn = db_conn
        self.orchestrator = orchestrator
        
        import os
        redis_host = os.environ.get("REDIS_HOST", "redis")
        redis_port = int(os.environ.get("REDIS_PORT", "6379"))
        redis_password = os.environ.get("REDIS_PASSWORD")
        self.redis_client = redis.Redis(
            host=redis_host,
            port=redis_port,
            db=0,
            password=redis_password,
            decode_responses=True,
            socket_connect_timeout=2,
            protocol=2
        )

    async def start_background_tasks(self):
        # 1. Listen for heartbeats to trigger immediate queue pop for a specific agent
        if self.nc:
            await self.nc.subscribe("agent.status.site.>", cb=self._on_agent_heartbeat)
            logger.info("[RECOVERY WORKER] Subscribed to heartbeats for immediate recovery trigger.")
        
        # 2. Run the retry scheduler loop
        asyncio.create_task(self._retry_scheduler_loop())
        logger.info("[RECOVERY WORKER] Started Recovery Orchestrator background tasks.")

    async def _on_agent_heartbeat(self, msg):
        try:
            payload = json.loads(msg.data.decode())
            agent_id = payload.get("agent")
            if not agent_id or payload.get("status") != "ONLINE":
                return
            
            # Immediately try to pop all pending jobs for this agent
            await self._process_agent_queue(agent_id)
        except Exception as e:
            logger.error(f"[RECOVERY WORKER] Heartbeat trigger error: {e}")

    async def _retry_scheduler_loop(self):
        while True:
            try:
                now = time.time()
                # Get jobs that are due
                due_jobs_raw = self.redis_client.zrangebyscore("offline_queue:jobs", "-inf", now)
                
                for job_bytes in due_jobs_raw:
                    try:
                        job_str = str(job_bytes)
                        job_data = json.loads(job_str)
                        # Remove from scheduler so we don't pick it up again immediately
                        self.redis_client.zrem("offline_queue:jobs", job_str)
                        await self._process_single_job(job_data)
                    except Exception as e:
                        logger.error(f"[RECOVERY WORKER] Error processing scheduled job: {e}")
                
            except Exception as e:
                logger.error(f"[RECOVERY WORKER] Scheduler loop error: {e}")
            await asyncio.sleep(5)

    async def _process_agent_queue(self, agent_id: str):
        agent_set_key = f"offline_queue:agent:{agent_id}"
        job_ids = self.redis_client.smembers(agent_set_key)
        for jid in job_ids:
            job_data_str = self.redis_client.get(f"offline_queue:job_data:{jid}")
            if job_data_str:
                job_data = json.loads(job_data_str)
                # Remove from all queues to prevent race condition
                self.redis_client.zrem("offline_queue:jobs", job_data_str)
                self.redis_client.srem(agent_set_key, jid)
                self.redis_client.delete(f"offline_queue:job_data:{jid}")
                await self._process_single_job(job_data)
            else:
                self.redis_client.srem(agent_set_key, jid) # cleanup orphan

    async def _process_single_job(self, job: dict):
        job_id = job.get("job_id")
        incident_id = job.get("incident_id")
        exec_id = job.get("execution_id")
        action = job.get("action")
        retry_count = job.get("retry_count", 0)
        max_retry = job.get("max_retry", 5)
        exec_token = job.get("execution_token", {})
        expected_version = exec_token.get("version", None)

        logger.info(f"[RECOVERY WORKER] Processing recovery job {job_id} for incident {incident_id} (Attempt {retry_count+1}/{max_retry})")

        # 1. Evaluate DLQ
        if retry_count >= max_retry:
            logger.warning(f"[RECOVERY WORKER] Job {job_id} reached max retries. Moving to DLQ.")
            self._move_to_dlq(job, "Max retries exceeded")
            return

        # 2. Validation 1: TTL Check
        created_at_str = exec_token.get("created_at")
        ttl_sec = exec_token.get("ttl_sec", 60)
        if created_at_str:
            created_dt = datetime.fromisoformat(created_at_str.replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - created_dt).total_seconds() > ttl_sec:
                logger.warning(f"[RECOVERY WORKER] Job {job_id} TTL expired. Dropping.")
                self._move_to_dlq(job, "TTL Expired")
                return

        # 3. Validation 2: Single Source of Truth & Version Check
        try:
            with self.conn.cursor() as cur:
                final_status, state_version = self.orchestrator._resolve_incident_status(cur, incident_id)
                
                if final_status == "UNKNOWN":
                    logger.info(f"[RECOVERY WORKER] Incident {incident_id} is UNKNOWN. Discarding job.")
                    self._move_to_dlq(job, "Incident Unknown")
                    return
                
                if final_status in ('RESOLVED', 'CLOSED', 'SOLVED VERIFIED'):
                    logger.info(f"[RECOVERY WORKER] Incident {incident_id} is already {final_status}. Discarding job.")
                    self._move_to_dlq(job, f"Incident already {final_status}")
                    return
                
                if expected_version is not None and state_version != expected_version:
                    logger.warning(f"[RECOVERY WORKER] TOCTOU Prevention: Incident {incident_id} version changed ({expected_version} -> {state_version}). Discarding job.")
                    self._move_to_dlq(job, "Version Mismatch (Incident state changed)")
                    return
        except Exception as e:
            logger.error(f"[RECOVERY WORKER] State revalidation failed: {e}")
            self._requeue_job(job, delay=30)
            return

        # 4. Agent Idempotency / Retry - Republish to NATS
        # We reuse the same execution_id to ensure the agent ignores duplicate commands.
        mitigation_payload = {
            "incident_id": incident_id,
            "action": action,
            "details": job.get("params", {}),
            "execution_id": exec_id,
            "execution_token": exec_token,
            "job_id": job_id,
            "retry_count": retry_count + 1
        }
        
        try:
            if self.nc:
                await self.nc.publish("remediation.execute", json.dumps(mitigation_payload).encode())
                logger.info(f"[RECOVERY WORKER] Successfully republished job {job_id} to remediation.execute")
        except Exception as e:
            logger.error(f"[RECOVERY WORKER] Publish failed: {e}")
            self._requeue_job(job, delay=30)

    def _requeue_job(self, job: dict, delay: int = 30):
        # We don't increment retry count here, it's incremented when sent to NATS and Dashboard Server handles timeout.
        job["next_retry_at"] = time.time() + delay
        job_bytes = json.dumps(job)
        
        self.redis_client.zadd("offline_queue:jobs", {job_bytes: job["next_retry_at"]})
        if job.get("agent_id") and job.get("job_id"):
            self.redis_client.sadd(f"offline_queue:agent:{job.get('agent_id')}", str(job.get("job_id")))
        self.redis_client.set(f"offline_queue:job_data:{job.get('job_id')}", job_bytes, ex=86400)
        logger.info(f"[RECOVERY WORKER] Re-queued job {job.get('job_id')} for retry in {delay}s")

    def _move_to_dlq(self, job: dict, reason: str):
        job["dlq_reason"] = reason
        job["dlq_timestamp"] = datetime.now(timezone.utc).isoformat()
        self.redis_client.lpush("offline_queue:dlq", json.dumps(job))
        logger.info(f"[RECOVERY WORKER] Job {job.get('job_id')} moved to DLQ: {reason}")
