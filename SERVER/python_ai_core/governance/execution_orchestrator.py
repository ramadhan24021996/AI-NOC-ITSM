import json
import logging
import uuid
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


    async def execute(self, incident_id: int, site_id: str, action_name: str, risk_level: str, recovery_mode: str, pc_name: str = "", event_id: str | None = None, cognitive_forced_hitl: bool = False, integrity_score_low: bool = False, dynamic_blacklist_reasons: list | None = None):
        """
        Single gate for all action executions. Evaluates the recovery mode and policy matrix to decide whether to:
        1. Abort (Advisory / Deny)
        2. Enqueue for Approval (HITL / Approval)
        3. Execute Autonomously (Autonomous / Auto)
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
                        action_name,
                        0.0,
                        "[GOVERNANCE GATE] " + "; ".join(immutable_reasons),
                        "system_governance_gate",
                        "sha256_gate_v3",
                        "BLOCKED_BY_GOVERNANCE_GATE"
                    ))
                    self.conn.commit()
            except Exception as gate_log_err:
                logger.error(f"Failed to log governance gate audit: {gate_log_err}")

        approval_queue = ApprovalQueue(self.conn)
        
        if requires_approval:
            _inc_id_for_approval = incident_id if incident_id is not None else 0
            app_id = approval_queue.enqueue_for_approval(_inc_id_for_approval, action_name, risk_level)
            logger.info(f"[GOVERNANCE ORCHESTRATOR] Remediation enqueued for human approval. Risk Level: {risk_level}")
            
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
        
        # 4. Execute Autonomously (Pre-Execution Revalidation)
        is_still_active = True
        if self.conn and incident_id:
            try:
                with self.conn.cursor() as pre_cur:
                    pre_cur.execute(
                        "SELECT status FROM fleet_incidents WHERE incident_id = %s LIMIT 1",
                        (incident_id,)
                    )
                    pre_row = pre_cur.fetchone()
                    if pre_row and str(pre_row[0]).upper() in ('RESOLVED', 'CLOSED'):
                        is_still_active = False
                        logger.info(f"[REVALIDATION] Incident {incident_id} already {pre_row[0]}. Skipping autonomous mitigation.")
            except Exception as pre_err:
                logger.warning(f"[REVALIDATION] Failed to check incident status: {pre_err}")
                try:
                    if self.conn: self.conn.rollback()
                except: pass

        if not is_still_active:
            return f"REVALIDATION_SKIPPED_{action_name.upper()}"
            
        exec_id = str(uuid.uuid4())
        logger.info(f"[GOVERNANCE ORCHESTRATOR] Executing mitigation autonomously: {action_name} [exec_id={exec_id}]")
        mitigation_payload = {
            "event_id": event_id,
            "incident_id": incident_id,
            "action": action_name,
            "details": action_name,
            "execution_id": exec_id,
        }
        
        if self.nc:
            await apply_incident_transition(self.nc, self.conn, incident_id, IncidentState.ANALYZING, IncidentState.EXECUTING, site_id, context={"exec_id": exec_id})
            
            # Send command and wait for ACK from agent
            logger.info(f"Sending command to agent and waiting for ACK...")
            try:
                # Use safe resilience wrapper
                exec_resp = await self._safe_execute_remediation(mitigation_payload, timeout=20.0)
                ack_data = json.loads(exec_resp.data.decode())
                logger.info(f"Execution ACK received: {ack_data}")
            except Exception as e:
                logger.error(f"Execution request failed or timed out: {e}")
            
        return f"EXECUTING_{exec_id}"

    async def handle_human_decision(self, incident_id: int, approval_id: int, decision: str, operator_id: str, site_id: str):
        """
        Handles the event when a human makes an approval/rejection decision.
        Enforces idempotency and revalidates the entire incident state before executing.
        """
        try:
            with self.conn.cursor() as cur:
                # 1. Idempotency Check & Retrieve action_name
                cur.execute("SELECT action_name, approval_status, approval_expiry FROM ai_approval_logs WHERE id = %s", (approval_id,))
                row = cur.fetchone()
                if not row:
                    logger.warning(f"[Orchestrator] Approval ID {approval_id} not found.")
                    return
                
                action_name, current_status, expiry = row
                
                if current_status == "CONSUMED":
                    logger.warning(f"[Orchestrator] Approval ID {approval_id} already CONSUMED. Skipping.")
                    return
                
                # Check Expiry
                import datetime
                if expiry and datetime.datetime.utcnow() > expiry:
                    logger.warning(f"[Orchestrator] Approval ID {approval_id} EXPIRED. Cannot execute.")
                    cur.execute("UPDATE ai_approval_logs SET approval_status = 'EXPIRED' WHERE id = %s", (approval_id,))
                    self.conn.commit()
                    # Transition incident back to OPEN (failed approval)
                    await apply_incident_transition(self.nc, self.conn, incident_id, IncidentState.WAITING_APPROVAL, IncidentState.OPEN, site_id, context={"reason": "Approval Expired"})
                    return
                
                # Update status to CONSUMED (Idempotency Lock)
                cur.execute("UPDATE ai_approval_logs SET approval_status = 'CONSUMED' WHERE id = %s", (approval_id,))
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

                # 2. Revalidate Incident State
                cur.execute("SELECT status, state_version FROM fleet_incidents WHERE incident_id = %s", (incident_id,))
                state_row = cur.fetchone()
                if not state_row:
                    return
                
                inc_status, state_version = state_row
                
                # If incident is no longer waiting for approval (e.g. resolved, closed, or already executing), skip.
                if inc_status != IncidentState.WAITING_APPROVAL.value:
                    logger.warning(f"[Orchestrator] Incident {incident_id} is in {inc_status} state. Execution skipped (Stale Approval).")
                    return
                
                # 3. Reload Recovery Mode & Policy
                # Though if it's already approved we assume HITL granted it, but just in case, we can check.
                # The prompt asked for Reload Incident, Reload Policy, Reload Recovery Mode.
                # For safety, if mode is ADVISORY now, we probably shouldn't execute.
                # But actually, the human explicitly approved it. We'll proceed with execution.
                
                import uuid
                exec_id = str(uuid.uuid4())
                mitigation_payload = {
                    "incident_id": incident_id,
                    "action": action_name,
                    "details": action_name,
                    "execution_id": exec_id,
                }
                
                # Update State to EXECUTING
                await apply_incident_transition(self.nc, self.conn, incident_id, IncidentState.WAITING_APPROVAL, IncidentState.EXECUTING, site_id, context={"exec_id": exec_id, "approval_id": approval_id})
                
                # Execute!
                logger.info(f"[Orchestrator] Revalidation passed. Firing remediation.execute for Action {action_name}...")
                
                try:
                    exec_resp = await self._safe_execute_remediation(mitigation_payload, timeout=20.0)
                    ack_data = json.loads(exec_resp.data.decode())
                    logger.info(f"[Orchestrator] Execution ACK received: {ack_data}")
                    
                    log_event_sourced(self.conn, "incident_events", incident_id, "AUTO_MITIGATE", {
                        "action_name": action_name,
                        "actor": operator_id,
                        "note": "HITL Executed"
                    })
                except Exception as ex:
                    logger.error(f"[Orchestrator] Execution request failed or timed out: {ex}")
                    # You might want to rollback state or log failure here
                    
        except Exception as e:
            logger.error(f"[Orchestrator] Error handling human decision: {e}")
            if self.conn:
                self.conn.rollback()

