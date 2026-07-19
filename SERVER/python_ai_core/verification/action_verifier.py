"""
OSI AI Ops — Action Verification Engine
Independent Outcome Verification Post-Execution

Pipeline: Execute -> VERIFYING State -> Active Event Listener + Polling Watchdog -> Commit OR Rollback
"""

import asyncio
import logging
import json
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional

logger = logging.getLogger("ACTION_VERIFIER")

# Verification Policy (Predicate-based)
VERIFICATION_POLICY = {
    "RESTART_NGINX": {
        "required": ["port_443_open", "health_200"],
        "optional": ["cpu_normal"],
        "deadline_sec": 120,
        "auto_rollback_allowed": True
    },
    "RESTART_POSTGRESQL": {
        "required": ["replication_healthy", "connections_active"],
        "optional": [],
        "deadline_sec": 180,
        "auto_rollback_allowed": True
    },
    "DEFAULT": {
        "required": ["status_active", "cpu_normal"],
        "optional": ["memory_stable"],
        "deadline_sec": 120,
        "auto_rollback_allowed": False
    }
}

class ActionVerifier:
    def __init__(self, db_conn, rollback_engine, shadow_mode: bool = True, nc=None):
        self.db = db_conn
        self.rollback_engine = rollback_engine
        self.shadow_mode = shadow_mode
        self.nc = nc

    async def wait_and_verify(
        self, 
        incident_id: int, 
        action: str, 
        device: str, 
        snapshot_id: str, 
        expected_outcome: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Active Listener + Polling Watchdog for verification.
        Uses absolute deadlines and predicate evaluation.
        """
        # 1. State: VERIFYING (Checkpoint)
        self._log_verification(incident_id, action, device, "VERIFYING", "Verification started")
        
        policy = VERIFICATION_POLICY.get(action.upper(), VERIFICATION_POLICY["DEFAULT"])
        deadline_sec = policy["deadline_sec"]
        start_time = time.time()
        deadline = start_time + deadline_sec
        
        logger.info(f"[VERIFIER] Starting verification for '{action}' on {device}. Deadline: {deadline_sec}s")

        # 2. Setup NATS Subscriber for Event-Driven updates
        incoming_metrics = asyncio.Queue()
        sub = None
        if self.nc:
            async def msg_handler(msg):
                try:
                    data = json.loads(msg.data.decode())
                    await incoming_metrics.put(data)
                except Exception as e:
                    logger.error(f"[VERIFIER] Error parsing NATS message: {e}")
            # Listen to this device's telemetry specifically
            sub = await self.nc.subscribe(f"telemetry.site.*.device.{device}", cb=msg_handler)

        try:
            # 2.5 Immediate Fast-Track Verification (Eliminate initial polling delay)
            current_metrics = self._fetch_current_metrics(device)
            if current_metrics:
                is_success, conf, reason = self._evaluate_predicates(action, current_metrics)
                if is_success:
                    logger.info(f"[VERIFIER] Passed Fast-Track Predicate Verification for '{action}'")
                    self._log_verification(incident_id, action, device, "VERIFIED", f"Passed predicates: {reason}")
                    return {"status": "SUCCESS", "score": 100, "confidence": conf}

            # 3. Watchdog + Event Loop
            while time.time() < deadline:
                current_metrics = {}
                
                try:
                    # Active Listening (Timeout every 2s to force Watchdog poll)
                    current_metrics = await asyncio.wait_for(incoming_metrics.get(), timeout=2.0)
                    logger.debug(f"[VERIFIER] Received event-driven metrics for {device}")
                except asyncio.TimeoutError:
                    # Polling Watchdog (Fallback)
                    current_metrics = self._fetch_current_metrics(device)
                    logger.debug(f"[VERIFIER] Polled watchdog metrics for {device}")
                
                if current_metrics:
                    # 4. Checkpoint State
                    self._update_checkpoint(incident_id, current_metrics, int(deadline - time.time()))
                    
                    # 5. Evaluate Predicates
                    is_success, conf, reason = self._evaluate_predicates(action, current_metrics)
                    
                    if is_success:
                        logger.info(f"[VERIFIER] Passed Predicate Verification for '{action}' in {int(time.time() - start_time)}s")
                        self._log_verification(incident_id, action, device, "VERIFIED", f"Passed predicates: {reason}")
                        return {"status": "SUCCESS", "score": 100, "confidence": conf}

            # 6. Timeout / Absolute Deadline Reached
            logger.warning(f"[VERIFIER] Verification TIMEOUT for '{action}' after {deadline_sec}s")
            return await self._handle_failure(incident_id, action, device, snapshot_id, 0, 50, policy["auto_rollback_allowed"], "VERIFY_TIMEOUT")
            
        finally:
            if sub:
                await sub.unsubscribe()

    def _evaluate_predicates(self, action: str, metrics: dict) -> tuple[bool, int, str]:
        policy = VERIFICATION_POLICY.get(action.upper(), VERIFICATION_POLICY["DEFAULT"])
        reqs = policy.get("required", [])
        if not isinstance(reqs, list):
            reqs = []
        
        passed = True
        reasons = []
        
        for req in reqs:
            if req == "status_active":
                if metrics.get("status") in ("OFFLINE", "DOWN", "ERROR"):
                    passed = False
                    reasons.append("Status != ACTIVE")
            elif req == "cpu_normal":
                if metrics.get("cpu_percent", 100) > 85:
                    passed = False
                    reasons.append("CPU > 85")
            elif req == "port_443_open":
                if not metrics.get("port_443_open", False):
                    passed = False
                    reasons.append("Port 443 closed")
            elif req == "health_200":
                if metrics.get("health_status") != 200:
                    passed = False
                    reasons.append("Health != 200")
            elif req == "replication_healthy":
                if metrics.get("replication_delay", 999) > 10:
                    passed = False
                    reasons.append("Replication > 10s")

        if not passed:
            return False, 50, " | ".join(reasons)
            
        return True, 90, "All REQUIRED predicates passed"

    async def _handle_failure(self, incident_id, action, device, snapshot_id, score, conf, auto_rollback, reason):
        if self.shadow_mode:
            self._log_verification(incident_id, action, device, "ROLLBACK_REQUIRED", reason)
            return {"status": "ROLLBACK_RECOMMENDED", "score": score, "confidence": conf}
            
        if not auto_rollback:
            self._log_verification(incident_id, action, device, "MANUAL_INTERVENTION", f"No auto-rollback allowed. {reason}")
            return {"status": "ESCALATION_RECOMMENDED", "score": score, "confidence": conf}

        # 7. Saga / Rollback Mechanism Trigger
        self._log_verification(incident_id, action, device, "ROLLBACK_REQUIRED", f"Triggering Saga Compensate: {reason}")
        
        rollback_success = False
        if self.rollback_engine:
            rollback_success = await self.rollback_engine.trigger_rollback(
                incident_id=incident_id,
                event_id=f"verify-fail-{int(datetime.now(timezone.utc).timestamp())}",
                action=action,
                snap_id=snapshot_id
            )
            
        final_status = "ROLLBACK_SUCCESS" if rollback_success else "ROLLBACK_FAILED"
        self._log_verification(incident_id, action, device, final_status, "Rollback executed")
        return {"status": final_status, "score": score, "confidence": conf}

    def _fetch_current_metrics(self, device: str) -> dict:
        metrics = {}
        if not self.db:
            return metrics
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    "SELECT hardware_info, status FROM fleet_devices WHERE pc_name = %s LIMIT 1",
                    (device,)
                )
                row = cur.fetchone()
                if row:
                    hw_info = row[0] or {}
                    if isinstance(hw_info, str):
                        try:
                            hw_info = json.loads(hw_info)
                        except Exception:
                            hw_info = {}
                    metrics = {
                        "cpu_percent": hw_info.get("cpu_percent", 0.0),
                        "ram_percent": hw_info.get("ram_percent", 0.0),
                        "status": row[1],
                        "packet_loss": hw_info.get("packet_loss", 0),
                        "port_443_open": hw_info.get("port_443_open", False),
                        "health_status": hw_info.get("health_status", 500)
                    }
        except Exception as e:
            logger.error(f"[VERIFIER] Watchdog failed: {e}")
        return metrics

    def _log_verification(self, incident_id: int, action: str, device: str, status: str, reason: str):
        if not self.db:
            return
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    """
                    INSERT INTO incident_events (incident_id, event_type, payload, created_at)
                    VALUES (%s, 'ACTION_VERIFICATION', %s, NOW())
                    """,
                    (incident_id, json.dumps({
                        "action": action, 
                        "device": device, 
                        "state_machine": status, 
                        "detail": reason
                    }))
                )
            self.db.commit()
        except Exception as e:
            logger.error(f"[VERIFIER] Failed to log verification to DB: {e}")

    def _update_checkpoint(self, incident_id: int, metrics: dict, remaining_sec: int):
        # Stores progress (e.g. CPU trend) so if worker dies, state isn't lost
        if not self.db:
            return
        try:
            with self.db.cursor() as cur:
                # Log checkpoint as an event in incident_events (Event Sourcing)
                cur.execute(
                    """
                    INSERT INTO incident_events (incident_id, event_type, payload, created_at)
                    VALUES (%s, 'VERIFY_CHECKPOINT', %s, NOW())
                    """,
                    (incident_id, json.dumps({
                        "progress": "VERIFYING",
                        "remaining_timeout": remaining_sec,
                        "last_health": metrics.get("health_status"),
                        "last_cpu": metrics.get("cpu_percent")
                    }))
                )
            self.db.commit()
        except Exception as e:
            logger.error(f"[VERIFIER] Failed to save checkpoint to DB: {e}")

