"""
HITL Authorization Gate (governance/hitl_authorization_gate.py)

Enforces the Final Execution Authorization Gate before any remediation action reaches the executor:
- Fail-Closed by default: UNKNOWN action / UNKNOWN risk / Incomplete Provenance -> BLOCKED
- Zero AI Confidence Bypass: AI confidence = 1.0 CANNOT override HITL requirements
- Real-time DB Verification: Re-verifies approval state in PostgreSQL immediately prior to execution
- Zero Fabricated IDs: Missing HITL IDs remain NULL; blocked execution attempts leave explicit evidence
"""

import logging
import psycopg2
import psycopg2.extras
import os
import json
import time
from typing import Dict, Any, Optional

from governance.action_matrix import ActionMatrix

logger = logging.getLogger("HITL_AUTHORIZATION_GATE")

DB_HOST = os.environ.get("DB_HOST", "127.0.0.1")
DB_PORT = os.environ.get("DB_PORT", "5433" if DB_HOST == "127.0.0.1" else "5432")
DB_NAME = os.environ.get("DB_NAME", "osi_system")
DB_USER = os.environ.get("DB_USER", "postgres")
DB_PASSWORD = os.environ.get("DB_PASSWORD", os.environ.get("POSTGRES_PASSWORD", "SecurePassword_123!"))


