import asyncio
import json
import logging
import os
import uuid
import hmac
import hashlib
from datetime import datetime, timezone
from enum import Enum

from state_machine import IncidentState
from ai_supervisor import apply_incident_transition, log_event_sourced
from core.approval_queue import ApprovalQueue
from resilience.circuit_breaker import CircuitBreaker, with_circuit_breaker, retry_with_backoff

logger = logging.getLogger("GovernanceOrchestrator")

# Instantiate a global circuit breaker for agent execution
agent_circuit_breaker = CircuitBreaker(failure_threshold=3, recovery_timeout_sec=30)

class ExecutionMode(Enum):
    ADVISORY = "Advisory"
    HITL = "HITL"
    AUTONOMOUS = "Autonomous"

class PolicyActionAction(Enum):
    AUTO = "Auto"
    APPROVAL = "Approval"
    DENY = "Deny"

# Fallback matrix if the action is not matched perfectly.
# Any unrecognized action will fall back to APPROVAL in HITL/Autonomous, and DENY in Advisory.
POLICY_MATRIX = {
    "NOTIFY": {ExecutionMode.ADVISORY: PolicyActionAction.AUTO, ExecutionMode.HITL: PolicyActionAction.AUTO, ExecutionMode.AUTONOMOUS: PolicyActionAction.AUTO},
    "TICKET": {ExecutionMode.ADVISORY: PolicyActionAction.AUTO, ExecutionMode.HITL: PolicyActionAction.AUTO, ExecutionMode.AUTONOMOUS: PolicyActionAction.AUTO},
    "RESTART AGENT": {ExecutionMode.ADVISORY: PolicyActionAction.DENY, ExecutionMode.HITL: PolicyActionAction.APPROVAL, ExecutionMode.AUTONOMOUS: PolicyActionAction.AUTO},
    "RESTART SERVICE": {ExecutionMode.ADVISORY: PolicyActionAction.DENY, ExecutionMode.HITL: PolicyActionAction.APPROVAL, ExecutionMode.AUTONOMOUS: PolicyActionAction.APPROVAL},
    "DB MIGRATION": {ExecutionMode.ADVISORY: PolicyActionAction.DENY, ExecutionMode.HITL: PolicyActionAction.APPROVAL, ExecutionMode.AUTONOMOUS: PolicyActionAction.DENY},
    "FIREWALL CHANGE": {ExecutionMode.ADVISORY: PolicyActionAction.DENY, ExecutionMode.HITL: PolicyActionAction.APPROVAL, ExecutionMode.AUTONOMOUS: PolicyActionAction.DENY},
}

DISRUPTIVE_ACTION_KEYWORDS = (
    "RESTART", "REBOOT", "STOP", "KILL", "FLUSH", "CLEAR",
    "FIREWALL", "UPGRADE", "PATCH", "MIGRATE", "DISCONNECT", "ISOLATE", "RESET"
)

CRITICAL_INFRASTRUCTURE_KEYWORDS = (
    "pos", "gateway", "router", "switch", "server", "db", "core", "dns", "auth"
)

