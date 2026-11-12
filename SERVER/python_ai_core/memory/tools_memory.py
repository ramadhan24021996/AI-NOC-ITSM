import logging
import json
import uuid
import os
import time
import psycopg2
from psycopg2.extras import RealDictCursor
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("TOOLS_MEMORY")

class ToolsMemoryManager:
    """
    Tools Memory Manager for Jarvis AI NOC:
    - Manages the tool registry (jarvis_tools_registry): Tool ID, name, category,
      description, risk level, required parameters, approval/HITL policies, rollback procedures.
    - Manages tool execution history (jarvis_tools_execution_history): Logs parameters,
      duration, incident_id, device_name, status, output summary, error details.
    - Computes live analytics: success rate %, average latency, total execution counts.
    - Full integration with PostgreSQL & Jarvis Enterprise Memory System.
    """

    def __init__(self):
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

    def register_tool(
        self,
        tool_id: str,
        tool_name: str,
        description: str,
        category: str = "SYSTEM_OPS",
        risk_level: str = "MEDIUM",
        requires_approval: bool = False,
        requires_hitl: bool = False,
        parameter_schema: Optional[Dict[str, Any]] = None,
        rollback_procedure: str = "",
        author: str = "SYSTEM"
    ) -> Dict[str, Any]:
        """
        Registers or updates a tool definition in jarvis_tools_registry.
        """
        tool_id_clean = tool_id.lower().strip()
        category_clean = category.upper().strip()
        risk_clean = risk_level.upper().strip()
        schema_json = json.dumps(parameter_schema or {})

        sql = """
            INSERT INTO jarvis_tools_registry (
                tool_id, tool_name, category, description, risk_level,
                requires_approval, requires_hitl, parameter_schema, rollback_procedure,
                author, version, is_active, updated_at
            ) VALUES (
                %s, %s, %s, %s, %s,
                %s, %s, %s::jsonb, %s,
                %s, 1, TRUE, CURRENT_TIMESTAMP
            )
            ON CONFLICT (tool_id) DO UPDATE SET
                tool_name = EXCLUDED.tool_name,
                category = EXCLUDED.category,
                description = EXCLUDED.description,
                risk_level = EXCLUDED.risk_level,
                requires_approval = EXCLUDED.requires_approval,
                requires_hitl = EXCLUDED.requires_hitl,
                parameter_schema = EXCLUDED.parameter_schema,
                rollback_procedure = EXCLUDED.rollback_procedure,
                version = jarvis_tools_registry.version + 1,
                updated_at = CURRENT_TIMESTAMP
            RETURNING tool_id, tool_name, category, risk_level, version, updated_at;
        """

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (
                    tool_id_clean, tool_name, category_clean, description, risk_clean,
                    requires_approval, requires_hitl, schema_json, rollback_procedure, author
                ))
                row = cur.fetchone()
            conn.commit()
            logger.info(f"[TOOLS_MEMORY] Registered tool '{tool_id_clean}' (Risk: {risk_clean}, Category: {category_clean})")
            return dict(row)
        except Exception as e:
            conn.rollback()
            logger.error(f"[TOOLS_MEMORY] Failed to register tool '{tool_id_clean}': {e}")
            raise e
        finally:
            conn.close()

    def get_tool(self, tool_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves a tool metadata definition by tool_id.
        """
        sql = "SELECT * FROM jarvis_tools_registry WHERE tool_id = %s;"
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, (tool_id.lower().strip(),))
                row = cur.fetchone()
            return dict(row) if row else None
        except Exception as e:
            logger.error(f"[TOOLS_MEMORY] Error fetching tool '{tool_id}': {e}")
            return None
        finally:
            conn.close()

    def list_tools(self, category: Optional[str] = None, active_only: bool = True) -> List[Dict[str, Any]]:
        """
        Lists registered tools, optionally filtered by category.
        """
        where_clauses = []
        params = []
        if active_only:
            where_clauses.append("is_active = TRUE")
        if category:
            where_clauses.append("category = %s")
            params.append(category.upper().strip())

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        sql = f"SELECT * FROM jarvis_tools_registry{where_sql} ORDER BY tool_name ASC;"

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[TOOLS_MEMORY] Error listing tools: {e}")
            return []
        finally:
            conn.close()

    def log_tool_execution(
        self,
        tool_id: str,
        incident_id: Optional[int] = None,
        device_name: Optional[str] = None,
        operator: str = "JARVIS_AGENT",
        parameters: Optional[Dict[str, Any]] = None,
        execution_duration_ms: int = 0,
        status: str = "SUCCESS",
        output_summary: str = "",
        error_details: str = ""
    ) -> Dict[str, Any]:
        """
        Logs a tool execution to jarvis_tools_execution_history and updates tool execution stats in jarvis_tools_registry.
        """
        tool_id_clean = tool_id.lower().strip()
        status_clean = status.upper().strip()
        exec_uuid = str(uuid.uuid4())
        params_json = json.dumps(parameters or {})

        sql_log = """
            INSERT INTO jarvis_tools_execution_history (
                execution_id, tool_id, incident_id, device_name, operator, parameters,
                execution_duration_ms, status, output_summary, error_details, timestamp
            ) VALUES (
                %s::uuid, %s, %s, %s, %s, %s::jsonb,
                %s, %s, %s, %s, CURRENT_TIMESTAMP
            )
            RETURNING execution_id, tool_id, incident_id, device_name, status, timestamp;
        """

        is_success = (status_clean == "SUCCESS")
        sql_update_stats = f"""
            UPDATE jarvis_tools_registry
            SET total_executions = total_executions + 1,
                successful_executions = successful_executions + {1 if is_success else 0},
                failed_executions = failed_executions + {0 if is_success else 1},
                last_executed_at = CURRENT_TIMESTAMP,
                updated_at = CURRENT_TIMESTAMP
            WHERE tool_id = %s;
        """

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql_log, (
                    exec_uuid, tool_id_clean, incident_id, device_name, operator,
                    params_json, execution_duration_ms, status_clean, output_summary, error_details
                ))
                row = cur.fetchone()
                cur.execute(sql_update_stats, (tool_id_clean,))
            conn.commit()
            logger.info(f"[TOOLS_MEMORY] Logged execution '{exec_uuid}' for tool '{tool_id_clean}' (Status: {status_clean})")
            return dict(row)
        except Exception as e:
            conn.rollback()
            logger.error(f"[TOOLS_MEMORY] Failed to log tool execution: {e}")
            raise e
        finally:
            conn.close()

    def get_execution_history(
        self,
        tool_id: Optional[str] = None,
        incident_id: Optional[int] = None,
        device_name: Optional[str] = None,
        limit: int = 20
    ) -> List[Dict[str, Any]]:
        """
        Retrieves recent tool execution logs filtered by tool_id, incident_id, or device_name.
        """
        where_clauses = []
        params = []

        if tool_id:
            where_clauses.append("tool_id = %s")
            params.append(tool_id.lower().strip())
        if incident_id:
            where_clauses.append("incident_id = %s")
            params.append(incident_id)
        if device_name:
            where_clauses.append("device_name = %s")
            params.append(device_name)

        where_sql = (" WHERE " + " AND ".join(where_clauses)) if where_clauses else ""
        sql = f"""
            SELECT execution_id, tool_id, incident_id, device_name, operator, parameters,
                   execution_duration_ms, status, output_summary, error_details, timestamp
            FROM jarvis_tools_execution_history
            {where_sql}
            ORDER BY timestamp DESC
            LIMIT %s;
        """
        params.append(limit)

        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                cur.execute(sql, tuple(params))
                rows = cur.fetchall()
            return [dict(r) for r in rows]
        except Exception as e:
            logger.error(f"[TOOLS_MEMORY] Error getting execution history: {e}")
            return []
        finally:
            conn.close()

    def get_tool_analytics(self, tool_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Computes aggregate metrics for a single tool or all registered tools.
        """
        conn = self._get_connection()
        try:
            with conn.cursor(cursor_factory=RealDictCursor) as cur:
                if tool_id:
                    cur.execute("""
                        SELECT tool_id, tool_name, category, risk_level, total_executions,
                               successful_executions, failed_executions, last_executed_at,
                               CASE WHEN total_executions > 0 
                                    THEN ROUND((successful_executions::numeric / total_executions::numeric) * 100, 2)
                                    ELSE 100.0 END as success_rate_percent
                        FROM jarvis_tools_registry
                        WHERE tool_id = %s;
                    """, (tool_id.lower().strip(),))
                    row = cur.fetchone()
                    return dict(row) if row else {}
                else:
                    cur.execute("""
                        SELECT 
                            COUNT(*) as total_tools_registered,
                            SUM(total_executions) as total_executions_all,
                            SUM(successful_executions) as total_successful_all,
                            SUM(failed_executions) as total_failed_all,
                            CASE WHEN SUM(total_executions) > 0 
                                 THEN ROUND((SUM(successful_executions)::numeric / SUM(total_executions)::numeric) * 100, 2)
                                 ELSE 100.0 END as overall_success_rate_percent
                        FROM jarvis_tools_registry;
                    """)
                    row = cur.fetchone()
                    return dict(row) if row else {}
        except Exception as e:
            logger.error(f"[TOOLS_MEMORY] Error getting tool analytics: {e}")
            return {}
        finally:
            conn.close()