class HITLAuthorizationGate:
    def __init__(self):
        self.action_matrix = ActionMatrix()

    def _get_connection(self):
        return psycopg2.connect(
            host=DB_HOST, port=DB_PORT, dbname=DB_NAME,
            user=DB_USER, password=DB_PASSWORD
        )

    def authorize_remediation_execution(
        self,
        action_id: str,
        ai_confidence: float = 1.0,
        policy_passed: bool = True,
        incident_id: Optional[str] = None,
        trace_id: Optional[str] = None,
        decision_id: Optional[str] = None,
        hitl_decision_id: Optional[str] = None,
        playbook_id: Optional[int] = None,
        playbook_status: Optional[str] = None,
        simulate_db_error: bool = False,
        simulate_service_down: bool = False
    ) -> Dict[str, Any]:
        """
        Final Execution Authorization Gate.
        Evaluates 7 safety dimensions prior to dispatching execution.
        Returns: Dict with status ('AUTHORIZED' or 'BLOCKED') and explicit forensic reason.
        """
        start_ts = time.strftime("%Y-%m-%dT%H:%M:%SZ")

        # 1. Action & Risk Classification
        classification = self.action_matrix.classify_action(action_id)
        level = classification.get("level", "UNKNOWN")
        approval_req = classification.get("approval", "UNKNOWN_ACTION_BLOCKED")
        risk_score = classification.get("risk_score", 999)

        if level == "UNKNOWN" or approval_req == "UNKNOWN_ACTION_BLOCKED" or risk_score == 999:
            reason = f"UNKNOWN_ACTION_OR_RISK_BLOCKED (Action: '{action_id}')"
            self._log_audit_evidence(action_id, trace_id, incident_id, decision_id, hitl_decision_id, playbook_id, "BLOCKED", reason)
            return {"status": "BLOCKED", "reason": reason, "classification": classification}

        # 2. Policy Evaluation Failure Check
        if not policy_passed:
            reason = f"POLICY_EVALUATION_DENIED for action '{action_id}'"
            self._log_audit_evidence(action_id, trace_id, incident_id, decision_id, hitl_decision_id, playbook_id, "BLOCKED", reason)
            return {"status": "BLOCKED", "reason": reason, "classification": classification}

        # 3. Provenance Chain Completeness Check
        if not incident_id or not trace_id or not decision_id:
            reason = f"INCOMPLETE_PROVENANCE_CHAIN (Missing: incident_id={bool(incident_id)}, trace_id={bool(trace_id)}, decision_id={bool(decision_id)})"
            self._log_audit_evidence(action_id, trace_id, incident_id, decision_id, hitl_decision_id, playbook_id, "BLOCKED", reason)
            return {"status": "BLOCKED", "reason": reason, "classification": classification}

        # 4. Playbook Eligibility Check
        if playbook_id is not None:
            if not playbook_status or playbook_status not in ["ACTIVE", "ELIGIBLE_FOR_ACTIVATION"]:
                reason = f"INVALID_OR_INELIGIBLE_PLAYBOOK (ID: {playbook_id}, Status: '{playbook_status}')"
                self._log_audit_evidence(action_id, trace_id, incident_id, decision_id, hitl_decision_id, playbook_id, "BLOCKED", reason)
                return {"status": "BLOCKED", "reason": reason, "classification": classification}

        # 5. Check if Action Requires HITL
        requires_hitl = approval_req in ["HITL_SINGLE", "MANDATORY_HITL", "DUAL_APPROVAL_MANDATORY"]

        if requires_hitl:
            # Rule: AI confidence = 1.0 CANNOT override HITL requirement
            if not hitl_decision_id:
                reason = f"MISSING_HITL_DECISION_ID_FOR_HIGH_RISK_ACTION (Action: '{action_id}', ApprovalReq: '{approval_req}', Confidence: {ai_confidence})"
                self._log_audit_evidence(action_id, trace_id, incident_id, decision_id, None, playbook_id, "BLOCKED", reason)
                return {"status": "BLOCKED", "reason": reason, "classification": classification}

            # Simulated Service / DB Outage Fail-Closed Test
            if simulate_service_down or simulate_db_error:
                reason = f"HITL_SERVICE_OR_DATABASE_UNAVAILABLE_FAIL_CLOSED (Action: '{action_id}')"
                self._log_audit_evidence(action_id, trace_id, incident_id, decision_id, hitl_decision_id, playbook_id, "BLOCKED", reason)
                return {"status": "BLOCKED", "reason": reason, "classification": classification}

            # Query Real-Time PostgreSQL Approval Record (TOCTOU Defense)
            conn = None
            try:
                conn = self._get_connection()
                with conn.cursor(cursor_factory=psycopg2.extras.DictCursor) as cur:
                    cur.execute("""
                        SELECT hitl_decision_id, status, approved_by, risk_level
                        FROM governance_approvals
                        WHERE hitl_decision_id = %s;
                    """, (hitl_decision_id,))
                    app_record = cur.fetchone()

                if not app_record:
                    reason = f"APPROVAL_RECORD_NOT_FOUND_IN_DB (hitl_decision_id: '{hitl_decision_id}')"
                    self._log_audit_evidence(action_id, trace_id, incident_id, decision_id, hitl_decision_id, playbook_id, "BLOCKED", reason)
                    return {"status": "BLOCKED", "reason": reason, "classification": classification}

                app_status = (app_record["status"] or "").upper()
                if app_status != "APPROVED":
                    reason = f"HITL_APPROVAL_NOT_GRANTED_STATUS_{app_status} (hitl_decision_id: '{hitl_decision_id}')"
                    self._log_audit_evidence(action_id, trace_id, incident_id, decision_id, hitl_decision_id, playbook_id, "BLOCKED", reason)
                    return {"status": "BLOCKED", "reason": reason, "classification": classification}

            except Exception as db_err:
                reason = f"HITL_DATABASE_ERROR_FAIL_CLOSED: {db_err}"
                self._log_audit_evidence(action_id, trace_id, incident_id, decision_id, hitl_decision_id, playbook_id, "BLOCKED", reason)
                return {"status": "BLOCKED", "reason": reason, "classification": classification}
            finally:
                if conn:
                    try: conn.close()
                    except Exception: pass

        # All Gates Passed -> Authorized
        self._log_audit_evidence(action_id, trace_id, incident_id, decision_id, hitl_decision_id, playbook_id, "AUTHORIZED", "ALL_AUTHORIZATION_GATES_PASSED")
        return {
            "status": "AUTHORIZED",
            "reason": "ALL_AUTHORIZATION_GATES_PASSED",
            "classification": classification,
            "authorized_at": start_ts
        }

    def _log_audit_evidence(
        self,
        action_id: str,
        trace_id: Optional[str],
        incident_id: Optional[str],
        decision_id: Optional[str],
        hitl_decision_id: Optional[str],
        playbook_id: Optional[int],
        status: str,
        reason: str
    ):
        logger.info(f"[HITL GATE] Result={status} | Action={action_id} | Trace={trace_id} | Reason={reason}")
        conn = None
        try:
            conn = self._get_connection()
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO system_audits (
                        status, recommendation, raw_json, trace_id, timestamp
                    ) VALUES (%s, %s, %s, %s, NOW());
                """, (
                    status, f"Action: {action_id} | Reason: {reason}",
                    json.dumps({
                        "component": "HITL_AUTHORIZATION_GATE",
                        "action_id": action_id, "incident_id": incident_id,
                        "decision_id": decision_id, "hitl_decision_id": hitl_decision_id,
                        "playbook_id": playbook_id, "reason": reason
                    }), trace_id
                ))
            conn.commit()
        except Exception as e:
            if conn:
                try: conn.rollback()
                except Exception: pass
            logger.error(f"[HITL GATE] Error logging audit evidence: {e}")
        finally:
            if conn:
                try: conn.close()
                except Exception: pass
