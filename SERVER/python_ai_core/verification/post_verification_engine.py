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

            exec_ts = time.time()
            # Record Rule #6 Execution Evidence bound to incident_id and target_pc
            self._record_incident_event(
                incident_id,
                "EXECUTION_EVIDENCE",
                {
                    "incident_id": incident_id,
                    "target_asset": target_pc,
                    "execution_id": exec_id,
                    "action": action,
                    "status": "SUCCESS",
                    "executed_at_epoch": exec_ts,
                    "executed_at": datetime.now(timezone.utc).isoformat(),
                },
            )

            # If SUCCESS, start Verification Pipeline
            # 1. Update State to WAITING_VERIFICATION
            self._update_state(incident_id, "WAITING_VERIFICATION")
            
            # 2. Spawn Verification Task
            asyncio.create_task(
                self._run_multi_sample_verification(
                    incident_id, action, target_pc, job_id, exec_id=exec_id, exec_ts=exec_ts
                )
            )

        except Exception as e:
            logger.error(f"[POST VERIFICATION] Error processing execution result: {e}")

    def _record_incident_event(self, incident_id, event_type: str, payload_dict: dict):
        if not self.conn or incident_id is None:
            return
        try:
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO incident_events (incident_id, event_type, payload, created_at)
                    VALUES (%s, %s, %s::jsonb, NOW())
                    """,
                    (str(incident_id), event_type, json.dumps(payload_dict)),
                )
            self.conn.commit()
        except Exception as e:
            logger.debug(f"[POST VERIFICATION] Failed to record {event_type} for {incident_id}: {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass

    def _update_state(self, incident_id, new_state: str):
        if not self.conn or incident_id is None:
            return
        try:
            now_iso = datetime.now(timezone.utc).isoformat()
            with self.conn.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO incident_states (incident_id, flag, status, to_state, created_at, last_updated, resolved_at)
                    VALUES (%s, %s, %s, %s, %s, NOW(), CASE WHEN %s = 'RESOLVED' THEN NOW() ELSE NULL END)
                    ON CONFLICT (incident_id) DO UPDATE
                    SET status = EXCLUDED.status,
                        to_state = EXCLUDED.to_state,
                        flag = EXCLUDED.flag,
                        last_updated = NOW(),
                        resolved_at = CASE WHEN EXCLUDED.status = 'RESOLVED' THEN NOW() ELSE incident_states.resolved_at END
                    """,
                    (incident_id, new_state, new_state, new_state, now_iso, new_state),
                )
                # Synchronize incidents & fleet_incidents to prevent split-brain state
                if new_state == "RESOLVED":
                    cur.execute(
                        """
                        UPDATE incidents
                        SET flag = 'RESOLVED',
                            verification_time = NOW(),
                            raw_data = jsonb_set(COALESCE(raw_data, '{}'::jsonb), '{status}', '"RESOLVED"'::jsonb)
                        WHERE incident_id = %s
                        """,
                        (incident_id,),
                    )
                    cur.execute(
                        """
                        UPDATE fleet_incidents
                        SET status = 'RESOLVED',
                            resolved_at = NOW(),
                            state_version = COALESCE(state_version, 0) + 1
                        WHERE incident_id = %s
                        """,
                        (incident_id,),
                    )
                else:
                    cur.execute(
                        """
                        UPDATE incidents
                        SET raw_data = jsonb_set(COALESCE(raw_data, '{}'::jsonb), '{status}', to_jsonb(%s::text))
                        WHERE incident_id = %s
                        """,
                        (new_state, incident_id),
                    )
                    cur.execute(
                        """
                        UPDATE fleet_incidents
                        SET status = %s,
                            state_version = COALESCE(state_version, 0) + 1
                        WHERE incident_id = %s
                        """,
                        (new_state, incident_id),
                    )
            self.conn.commit()
            logger.info(f"[POST VERIFICATION] Transitioned Incident {incident_id} to {new_state}")
        except Exception as e:
            logger.error(f"[POST VERIFICATION] Failed to update state for {incident_id}: {e}")
            try:
                self.conn.rollback()
            except Exception:
                pass

    async def _handle_execution_failure(self, incident_id, action, target_pc, payload, exec_id=None):
        self._update_state(incident_id, "FAILED")
        self._update_decision_record(exec_id, incident_id, 'FAILED_AT_AGENT', 'FAILED')
        logger.warning(f"[POST VERIFICATION] Incident {incident_id} Execution FAILED. Check DLQ or Retry mechanisms.")

    async def _run_multi_sample_verification(self, incident_id, action, target_pc, job_id, exec_id=None, exec_ts: float = 0.0):
        logger.info(f"[POST VERIFICATION] Starting Stabilization Delay ({self.STABILIZATION_DELAY_SEC}s) for {incident_id}")
        await asyncio.sleep(self.STABILIZATION_DELAY_SEC)

        self._update_state(incident_id, "VERIFYING")
        logger.info(f"[POST VERIFICATION] Starting Multi-Sample Verification for {incident_id}")

        confidence_scores = []
        fail_count = 0
        unknown_count = 0
        last_details = {}

        for i in range(self.SAMPLE_COUNT):
            logger.info(f"[POST VERIFICATION] Sample {i+1}/{self.SAMPLE_COUNT} for {incident_id}")
            result = await asyncio.to_thread(self._verify_capability, target_pc, action, exec_ts)
            
            status = result.get("status")
            last_details = result.get("details") or {}
            if status == "PASS":
                confidence_scores.append(result.get("confidence", 0.0))
            elif status == "UNKNOWN":
                unknown_count += 1
            else:
                fail_count += 1

            if i < self.SAMPLE_COUNT - 1:
                await asyncio.sleep(self.SAMPLE_INTERVAL_SEC)

        # Multi-Sample Decision & Confidence Aggregation
        if unknown_count == self.SAMPLE_COUNT or len(confidence_scores) == 0:
            logger.warning(f"[POST VERIFICATION] Incident {incident_id} Verification UNKNOWN (stale/missing telemetry). Escalate.")
            self._update_state(incident_id, "ESCALATED")
            self._update_decision_record(exec_id, incident_id, 'UNKNOWN', 'ESCALATED')
        elif fail_count > 0:
            logger.warning(f"[POST VERIFICATION] Incident {incident_id} Verification FAILED ({fail_count} failures). Triggering Auto-Rollback...")
            self._update_state(incident_id, "FAILED")
            self._update_decision_record(exec_id, incident_id, 'FAILED', 'FAILED')
            if self.nc:
                try:
                    rollback_payload = {
                        "incident_id": incident_id,
                        "pc_name": target_pc,
                        "action": action,
                        "reason": f"Post-verification failed ({fail_count} sample failures)",
                        "timestamp": datetime.now(timezone.utc).isoformat()
                    }
                    asyncio.create_task(self.nc.publish("remediation.rollback", json.dumps(rollback_payload).encode()))
                    logger.info(f"[POST VERIFICATION] Triggered automatic Rollback for Incident {incident_id}")
                except Exception as r_err:
                    logger.error(f"[POST VERIFICATION] Failed to trigger rollback: {r_err}")

        else:
            # All valid samples passed — Enforce Governance Rule #6 Dual-Evidence Binding (T_post >= T_exec)
            avg_confidence = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0.0
            post_ts = time.time()
            if exec_ts and post_ts < exec_ts:
                logger.warning(f"[POST VERIFICATION] [RULE #6 BLOCK] T_post ({post_ts}) < T_exec ({exec_ts}) for {incident_id}")
                self._update_state(incident_id, "PENDING_VERIFICATION")
                return

            self._record_incident_event(
                incident_id,
                "POST_REMEDIATION_EVIDENCE",
                {
                    "incident_id": incident_id,
                    "target_asset": target_pc,
                    "execution_id": exec_id,
                    "action": action,
                    "verification_confidence": avg_confidence,
                    "samples_passed": len(confidence_scores),
                    "telemetry_details": last_details,
                    "verified_at_epoch": post_ts,
                    "verified_at": datetime.now(timezone.utc).isoformat(),
                    "rule6_dual_evidence_bound": True,
                },
            )
            logger.info(f"[POST VERIFICATION] Incident {incident_id} Verification PASSED (Rule #6 Dual-Evidence Bound). Confidence: {avg_confidence:.1f}%")
            
            # Log the confidence to incident_events or emit to learning pipeline
            if self.nc:
                try:
                    event = {
                        "incident_id": incident_id,
                        "target_asset": target_pc,
                        "action": action,
                        "verification_confidence": avg_confidence,
                        "samples": len(confidence_scores),
                        "rule6_verified": True,
                    }
                    asyncio.create_task(self.nc.publish(f"learning.feedback.{incident_id}", json.dumps(event).encode()))
                except Exception:
                    logging.getLogger(__name__).debug("Suppressed exception", exc_info=True)

            # In-process Self-Learning Bridge trigger (Pipeline 3 -> Pipeline 4 integration)
            try:
                from SERVER.jarvis.knowledge.knowledge_learning_bridge import JarvisKnowledgeLearningBridge
                bridge = JarvisKnowledgeLearningBridge.get_instance()
                bridge.auto_learn_from_resolution(
                    incident_id=str(incident_id),
                    title=f"Verified Remediation: {action} on {target_pc}",
                    root_cause=f"Remediated via {action} on {target_pc}",
                    resolution_steps=[f"Executed {action} on {target_pc}", f"Verified post-remediation telemetry ({avg_confidence:.1f}% confidence)"],
                    category="autonomous_remediation",
                    target_asset=str(target_pc or "unknown"),
                    execution_evidence=f"EXECUTION_ID:{exec_id or 'AUTO'}",
                    post_remediation_evidence=json.dumps(last_details),
                )
            except Exception as learn_err:
                logger.debug(f"[POST VERIFICATION] Learning bridge notification skipped: {learn_err}")
            
            try:
                with self.conn.cursor() as cur:
                    if exec_id:
                        cur.execute("""
                            UPDATE autonomous_decision_records
                            SET verification_result = 'PASSED',
                                average_confidence = %s,
                                final_outcome = 'RESOLVED'
                            WHERE execution_id = %s AND incident_id = %s
                        """, (avg_confidence, str(exec_id), str(incident_id)))
                    else:
                        cur.execute("""
                            UPDATE autonomous_decision_records
                            SET verification_result = 'PASSED',
                                average_confidence = %s,
                                final_outcome = 'RESOLVED'
                            WHERE incident_id = %s
                        """, (avg_confidence, str(incident_id)))
                self.conn.commit()
            except Exception as e:
                logger.error(f"[POST VERIFICATION] Failed to update decision record: {e}")
                self.conn.rollback()
            
            self._update_state(incident_id, "RESOLVED")
            self._clean_queue_job(job_id, target_pc)

    def _update_decision_record(self, exec_id, incident_id, result, outcome):
        try:
            with self.conn.cursor() as cur:
                if exec_id:
                    cur.execute("""
                        UPDATE autonomous_decision_records
                        SET verification_result = %s, final_outcome = %s
                        WHERE execution_id = %s AND incident_id = %s
                    """, (result, outcome, str(exec_id), str(incident_id)))
                else:
                    cur.execute("""
                        UPDATE autonomous_decision_records
                        SET verification_result = %s, final_outcome = %s
                        WHERE incident_id = %s
                    """, (result, outcome, str(incident_id)))
            self.conn.commit()
        except Exception as e:
            logger.error(f"[POST VERIFICATION] Failed to update decision record: {e}")
            self.conn.rollback()

    def _verify_capability(self, target_pc: str, action: str, exec_ts: float = 0.0) -> dict:
        """
        Capability-Specific Verification using canonical telemetry_logs (metric_type).
        Strictly enforces Governance Rule #6: post-remediation telemetry must exist
        and satisfy T_post >= T_exec (zero assumption of success).
        Returns: {"status": "PASS"|"FAIL"|"UNKNOWN", "confidence": float, "details": dict}
        """
        try:
            with self.conn.cursor() as cur:
                # Query recent telemetry from canonical metric_type column (last 1 minute)
                cur.execute("""
                    SELECT metric_type, metric_value, EXTRACT(EPOCH FROM timestamp) as ts
                    FROM telemetry_logs 
                    WHERE device_name = %s 
                    AND timestamp >= NOW() - INTERVAL '1 minute'
                    ORDER BY timestamp DESC
                """, (target_pc,))
                rows = cur.fetchall()
                
                metrics = {}
                now_ts = time.time()
                alias_map = {
                    "cpu_percent": "cpu_usage",
                    "memory_percent": "memory_usage",
                    "disk_percent": "disk_usage",
                }
                for m_name, m_val, m_ts in rows:
                    m_ts_float = float(m_ts)
                    # EVIDENCE FRESHNESS & CAUSAL ORDERING CHECK (T_post >= T_exec)
                    is_fresh = ((now_ts - m_ts_float) < 60.0) and (m_ts_float >= float(exec_ts or 0.0))
                    entry = {
                        "value": float(m_val),
                        "fresh": is_fresh,
                        "timestamp": m_ts_float,
                    }
                    if m_name not in metrics:
                        metrics[m_name] = entry
                    canonical_alias = alias_map.get(m_name)
                    if canonical_alias and canonical_alias not in metrics:
                        metrics[canonical_alias] = entry

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
                    # For agent restart, any fresh telemetry with T_post >= T_exec indicates success
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
                        "confidence": max(0.0, 100.0 - cpu),
                        "details": {"cpu": cpu}
                    }
                
                elif action == "clear_cache":
                    mem = get_m("memory_usage")
                    if mem is None or not is_f("memory_usage"):
                        return {"status": "UNKNOWN", "confidence": 0.0, "details": {"reason": "stale_or_missing_mem"}}
                    return {
                        "status": "PASS" if mem < 80.0 else "FAIL",
                        "confidence": max(0.0, 100.0 - mem),
                        "details": {"mem": mem}
                    }
                
                # Governance Rule #6 Default Verification:
                # Never assume remediation succeeded without live post-remediation telemetry (T_post >= T_exec)
                fresh_metrics = {k: v["value"] for k, v in metrics.items() if v.get("fresh")}
                if not fresh_metrics:
                    return {
                        "status": "UNKNOWN",
                        "confidence": 0.0,
                        "details": {"reason": "rule6_missing_post_remediation_telemetry", "action": action},
                    }
                cpu = get_m("cpu_usage")
                mem = get_m("memory_usage")
                if (cpu is not None and cpu >= 85.0) or (mem is not None and mem >= 90.0):
                    return {
                        "status": "FAIL",
                        "confidence": 30.0,
                        "details": {"reason": "post_remediation_metrics_unhealthy", "cpu": cpu, "mem": mem},
                    }
                return {
                    "status": "PASS",
                    "confidence": 85.0,
                    "details": {"reason": "rule6_verified_fresh_telemetry", "fresh_metrics": fresh_metrics},
                }
                
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
