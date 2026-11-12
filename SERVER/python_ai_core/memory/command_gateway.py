import logging
import json
import time
import uuid
import os
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, Optional, Callable, Tuple

from .tools_memory import ToolsMemoryManager
from .policy_memory import PolicyMemoryManager

logger = logging.getLogger("COMMAND_GATEWAY")

class CapabilityCommandGateway:
    """
    Capability-Based Command Gateway for Enterprise AI NOC / AIOps Architecture.
    Design Mandates:
      1. Zero Direct Shell Execution: AI agents never execute raw shell strings directly.
      2. Strict Whitelist Enforcement: Commands must match registered tool_ids in jarvis_tools_registry.
      3. Policy & RBAC Evaluation: Evaluates risk levels against Layer 5 Policy Memory rules.
      4. Human-In-The-Loop (HITL) Gate: High-risk, destructive, or configuration changes require HITL/Approval.
      5. Immutable Audit Trail: Every attempt (allowed, denied, pending HITL, executed) is logged to jarvis_audit_trail and jarvis_tools_execution_history.
    """

    def __init__(
        self,
        tools_mgr: Optional[ToolsMemoryManager] = None,
        policy_mgr: Optional[PolicyMemoryManager] = None
    ):
        self.tools_mgr = tools_mgr or ToolsMemoryManager()
        self.policy_mgr = policy_mgr or PolicyMemoryManager()
        self.db_host = os.getenv("DB_HOST", "127.0.0.1")
        self.db_port = os.getenv("DB_PORT", "5432")
        self.db_name = os.getenv("DB_NAME", "osi_system")
        self.user = os.getenv("DB_USER", "postgres")
        self.password = os.getenv("DB_PASSWORD", "")

    def _get_connection(self):
        try:
            from shared.db_pool import get_db_connection
            return get_db_connection()
        except Exception:
            return psycopg2.connect(
                host=self.db_host,
                port=self.db_port,
                database=self.db_name,
                user=self.user,
                password=self.password
            )

    def execute_tool_capability(
        self,
        tool_id: str,
        parameters: Optional[Dict[str, Any]] = None,
        incident_id: Optional[int] = None,
        device_name: Optional[str] = None,
        operator: str = "JARVIS_AGENT",
        execution_callback: Optional[Callable[[str, Dict[str, Any]], Tuple[str, str]]] = None
    ) -> Dict[str, Any]:
        """
        Main entry point for tool execution through the Capability-Based Command Gateway.
        """
        tool_id_clean = tool_id.lower().strip()
        params = parameters or {}
        start_time = time.time()

        # Step 1: Whitelist Check
        tool_meta = self.tools_mgr.get_tool(tool_id_clean)
        if not tool_meta or not tool_meta.get("is_active"):
            err_msg = f"SECURITY ALERT: Perintah/Tool '{tool_id_clean}' tidak terdaftar pada Whitelist Command Gateway."
            logger.warning(f"[COMMAND_GATEWAY] {err_msg}")
            self._log_audit_event(
                tool_id=tool_id_clean, operator=operator, status="DENIED_NOT_IN_WHITELIST",
                details={"reason": err_msg, "params": params}
            )
            return {
                "status": "DENIED_NOT_IN_WHITELIST",
                "message": err_msg,
                "tool_id": tool_id_clean,
                "execution_duration_ms": int((time.time() - start_time) * 1000)
            }

        risk_level = tool_meta.get("risk_level", "MEDIUM")
        requires_approval = tool_meta.get("requires_approval", False)
        requires_hitl = tool_meta.get("requires_hitl", False)

        # Step 2: Policy & Governance Evaluation (Layer 5 Policy Memory)
        policy_eval = self.policy_mgr.evaluate_command_against_policies(
            command_str=f"{tool_id_clean} {json.dumps(params)}",
            risk_level=risk_level
        )

        final_effect = policy_eval.get("final_effect", "ALLOW")
        if final_effect == "DENY":
            err_msg = f"POLICY VIOLATION: Perintah '{tool_id_clean}' ditolak oleh Kebijakan Keamanan Governance."
            logger.warning(f"[COMMAND_GATEWAY] {err_msg}")
            self._log_audit_event(
                tool_id=tool_id_clean, operator=operator, status="DENIED_BY_POLICY",
                details={"policy_evaluation": policy_eval, "params": params}
            )
            return {
                "status": "DENIED_BY_POLICY",
                "message": err_msg,
                "tool_id": tool_id_clean,
                "policy_evaluation": policy_eval,
                "execution_duration_ms": int((time.time() - start_time) * 1000)
            }

        # Step 3: HITL & Approval Enforcement Gate
        if requires_approval or requires_hitl or final_effect in ["REQUIRE_APPROVAL", "FORCE_HITL"] or risk_level in ["HIGH", "CRITICAL"]:
            hitl_msg = f"HITL MANDATE: Perintah '{tool_id_clean}' (Risk: {risk_level}) memerlukan persetujuan Human-In-The-Loop (HITL) sebelum dieksekusi."
            logger.info(f"[COMMAND_GATEWAY] {hitl_msg}")
            
            # Log execution attempt as PENDING_APPROVAL
            self.tools_mgr.log_tool_execution(
                tool_id=tool_id_clean, incident_id=incident_id, device_name=device_name,
                operator=operator, parameters=params, execution_duration_ms=0,
                status="PENDING_APPROVAL", output_summary=hitl_msg
            )
            self._log_audit_event(
                tool_id=tool_id_clean, operator=operator, status="PENDING_APPROVAL",
                details={"risk_level": risk_level, "params": params}
            )
            return {
                "status": "REQUIRE_HITL_APPROVAL",
                "message": hitl_msg,
                "tool_id": tool_id_clean,
                "risk_level": risk_level,
                "requires_approval": True,
                "requires_hitl": True,
                "execution_duration_ms": int((time.time() - start_time) * 1000)
            }

        # Step 4: Execution Delegation
        output_summary = f"Tool '{tool_id_clean}' executed successfully."
        error_details = ""
        exec_status = "SUCCESS"

        if execution_callback:
            try:
                output_summary, error_details = execution_callback(tool_id_clean, params)
                if error_details:
                    exec_status = "FAILED"
            except Exception as ex:
                exec_status = "FAILED"
                error_details = str(ex)
                output_summary = f"Execution error in tool '{tool_id_clean}': {ex}"
        else:
            output_summary = f"Executed tool '{tool_id_clean}' with parameters: {params}"

        duration_ms = int((time.time() - start_time) * 1000)

        # Step 5: Immutable Logging (Execution Ledger + Audit Trail)
        self.tools_mgr.log_tool_execution(
            tool_id=tool_id_clean, incident_id=incident_id, device_name=device_name,
            operator=operator, parameters=params, execution_duration_ms=duration_ms,
            status=exec_status, output_summary=output_summary, error_details=error_details
        )
        self._log_audit_event(
            tool_id=tool_id_clean, operator=operator, status=exec_status,
            details={"output_summary": output_summary, "duration_ms": duration_ms}
        )

        return {
            "status": exec_status,
            "tool_id": tool_id_clean,
            "output": output_summary,
            "error": error_details,
            "execution_duration_ms": duration_ms
        }

    def _log_audit_event(self, tool_id: str, operator: str, status: str, details: Dict[str, Any]):
        audit_id = str(uuid.uuid4())
        sql = """
            INSERT INTO jarvis_audit_trail (
                audit_id, memory_layer, operation, operator, status, details, timestamp
            ) VALUES (
                %s::uuid, 'TOOLS', 'EXECUTE', %s, %s, %s::jsonb, CURRENT_TIMESTAMP
            );
        """
        conn = self._get_connection()
        try:
            with conn.cursor() as cur:
                cur.execute(sql, (audit_id, operator, status, json.dumps(details)))
            conn.commit()
        except Exception as e:
            logger.error(f"[COMMAND_GATEWAY] Audit log error: {e}")
        finally:
            conn.close()