def evaluate_downstream_blast_radius(
    conn, target_host: str, action_name: str, hour: int | None = None
) -> dict:
    """
    Evaluates downstream blast radius of executing an action on target_host.
    Checks device_dependencies where depends_on = target_host.
    If the action is disruptive and disrupts >= 3 downstream hosts or >= 1 critical host during peak hours,
    demands HITL downgrade to protect business continuity.
    """
    result = {
        "target_host": target_host,
        "action_name": action_name,
        "downstream_count": 0,
        "critical_children": [],
        "dependent_hosts": [],
        "is_disruptive_action": False,
        "risk_downgrade_required": False,
        "reason": ""
    }
    if not target_host:
        return result

    act_upper = (action_name or "").upper()
    is_disruptive = any(kw in act_upper for kw in DISRUPTIVE_ACTION_KEYWORDS)
    result["is_disruptive_action"] = is_disruptive

    if not is_disruptive or not conn:
        return result

    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT pc_name, dep_type, criticality
                FROM device_dependencies
                WHERE LOWER(depends_on) = LOWER(%s)
                ORDER BY criticality DESC, pc_name ASC
                LIMIT 50
            """, (target_host,))
            rows = cur.fetchall()
            
            dependent_hosts = []
            critical_children = []
            for row in rows:
                child_pc = str(row[0])
                crit = str(row[2] or "MEDIUM").upper()
                dependent_hosts.append(child_pc)
                child_lower = child_pc.lower()
                if crit in ("CRITICAL", "HIGH") or any(kw in child_lower for kw in CRITICAL_INFRASTRUCTURE_KEYWORDS):
                    critical_children.append(child_pc)

            downstream_count = len(dependent_hosts)
            result["downstream_count"] = downstream_count
            result["dependent_hosts"] = dependent_hosts
            result["critical_children"] = critical_children

            # Evaluate Peak Hour (08:00 - 21:00)
            is_peak = True
            if hour is not None:
                is_peak = (8 <= hour <= 21)

            # Downgrade condition 1: >= 3 downstream dependent hosts
            if downstream_count >= 3:
                result["risk_downgrade_required"] = True
                result["reason"] = (
                    f"Downstream Blast Radius Risk: Action '{action_name}' on '{target_host}' "
                    f"will disrupt {downstream_count} dependent hosts ({', '.join(dependent_hosts[:5])})"
                )
            # Downgrade condition 2: Critical child node during peak hours
            elif len(critical_children) >= 1 and is_peak:
                result["risk_downgrade_required"] = True
                result["reason"] = (
                    f"Downstream Blast Radius Peak Hour Risk: Action '{action_name}' on '{target_host}' "
                    f"affects critical infrastructure {critical_children} during business hours (hour={hour})"
                )
            # Downgrade condition 3: Multiple critical children even off-peak
            elif len(critical_children) >= 2:
                result["risk_downgrade_required"] = True
                result["reason"] = (
                    f"Downstream Blast Radius High Severity Risk: Action '{action_name}' on '{target_host}' "
                    f"affects multiple critical downstream nodes {critical_children}"
                )
    except Exception as err:
        logger.warning(f"[BLAST RADIUS EVALUATOR] Error evaluating downstream impact for {target_host}: {err}")

    return result

def get_policy_decision(action_name: str, mode: ExecutionMode) -> PolicyActionAction:
    action_upper = action_name.upper()
    for key, matrix in POLICY_MATRIX.items():
        if key in action_upper:
            return matrix[mode]
    # Default Fallback for unknown actions: DENY for Advisory, APPROVAL for HITL/Autonomous
    if mode == ExecutionMode.ADVISORY:
        return PolicyActionAction.DENY
    return PolicyActionAction.APPROVAL

class GovernanceExecutionOrchestrator:
    def __init__(self, nc, conn):
        self.nc = nc
        self.conn = conn

    @with_circuit_breaker(agent_circuit_breaker)
    @retry_with_backoff(max_retries=1, initial_delay=2.0)
    async def _safe_execute_remediation(self, mitigation_payload: dict, timeout: float = 20.0):
        """Execute remediation with Timeout, Retry, and Circuit Breaker"""
        if not self.nc:
            raise Exception("NATS connection not initialized.")
        return await self.nc.request("remediation.execute", json.dumps(mitigation_payload).encode(), timeout=timeout)

    def _resolve_incident_status(self, cur, incident_id: int):
        """
        Incident Status Resolver: Uses ONLY incident_states as the Single Source of Truth.
        Retrieves state_version for Optimistic Concurrency Validation.
        Returns (final_status: str, state_version: int)
        """
        cur.execute("""
            SELECT status FROM incident_states 
            WHERE incident_id = %s ORDER BY created_at DESC LIMIT 1
        """, (incident_id,))
        state_row = cur.fetchone()
        
        cur.execute("SELECT state_version FROM fleet_incidents WHERE incident_id = %s", (incident_id,))
        version_row = cur.fetchone()
        
        if not state_row:
            final_status = "UNKNOWN"
        else:
            final_status = str(state_row[0]).upper()
        state_version = version_row[0] if version_row and version_row[0] is not None else 1
        
        return final_status, state_version


    async def execute(self, incident_id: int, site_id: str, action_name: str, risk_level: str, recovery_mode: str, pc_name: str = "", event_id: str | None = None, cognitive_forced_hitl: bool = False, integrity_score_low: bool = False, dynamic_blacklist_reasons: list | None = None, expected_version: int | None = None):
        """
        Single gate for all action executions. Evaluates the recovery mode and policy matrix to decide whether to:
        1. Abort (Advisory / Deny)
        2. Enqueue for Approval (HITL / Approval)
        3. Execute Autonomously (Autonomous / Auto)
        Uses Distributed Locks and Optimistic Concurrency to prevent race conditions.
        """
        try:
            mode = ExecutionMode(recovery_mode)
        except ValueError:
            logger.warning(f"Unknown recovery mode '{recovery_mode}', falling back to HITL.")
            mode = ExecutionMode.HITL

        policy_decision = get_policy_decision(action_name, mode)
        logger.info(f"[GOVERNANCE ORCHESTRATOR] Action: {action_name} | Mode: {mode.value} | Decision: {policy_decision.value}")

        requires_approval = False
        immutable_reasons = []

        # 1. Evaluate hard blocks (Cognitive Safety, Blacklist, Integrity)
        if cognitive_forced_hitl:
            immutable_reasons.append("Cognitive Safety Layer Forced HITL")
            requires_approval = True
        
        if integrity_score_low:
            immutable_reasons.append("Low Telemetry Integrity Score")
            requires_approval = True

        if dynamic_blacklist_reasons:
            immutable_reasons.extend(dynamic_blacklist_reasons)
            requires_approval = True

        # 1b. Blast Radius Cascade Throttling Check (Max 5 concurrent remediations per site in 60s)
        if self.conn and site_id:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        SELECT COUNT(*) FROM hitl_audit_logs 
                        WHERE created_at > NOW() - INTERVAL '60 seconds'
                    """)
                    row_cnt = cur.fetchone()
                    recent_cnt = row_cnt[0] if row_cnt else 0
                    if recent_cnt >= 5:
                        immutable_reasons.append(f"Blast Radius Cascade Throttling Active ({recent_cnt} actions in 60s)")
                        requires_approval = True
            except Exception as _tb_err:
                logger.debug(f"[CASCADE THROTTLE] Check skipped: {_tb_err}")

        # 1c. Downstream Blast Radius Predictive Guard (Pillar 2)
        if self.conn and pc_name:
            try:
                curr_hour = datetime.now(timezone.utc).hour
                blast_eval = evaluate_downstream_blast_radius(self.conn, pc_name, action_name, hour=curr_hour)
                if blast_eval.get("risk_downgrade_required", False):
                    blast_reason = blast_eval.get("reason", "Downstream Blast Radius threshold exceeded")
                    logger.warning(f"[GOVERNANCE BLAST RADIUS] Downgrading to HITL: {blast_reason}")
                    immutable_reasons.append(blast_reason)
                    requires_approval = True
                    # Record in ai_blast_radius_logs if incident_id is available
                    if incident_id:
                        try:
                            with self.conn.cursor() as cur:
                                cur.execute("""
                                    INSERT INTO ai_blast_radius_logs (incident_id, impacted_sites, impacted_pcs, impacted_printers, impacted_dashboards, impact_level)
                                    VALUES (%s, %s, %s, %s, %s, %s)
                                """, (
                                    incident_id,
                                    1,
                                    blast_eval.get("downstream_count", 0),
                                    0,
                                    0,
                                    "CRITICAL" if len(blast_eval.get("critical_children", [])) > 0 else "HIGH"
                                ))
                                self.conn.commit()
                        except Exception as blast_log_err:
                            logger.debug(f"Failed to log ai_blast_radius_logs: {blast_log_err}")
            except Exception as br_err:
                logger.debug(f"[GOVERNANCE BLAST RADIUS] Check skipped: {br_err}")


        # 2. Evaluate Policy Matrix Decision
        if policy_decision == PolicyActionAction.DENY or mode == ExecutionMode.ADVISORY:
            # Advisory Mode OR explicitly denied action
            logger.info(f"[GOVERNANCE ORCHESTRATOR] Execution aborted. Mode={mode.value}, Decision={policy_decision.value}.")
            if self.conn and incident_id:
                log_event_sourced(self.conn, "incident_events", incident_id, "ADVISORY_GENERATED", {
                    "action_name": action_name,
                    "risk_level": risk_level,
                    "reason": "Aborted by Governance Orchestrator"
                })
                await apply_incident_transition(self.nc, self.conn, incident_id, IncidentState.ANALYZING, IncidentState.OPEN, site_id, context={"reason": f"Governance blocked execution: {policy_decision.value}"})
            return "ADVISORY_RECOMMENDATION"

        if policy_decision == PolicyActionAction.APPROVAL:
            requires_approval = True
            immutable_reasons.append("Policy Matrix requires approval for this action")

        # 3. Log any forced overrides to DB
        if requires_approval and immutable_reasons and self.conn and incident_id:
            try:
                with self.conn.cursor() as cur:
                    cur.execute("""
                        INSERT INTO hitl_audit_logs (
                            incident_id, action_name, critic_score, force_hitl_reason,
                            approved_by, approval_signature, action_taken
                        ) VALUES (%s, %s, %s, %s, %s, %s, %s)
                    """, (
                        incident_id,
                        action_name if (action_name and action_name != "unknown") else "GOVERNANCE_EVALUATION",
                        0.85,
                        "[GOVERNANCE GATE] " + "; ".join(immutable_reasons),
                        "system_governance_gate",
                        "sha256_gate_v3",
                        "BLOCKED_BY_GOVERNANCE_GATE"
                    ))
                    self.conn.commit()
            except Exception as gate_log_err:
                logger.error(f"Failed to log governance gate audit: {gate_log_err}")

        approval_queue = ApprovalQueue(self.conn)
        
        # Distributed Lock (PostgreSQL Advisory Transaction Lock)
        # Using xact_lock ensures it automatically releases at the end of the transaction,
        # preventing lock leaks in connection pools if crash occurs.
        lock_id = incident_id
        if self.conn and incident_id:
            try:
                with self.conn.cursor() as cur:
                    # Transaction-level lock
                    cur.execute("SELECT pg_try_advisory_xact_lock(%s)", (lock_id,))
                    lock_acquired = cur.fetchone()[0]
                    if not lock_acquired:
                        logger.warning(f"[ORCHESTRATOR] Failed to acquire lock for Incident {incident_id}. Another worker is executing.")
                        return "ABORTED_LOCK_FAILED"
            except Exception as e:
                logger.error(f"[ORCHESTRATOR] Lock error: {e}")

        try:
            # Revalidate state and version (Optimistic Concurrency)
            if self.conn and incident_id:
                try:
                    with self.conn.cursor() as cur:
                        final_status, state_version = self._resolve_incident_status(cur, incident_id)
                        
                        if final_status == "UNKNOWN":
                            logger.warning(f"[ORCHESTRATOR] Incident {incident_id} not found in incident_states (UNKNOWN). Aborting for safety.")
                            return "ABORTED_UNKNOWN_STATE"
                            
                        if expected_version is not None and state_version != expected_version:
                            logger.warning(f"[ORCHESTRATOR] TOCTOU Prevention: Incident {incident_id} version changed ({expected_version} -> {state_version}). Aborting.")
                            return "ABORTED_VERSION_MISMATCH"
                            
                        if final_status in ('RESOLVED', 'CLOSED', 'SOLVED VERIFIED'):
                            logger.info(f"[ORCHESTRATOR] Incident {incident_id} officially {final_status}. Skipping execution.")
                            return "ABORTED_ALREADY_RESOLVED"
                except Exception as e:
                    logger.warning(f"[ORCHESTRATOR] Revalidation error: {e}")

            if requires_approval or policy_decision == PolicyActionAction.APPROVAL:
                app_id = ApprovalQueue.enqueue(self.conn, incident_id, action_name, risk_level, "System", "Autonomous Governance Gate", "\n".join(immutable_reasons) if requires_approval else "HITL Policy Matrix enforced.")
                logger.info(f"[Governance Orchestrator] Placed Action {action_name} in Approval Queue (ID: {app_id}).")
                log_event_sourced(self.conn, "approval_events", app_id, "REQUESTED", {
                    "incident_id": incident_id,
                    "action_name": action_name,
                    "risk_level": risk_level
                })

                approval_event_payload = {
                    "approval_id": app_id,
                    "incident_id": incident_id,
                    "site_id": site_id,
                    "action_name": action_name,
                    "risk_level": risk_level,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
                if self.nc:
                    await self.nc.publish(f"approval.site.{site_id}", json.dumps(approval_event_payload).encode())

                if self.conn and incident_id:
                    await apply_incident_transition(self.nc, self.conn, incident_id, IncidentState.ANALYZING, IncidentState.WAITING_APPROVAL, site_id, context={"reason": "HITL Required by Governance"})
                return "AWAITING_APPROVAL"
        
            # 4. Execute Autonomously (Token Generation & NATS Publish)
            logger.info(f"[Orchestrator] Firing autonomous remediation.execute for Action {action_name}...")
            
            exec_id = str(uuid.uuid4())
            token_payload = {
                "incident_id": incident_id,
                "version": expected_version if expected_version else 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "ttl_sec": 60
            }
            
            # Generate HMAC for Token Integrity (GAP B)
            secret_key = os.getenv("OSI_SECURITY_KEY", "ENTERPRISE_AIOPS_SECRET_KEY_V1").encode("utf-8")
            payload_bytes = json.dumps(token_payload, sort_keys=True).encode('utf-8')
            signature = hmac.new(secret_key, payload_bytes, hashlib.sha256).hexdigest()
            token_payload["signature"] = signature
            
            mitigation_payload = {
                "incident_id": incident_id,
                "action": action_name,
                "details": pc_name,
                "risk_level": risk_level,
                "execution_id": exec_id,
                "event_id": event_id,
                # Execution Token details
                "execution_token": token_payload
            }
            
            if self.conn and incident_id:
                await apply_incident_transition(self.nc, self.conn, incident_id, IncidentState.ANALYZING, IncidentState.EXECUTING, site_id, context={"exec_id": exec_id, "reason": "Autonomous Execution Approved"})
                
            try:
                exec_resp = await self._safe_execute_remediation(mitigation_payload)
                ack_data = json.loads(exec_resp.data.decode())
                logger.info(f"[Orchestrator] Execution ACK received: {ack_data}")
                if self.conn and incident_id:
                    log_event_sourced(self.conn, "incident_events", incident_id, "EXECUTION_EVIDENCE", {
                        "incident_id": incident_id,
                        "target_asset": pc_name,
                        "action_name": action_name,
                        "execution_id": exec_id,
                        "actor": "AUTONOMOUS_ORCHESTRATOR",
                        "ack": ack_data,
                        "executed_at": datetime.now(timezone.utc).isoformat()
                    })
                return "AUTO_EXECUTED"
            except Exception as ex:
                logger.error(f"[Orchestrator] Execution request failed or timed out: {ex}")
                if self.conn and incident_id:
                    await apply_incident_transition(self.nc, self.conn, incident_id, IncidentState.EXECUTING, IncidentState.ANALYZING, site_id, context={"reason": f"Execution failed: {str(ex)}"})
                return "AUTO_EXECUTION_FAILED"
        finally:
            # pg_try_advisory_xact_lock releases automatically on commit/rollback.
            if self.conn:
                try:
                    self.conn.commit()
                except Exception:
                    pass

    async def handle_human_decision(self, incident_id: int, approval_id: int, decision: str, operator_id: str, site_id: str):
        """
        Handles the event when a human makes an approval/rejection decision.
        Enforces idempotency and revalidates the entire incident state before executing.
        """
        try:
            with self.conn.cursor() as cur:
                # 1. Idempotency Check & Retrieve action_name (with fallback by incident_id for Portal approval_queue IDs)
                resolved_approval_id = approval_id
                row = None
                if approval_id:
                    cur.execute("SELECT id, action_name, approval_status, approval_expiry FROM ai_approval_logs WHERE id = %s", (approval_id,))
                    row = cur.fetchone()
                if not row and incident_id:
                    cur.execute(
                        "SELECT id, action_name, approval_status, approval_expiry FROM ai_approval_logs WHERE incident_id = %s ORDER BY id DESC LIMIT 1",
                        (incident_id,)
                    )
                    row = cur.fetchone()
                if not row:
                    logger.warning(f"[Orchestrator] Approval ID {approval_id} (Incident {incident_id}) not found in ai_approval_logs.")
                    return

                resolved_approval_id, action_name, current_status, expiry = row

                if current_status == "CONSUMED":
                    logger.warning(f"[Orchestrator] Approval ID {resolved_approval_id} already CONSUMED. Skipping.")
                    return

                # Check Expiry
                import datetime as _dt
                if expiry and _dt.datetime.now(_dt.timezone.utc).replace(tzinfo=None) > expiry:
                    logger.warning(f"[Orchestrator] Approval ID {resolved_approval_id} EXPIRED. Cannot execute.")
                    cur.execute("UPDATE ai_approval_logs SET approval_status = 'EXPIRED' WHERE id = %s", (resolved_approval_id,))
                    self.conn.commit()
                    await apply_incident_transition(self.nc, self.conn, incident_id, IncidentState.WAITING_APPROVAL, IncidentState.OPEN, site_id, context={"reason": "Approval Expired"})
                    return

                # Update status to CONSUMED (Idempotency Lock)
                cur.execute("UPDATE ai_approval_logs SET approval_status = 'CONSUMED' WHERE id = %s", (resolved_approval_id,))
                self.conn.commit()

                if decision != "APPROVED" and decision != "EMERGENCY_OVERRIDE_APPROVED":
                    logger.info(f"[Orchestrator] Action {action_name} for Incident {incident_id} REJECTED by {operator_id}.")
                    log_event_sourced(self.conn, "incident_events", incident_id, "APPROVAL_DENIED", {
                        "action_name": action_name,
                        "actor": operator_id,
                        "decision": decision
                    })
                    await apply_incident_transition(self.nc, self.conn, incident_id, IncidentState.WAITING_APPROVAL, IncidentState.OPEN, site_id, context={"reason": f"Approval {decision}"})
                    return

                # 2. Revalidate Incident State via Resolver (Single Source of Truth)
                final_status, state_version = self._resolve_incident_status(cur, incident_id)
                if final_status == "UNKNOWN":
                    return

                inc_status = final_status

                # Accept WAITING_APPROVAL, APPROVAL_PENDING, or IN_PROGRESS (set by Go Portal upon HITL click)
                valid_hitl_states = {
                    IncidentState.WAITING_APPROVAL,
                    IncidentState.APPROVAL_PENDING,
                    "IN_PROGRESS",
                    "OPEN",
                    "TRIGGERED",
                    "ANALYZING",
                }
                if inc_status not in valid_hitl_states:
                    logger.warning(f"[Orchestrator] Incident {incident_id} is in {inc_status} state. Execution skipped (Stale Approval).")
                    return

                # Resolve target device name for verification & execution binding
                target_device = action_name
                try:
                    cur.execute("SELECT device_name FROM incidents WHERE incident_id = %s LIMIT 1", (incident_id,))
                    dev_row = cur.fetchone()
                    if dev_row and dev_row[0]:
                        target_device = dev_row[0]
                except Exception:
                    pass

                exec_id = str(uuid.uuid4())

                token_payload = {
                    "incident_id": incident_id,
                    "version": state_version,
                    "created_at": datetime.now(timezone.utc).isoformat(),
                    "ttl_sec": 120
                }

                secret_key = os.getenv("OSI_SECURITY_KEY", "ENTERPRISE_AIOPS_SECRET_KEY_V1").encode("utf-8")
                payload_bytes = json.dumps(token_payload, sort_keys=True).encode('utf-8')
                signature = hmac.new(secret_key, payload_bytes, hashlib.sha256).hexdigest()
                token_payload["signature"] = signature

                mitigation_payload = {
                    "incident_id": incident_id,
                    "action": action_name,
                    "details": target_device,
                    "execution_id": exec_id,
                    "execution_token": token_payload
                }

                # Update State to EXECUTING
                await apply_incident_transition(self.nc, self.conn, incident_id, inc_status, IncidentState.EXECUTING, site_id, context={"exec_id": exec_id, "approval_id": resolved_approval_id})

                # Execute!
                logger.info(f"[Orchestrator] Revalidation passed. Firing remediation.execute for Action {action_name} on {target_device}...")

                try:
                    exec_resp = await self._safe_execute_remediation(mitigation_payload, timeout=20.0)
                    ack_data = json.loads(exec_resp.data.decode())
                    logger.info(f"[Orchestrator] Execution ACK received: {ack_data}")

                    log_event_sourced(self.conn, "incident_events", incident_id, "AUTO_MITIGATE", {
                        "action_name": action_name,
                        "actor": operator_id,
                        "note": "HITL Executed"
                    })
                    log_event_sourced(self.conn, "incident_events", incident_id, "EXECUTION_EVIDENCE", {
                        "incident_id": incident_id,
                        "target_asset": target_device,
                        "action_name": action_name,
                        "execution_id": exec_id,
                        "actor": operator_id,
                        "ack": ack_data,
                        "executed_at": datetime.now(timezone.utc).isoformat()
                    })

                    # Axiom Rule #6: Trigger post-remediation background verification before resolving
                    try:
                        from supervisor.handlers.approval_handler import run_background_verification
                        asyncio.create_task(
                            run_background_verification(
                                nc=self.nc,
                                incident_id=incident_id,
                                validated_action_name=action_name,
                                pc_name=target_device,
                                exec_id=exec_id,
                                site_id_str=site_id,
                                event_id=f"hitl-{resolved_approval_id}",
                                incident_details={}
                            )
                        )
                    except Exception as ver_err:
                        logger.error(f"[Orchestrator] Failed to schedule post-HITL verification: {ver_err}")
                except Exception as ex:
                    logger.error(f"[Orchestrator] Execution request failed or timed out: {ex}")
                    
        except Exception as e:
            logger.error(f"[Orchestrator] Error handling human decision: {e}")
            if self.conn:
                self.conn.rollback()

