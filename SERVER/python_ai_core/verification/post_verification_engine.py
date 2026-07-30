import asyncio
import json
import logging
from datetime import datetime, timezone
import time

logger = logging.getLogger("POST_VERIFICATION")

class PostVerificationEngine:
    def __init__(self, nc, db_conn, state_machine=None):
        self.nc = nc
        self.conn = db_conn
        self.state_machine = state_machine
        self.STABILIZATION_DELAY_SEC = 15
        self.SAMPLE_COUNT = 3
        self.SAMPLE_INTERVAL_SEC = 15

    async def start(self):
        if self.nc:
            await self.nc.subscribe("agent.execution.>", queue="post-verification-group", cb=self._on_execution_event)
            logger.info("[POST VERIFICATION] Subscribed to agent.execution.>")

    async def _on_execution_event(self, msg):
        try:
            topic = msg.subject
            if "queued" in topic:
                return  # handled by Recovery Worker

            payload = json.loads(msg.data.decode())
            incident_id = payload.get("incident_id")
            exec_id = payload.get("execution_id")
            action = payload.get("action")
            target_pc = payload.get("pc_name")
            status = payload.get("status")
            job_id = payload.get("job_id")  # may be None if not passed all the way

            logger.info(f"[POST VERIFICATION] Received execution result for Incident {incident_id}: {status}")

            if status != "SUCCESS":
                await self._handle_execution_failure(incident_id, action, target_pc, payload, exec_id=exec_id)
                return

            # If SUCCESS, start Verification Pipeline
            # 1. Update State to WAITING_VERIFICATION
            self._update_state(incident_id, "WAITING_VERIFICATION")
            
            # 2. Spawn Verification Task
            asyncio.create_task(self._run_multi_sample_verification(incident_id, action, target_pc, job_id, exec_id=exec_id))

        except Exception as e:
            logger.error(f"[POST VERIFICATION] Error processing execution result: {e}")

    def _update_state(self, incident_id, new_state: str):
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO incident_states (incident_id, status, created_at)
                    VALUES (%s, %s, %s)
                """, (incident_id, new_state, datetime.now(timezone.utc).isoformat()))
            self.conn.commit()
            logger.info(f"[POST VERIFICATION] Transitioned Incident {incident_id} to {new_state}")
        except Exception as e:
            logger.error(f"[POST VERIFICATION] Failed to update state for {incident_id}: {e}")
            self.conn.rollback()

    async def _handle_execution_failure(self, incident_id, action, target_pc, payload, exec_id=None):
        self._update_state(incident_id, "FAILED")
        self._update_decision_record(exec_id, incident_id, 'FAILED_AT_AGENT', 'FAILED')
        logger.warning(f"[POST VERIFICATION] Incident {incident_id} Execution FAILED. Check DLQ or Retry mechanisms.")

    async def _run_multi_sample_verification(self, incident_id, action, target_pc, job_id, exec_id=None):
        logger.info(f"[POST VERIFICATION] Starting Stabilization Delay ({self.STABILIZATION_DELAY_SEC}s) for {incident_id}")
        await asyncio.sleep(self.STABILIZATION_DELAY_SEC)

        self._update_state(incident_id, "VERIFYING")
        logger.info(f"[POST VERIFICATION] Starting Multi-Sample Verification for {incident_id}")

        confidence_scores = []
        fail_count = 0
        unknown_count = 0

        for i in range(self.SAMPLE_COUNT):
            logger.info(f"[POST VERIFICATION] Sample {i+1}/{self.SAMPLE_COUNT} for {incident_id}")
            result = await asyncio.to_thread(self._verify_capability, target_pc, action)
            
            status = result.get("status")
            if status == "PASS":
                confidence_scores.append(result.get("confidence", 0.0))
            elif status == "UNKNOWN":
                unknown_count += 1
            else:
                fail_count += 1

            if i < self.SAMPLE_COUNT - 1:
                await asyncio.sleep(self.SAMPLE_INTERVAL_SEC)

        # Multi-Sample Decision & Confidence Aggregation
        if unknown_count == self.SAMPLE_COUNT:
            logger.warning(f"[POST VERIFICATION] Incident {incident_id} Verification UNKNOWN (stale/missing telemetry). Escalate.")
            self._update_state(incident_id, "ESCALATED")
            self._update_decision_record(exec_id, incident_id, 'UNKNOWN', 'ESCALATED')
        elif fail_count > 0:
            logger.warning(f"[POST VERIFICATION] Incident {incident_id} Verification FAILED ({fail_count} failures).")
            self._update_state(incident_id, "FAILED") # or ESCALATED
            self._update_decision_record(exec_id, incident_id, 'FAILED', 'FAILED')
            # Trigger learning feedback loop (Confidence --)
        else:
            # All valid samples passed.
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
            logger.info(f"[POST VERIFICATION] Incident {incident_id} Verification PASSED. Confidence: {avg_confidence:.1f}%")
            
            # Log the confidence to incident_events or emit to learning pipeline
            if self.nc:
                try:
                    event = {
                        "incident_id": incident_id,
                        "action": action,
                        "verification_confidence": avg_confidence,
                        "samples": len(confidence_scores)
                    }
                    asyncio.create_task(self.nc.publish(f"learning.feedback.{incident_id}", json.dumps(event).encode()))
                except Exception as e:
                    pass
            
            try:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        UPDATE autonomous_decision_records
                        SET verification_result = 'PASSED',
                            average_confidence = %s,
                            final_outcome = 'RESOLVED'
                        WHERE execution_id = %s OR incident_id = %s
                    """, (avg_confidence, exec_id, incident_id))
                self.conn.commit()
            except Exception as e:
                logger.error(f"[POST VERIFICATION] Failed to update decision record: {e}")
                self.conn.rollback()
            
            self._update_state(incident_id, "RESOLVED")
            self._clean_queue_job(job_id, target_pc)

    def _update_decision_record(self, exec_id, incident_id, result, outcome):
        try:
            with self.conn.cursor() as cur:
                cur.execute("""
                    UPDATE autonomous_decision_records
                    SET verification_result = %s, final_outcome = %s
                    WHERE execution_id = %s OR incident_id = %s
                """, (result, outcome, exec_id, incident_id))
            self.conn.commit()
        except Exception as e:
            logger.error(f"[POST VERIFICATION] Failed to update decision record: {e}")
            self.conn.rollback()

    def _verify_capability(self, target_pc: str, action: str) -> dict:
        """
        Capability-Specific Verification using Netdata telemetry.
        Returns: {"status": "PASS"|"FAIL"|"UNKNOWN", "confidence": float, "details": dict}
        """
        try:
            with self.conn.cursor() as cur:
                # Query recent telemetry (last 1 minute) and extract timestamp
                cur.execute("""
                    SELECT metric_name, metric_value, EXTRACT(EPOCH FROM timestamp) as ts
                    FROM telemetry_logs 
                    WHERE device_name = %s 
                    AND timestamp >= NOW() - INTERVAL '1 minute'
                    ORDER BY timestamp DESC
                """, (target_pc,))
                rows = cur.fetchall()
                
                metrics = {}
                now_ts = time.time()
                for m_name, m_val, m_ts in rows:
                    if m_name not in metrics:
                        # EVIDENCE FRESHNESS CHECK
                        is_fresh = (now_ts - float(m_ts)) < 30.0
                        metrics[m_name] = {
                            "value": float(m_val),
                            "fresh": is_fresh
                        }

                # Helper to get metric safely
                def get_m(name): return metrics.get(name, {}).get("value")
                def is_f(name): return metrics.get(name, {}).get("fresh", False)

                # Capability rules
                if action == "restart_service":
                    cpu = get_m("cpu_usage")
                    mem = get_m("memory_usage")
                    if cpu is None or mem is None:
                        return {"status": "UNKNOWN", "confidence": 0.0, "details": {"reason": "missing_metrics"}}
                    if not is_f("cpu_usage"):
                        return {"status": "UNKNOWN", "confidence": 0.0, "details": {"reason": "stale_telemetry"}}
                    
                    confidence = 100.0
                    if cpu > 80.0: confidence -= 40.0
                    if mem > 90.0: confidence -= 20.0
                    
                    return {
                        "status": "PASS" if confidence >= 80.0 else "FAIL",
                        "confidence": confidence,
                        "details": {"cpu": cpu, "mem": mem}
                    }
                
                elif action == "restart_agent":
                    # For agent restart, any fresh telemetry indicates success
                    fresh_metrics = [k for k, v in metrics.items() if v.get("fresh")]
                    if len(fresh_metrics) > 0:
                        return {"status": "PASS", "confidence": 95.0, "details": {"fresh_metrics": len(fresh_metrics)}}
                    return {"status": "UNKNOWN", "confidence": 0.0, "details": {"reason": "no_fresh_telemetry"}}
                
                elif action == "kill_process":
                    cpu = get_m("cpu_usage")
                    if cpu is None or not is_f("cpu_usage"):
                        return {"status": "UNKNOWN", "confidence": 0.0, "details": {"reason": "stale_or_missing_cpu"}}
                    return {
                        "status": "PASS" if cpu < 60.0 else "FAIL",
                        "confidence": 100.0 - cpu,
                        "details": {"cpu": cpu}
                    }
                
                elif action == "clear_cache":
                    mem = get_m("memory_usage")
                    if mem is None or not is_f("memory_usage"):
                        return {"status": "UNKNOWN", "confidence": 0.0, "details": {"reason": "stale_or_missing_mem"}}
                    return {
                        "status": "PASS" if mem < 80.0 else "FAIL",
                        "confidence": 100.0 - mem,
                        "details": {"mem": mem}
                    }
                
                # Default verification
                return {"status": "PASS", "confidence": 80.0, "details": {"reason": "no_specific_capability_rule"}}
                
        except Exception as e:
            logger.error(f"[POST VERIFICATION] Capability check error: {e}")
            return {"status": "UNKNOWN", "confidence": 0.0, "details": {"error": str(e)}}

    def _clean_queue_job(self, job_id, agent_id):
        if not job_id:
            return
        try:
            import os
            import redis
            redis_host = os.environ.get("REDIS_HOST", "redis")
            redis_client = redis.Redis(host=redis_host, port=6379, db=0, decode_responses=True)
            redis_client.zrem("offline_queue:jobs", job_id)
            if agent_id:
                redis_client.srem(f"offline_queue:agent:{agent_id}", job_id)
            redis_client.delete(f"offline_queue:job_data:{job_id}")
            logger.info(f"[POST VERIFICATION] Cleaned up job {job_id} from queues")
        except Exception as e:
            logger.error(f"[POST VERIFICATION] Failed to clean queue job: {e}")
