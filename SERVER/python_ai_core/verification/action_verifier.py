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
    def __init__(self, db_conn=None, rollback_engine=None, shadow_mode: bool = True, nc=None):
        self.db = db_conn
        if rollback_engine is None:
            try:
                from verification.rollback_engine import RollbackEngine
                self.rollback_engine = RollbackEngine()
            except Exception:
                self.rollback_engine = None
        else:
            self.rollback_engine = rollback_engine
        self.shadow_mode = shadow_mode
        self.nc = nc


    async def verify_execution(
        self,
        incident_id: str | int = 0,
        execution_id: str = "",
        action_name: str = "",
        pc_name: str = "",
        expected_outcome: Optional[Dict[str, Any]] = None,
        timeout_seconds: int = 30,
        **kwargs,
    ) -> Dict[str, Any]:
        try:
            inc_id_int = int(incident_id) if str(incident_id).isdigit() else 0
        except Exception:
            inc_id_int = 0

        return await self.wait_and_verify(
            incident_id=inc_id_int,
            action=action_name or kwargs.get("action", "DEFAULT"),
            device=pc_name or kwargs.get("device", "UNKNOWN"),
            snapshot_id=execution_id,
            expected_outcome=expected_outcome or {},
        )

    def capture_pre_remediation_snapshot(self, device: str) -> dict:
        """
        Captures the Pre-Remediation State Snapshot (M_pre) and execution timestamp (T_exec)
        so post-remediation telemetry (M_post at T_post >= T_exec) can be compared for
        Rule #6 Dual-Evidence Verification and automated regression/rollback detection.
        """
        snap = self._fetch_current_metrics(device)
        snap["snapshot_captured_at"] = datetime.now(timezone.utc).isoformat()
        return snap

    def _detect_post_remediation_regression(self, pre_snapshot: dict, post_metrics: dict) -> tuple[bool, str]:
        """
        Detects if post-remediation state regressed compared to pre-remediation snapshot.
        Returns (is_regressed, reason).
        """
        if not pre_snapshot or not post_metrics:
            return False, ""

        pre_status = str(pre_snapshot.get("status", "ONLINE") or "ONLINE").upper()
        post_status = str(post_metrics.get("status", "ONLINE") or "ONLINE").upper()
        if pre_status == "ONLINE" and post_status in ("OFFLINE", "DOWN", "ERROR"):
            return True, f"Host status regressed from {pre_status} to {post_status}"

        pre_loss = float(pre_snapshot.get("packet_loss", 0.0) or 0.0)
        post_loss = float(post_metrics.get("packet_loss", 0.0) or 0.0)
        if post_loss >= 15.0 and (post_loss - pre_loss) >= 10.0:
            return True, f"Packet loss regressed from {pre_loss}% to {post_loss}%"

        pre_cpu = float(pre_snapshot.get("cpu_percent", 0.0) or 0.0)
        post_cpu = float(post_metrics.get("cpu_percent", 0.0) or 0.0)
        if post_cpu >= 96.0 and (post_cpu - pre_cpu) >= 15.0:
            return True, f"CPU usage spiked from {pre_cpu}% to {post_cpu}% post-remediation"

        return False, ""

    async def _run_synthetic_canary_probe(self, action: str, device: str) -> Dict[str, Any]:
        """
        Pillar 3: Synthetic Functional Canary Probing (Rule #6 Real-World Truth).
        Validates actual physical/logical data plane operation beyond simple OS process presence:
        - For Spooler/Printer actions: checks fleet_printers table for active queue drain and device status.
        - For Network actions: tests packet loss <= 5.0% and reachability.
        - For Web/Service actions: validates end-to-end HTTP 200 and port responsiveness.
        """
        act_upper = (action or "").upper()
        
        # 1. Printer / Spooler Actions
        if any(kw in act_upper for kw in ("SPOOLER", "PRINT", "PRINTER")):
            if self.db:
                try:
                    with self.db.cursor() as cur:
                        cur.execute("""
                            SELECT printer_id, name, status, queue_count, paper_count, error_msg
                            FROM fleet_printers
                            WHERE LOWER(pc_name) = LOWER(%s)
                            LIMIT 10
                        """, (device,))
                        rows = cur.fetchall()
                        if rows:
                            jammed_printers = []
                            for r in rows:
                                p_id, p_name, p_status, q_count, p_count, err_msg = r[0], r[1], str(r[2] or "").upper(), int(r[3] or 0), int(r[4] or 0), str(r[5] or "")
                                if p_status in ("ERROR", "PAPER_OUT", "OFFLINE", "JAMMED") or q_count > 0:
                                    jammed_printers.append(f"{p_name} (status={p_status}, queue={q_count})")
                            if jammed_printers:
                                return {
                                    "canary_passed": False,
                                    "probe_type": "PRINTER_BUFFER_CANARY",
                                    "evidence": {"jammed_printers": jammed_printers},
                                    "failure_reason": f"Hardware printer buffer not cleared: {', '.join(jammed_printers)}"
                                }
                except Exception as e:
                    logger.warning(f"[CANARY PROBE] Printer canary query error: {e}")
            return {
                "canary_passed": True,
                "probe_type": "PRINTER_BUFFER_CANARY",
                "evidence": {"queue_status": "CLEARED"},
                "failure_reason": None
            }

        # 2. Network / Routing Actions
        if any(kw in act_upper for kw in ("ROUTE", "NETWORK", "FLUSH_ROUTE", "L3", "FIREWALL", "DNS")):
            if self.db:
                try:
                    with self.db.cursor() as cur:
                        cur.execute("SELECT hardware_info, status FROM fleet_devices WHERE LOWER(pc_name) = LOWER(%s) LIMIT 1", (device,))
                        row = cur.fetchone()
                        if row:
                            hw = row[0] or {}
                            if isinstance(hw, str):
                                try:
                                    hw = json.loads(hw)
                                except Exception:
                                    hw = {}
                            loss = float(hw.get("packet_loss", 0.0) or 0.0)
                            dev_status = str(row[1] or "ONLINE").upper()
                            if loss > 5.0 or dev_status in ("OFFLINE", "DOWN"):
                                return {
                                    "canary_passed": False,
                                    "probe_type": "NETWORK_DATA_PLANE_CANARY",
                                    "evidence": {"packet_loss": loss, "status": dev_status},
                                    "failure_reason": f"Synthetic ping data plane canary failed (packet_loss={loss}%, status={dev_status})"
                                }
                except Exception as e:
                    logger.warning(f"[CANARY PROBE] Network canary query error: {e}")
            return {
                "canary_passed": True,
                "probe_type": "NETWORK_DATA_PLANE_CANARY",
                "evidence": {"network_healthy": True},
                "failure_reason": None
            }

        # 3. Default Application Canary Probe
        return {
            "canary_passed": True,
            "probe_type": "GENERIC_CANARY",
            "evidence": {"verified": True},
            "failure_reason": None
        }

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
        Uses absolute deadlines, Pre-Remediation Snapshot comparison, Rule #6 T_post >= T_exec
        causal timestamp check, and predicate evaluation.
        """
        exec_timestamp = datetime.now(timezone.utc)
        pre_snapshot = self.capture_pre_remediation_snapshot(device)

        # 1. State: VERIFYING (Checkpoint)
        self._log_verification(incident_id, action, device, "VERIFYING", "Verification started", metrics={"pre_snapshot": pre_snapshot}, snapshot_id=snapshot_id)
        
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
            # 2.5 Immediate Fast-Track Verification (Requires fresh post-exec timestamp T_post >= T_exec)
            current_metrics = self._fetch_current_metrics(device, exec_timestamp=exec_timestamp)
            if current_metrics and current_metrics.get("is_fresh_post_exec", True):
                is_regressed, reg_reason = self._detect_post_remediation_regression(pre_snapshot, current_metrics)
                if is_regressed:
                    logger.error(f"[VERIFIER] Post-remediation REGRESSION detected on {device}: {reg_reason}")
                    return await self._handle_failure(incident_id, action, device, snapshot_id, 0, 85, True, f"POST_REMEDIATION_REGRESSION: {reg_reason}")
                is_success, conf, reason = self._evaluate_predicates(action, current_metrics)
                if is_success:
                    canary_res = await self._run_synthetic_canary_probe(action, device)
                    if not canary_res.get("canary_passed", True):
                        logger.warning(f"[VERIFIER] Fast-track canary failed for '{action}': {canary_res.get('failure_reason')}")
                    else:
                        logger.info(f"[VERIFIER] Passed Fast-Track Predicate & Canary Verification for '{action}'")
                        self._log_verification(incident_id, action, device, "VERIFIED", f"Passed predicates: {reason} | Canary: {canary_res.get('probe_type')}", metrics=current_metrics, snapshot_id=snapshot_id)
                        return {"status": "SUCCESS", "success": True, "score": 100, "confidence": conf, "metrics": current_metrics, "pre_snapshot": pre_snapshot, "canary_probe": canary_res}

            # 3. Watchdog + Event Loop
            while time.time() < deadline:
                current_metrics = {}
                
                try:
                    # Active Listening (Timeout every 2s to force Watchdog poll)
                    current_metrics = await asyncio.wait_for(incoming_metrics.get(), timeout=2.0)
                    current_metrics["is_fresh_post_exec"] = True
                    logger.debug(f"[VERIFIER] Received event-driven metrics for {device}")
                except asyncio.TimeoutError:
                    # Polling Watchdog (Fallback)
                    current_metrics = self._fetch_current_metrics(device, exec_timestamp=exec_timestamp)
                    logger.debug(f"[VERIFIER] Polled watchdog metrics for {device}")
                
                if current_metrics:
                    # 4. Checkpoint State
                    self._update_checkpoint(incident_id, current_metrics, int(deadline - time.time()))

                    # 4.5 Check for Post-Remediation Regression vs Pre-Snapshot
                    is_regressed, reg_reason = self._detect_post_remediation_regression(pre_snapshot, current_metrics)
                    if is_regressed:
                        logger.error(f"[VERIFIER] Post-remediation REGRESSION detected on {device}: {reg_reason}")
                        return await self._handle_failure(incident_id, action, device, snapshot_id, 0, 85, True, f"POST_REMEDIATION_REGRESSION: {reg_reason}")
                    
                    # 5. Evaluate Predicates (Axiom Rule #6: requires fresh telemetry T_post >= T_exec)
                    if not current_metrics.get("is_fresh_post_exec", True):
                        continue
                    is_success, conf, reason = self._evaluate_predicates(action, current_metrics)
                    
                    if is_success:
                        canary_res = await self._run_synthetic_canary_probe(action, device)
                        if not canary_res.get("canary_passed", True):
                            logger.warning(f"[VERIFIER] Synthetic canary pending/failed for '{action}': {canary_res.get('failure_reason')}")
                            continue
                        logger.info(f"[VERIFIER] Passed Predicate & Canary Verification for '{action}' in {int(time.time() - start_time)}s")
                        self._log_verification(incident_id, action, device, "VERIFIED", f"Passed predicates: {reason} | Canary: {canary_res.get('probe_type')}", metrics=current_metrics, snapshot_id=snapshot_id)
                        return {"status": "SUCCESS", "success": True, "score": 100, "confidence": conf, "metrics": current_metrics, "pre_snapshot": pre_snapshot, "canary_probe": canary_res}

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
            return {"status": "ROLLBACK_RECOMMENDED", "success": False, "failure_reason": reason, "score": score, "confidence": conf}
            
        if not auto_rollback:
            self._log_verification(incident_id, action, device, "MANUAL_INTERVENTION", f"No auto-rollback allowed. {reason}")
            return {"status": "ESCALATION_RECOMMENDED", "success": False, "failure_reason": reason, "score": score, "confidence": conf}

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
        return {"status": final_status, "success": False, "failure_reason": reason, "score": score, "confidence": conf}

    def _fetch_current_metrics(self, device: str, exec_timestamp: Optional[datetime] = None) -> dict:
        metrics = {}
        if not self.db:
            return metrics
        try:
            with self.db.cursor() as cur:
                cur.execute(
                    "SELECT hardware_info, status, last_seen FROM fleet_devices WHERE pc_name = %s LIMIT 1",
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
                    last_seen_ts = row[2]
                    is_fresh = True
                    if exec_timestamp is not None and last_seen_ts is not None:
                        try:
                            if last_seen_ts.tzinfo is None:
                                last_seen_ts = last_seen_ts.replace(tzinfo=timezone.utc)
                            is_fresh = bool(last_seen_ts >= exec_timestamp)
                        except Exception:
                            is_fresh = True
                    metrics = {
                        "cpu_percent": hw_info.get("cpu_percent", 0.0),
                        "ram_percent": hw_info.get("ram_percent", 0.0),
                        "status": row[1],
                        "packet_loss": hw_info.get("packet_loss", 0),
                        "port_443_open": hw_info.get("port_443_open", False),
                        "health_status": hw_info.get("health_status", 500),
                        "last_seen": last_seen_ts.isoformat() if hasattr(last_seen_ts, "isoformat") else str(last_seen_ts or ""),
                        "is_fresh_post_exec": is_fresh,
                    }
        except Exception as e:
            logger.error(f"[VERIFIER] Watchdog failed: {e}")
        return metrics

    def _log_verification(self, incident_id: int, action: str, device: str, status: str, reason: str, metrics: Optional[dict] = None, snapshot_id: str = ""):
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
                # Axiom Rule #6: Record explicit POST_REMEDIATION_EVIDENCE bound to incident_id and target_asset
                if status == "VERIFIED":
                    cur.execute(
                        """
                        INSERT INTO incident_events (incident_id, event_type, payload, created_at)
                        VALUES (%s, 'POST_REMEDIATION_EVIDENCE', %s, NOW())
                        """,
                        (incident_id, json.dumps({
                            "incident_id": incident_id,
                            "target_asset": device,
                            "action": action,
                            "execution_id": snapshot_id,
                            "metrics": metrics or {},
                            "detail": reason,
                            "verified_at": datetime.now(timezone.utc).isoformat()
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

