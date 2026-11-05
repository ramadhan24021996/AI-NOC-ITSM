"""
SERVER.python_ai_core.adapters.mcp_adapter — Model Context Protocol (MCP) Client Gateway
========================================================================================
Provides standardized Model Context Protocol (MCP) client connection layer for enterprise tools:
 - PostgreSQL MCP Server
 - Kubernetes MCP Server
 - Prometheus / Metrics MCP Server
 - Docker & N8N Workflow MCP Servers

Includes Anti-Context Rot Tool Selection to prevent prompt window overflow.
"""
import logging
import json
import re
import os
import subprocess
from datetime import datetime, timezone
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("adapters.mcp_adapter")


@dataclass
class MCPToolDefinition:
    """Definition of an MCP Tool exposed by an MCP Server."""
    server_name: str
    tool_name: str
    description: str
    input_schema: Dict[str, Any]
    tags: List[str] = field(default_factory=list)


@dataclass
class MCPExecutionResult:
    """Standard execution result returned from an MCP Tool."""
    server_name: str
    tool_name: str
    status: str       # "SUCCESS" | "FAILED" | "UNAUTHORIZED"
    output: Any
    error_message: Optional[str] = None


class MCPAdapterGateway:
    """Client Gateway for managing MCP Tool Registries & Executions."""

    def __init__(self):
        self._registered_tools: Dict[str, MCPToolDefinition] = {}
        self._register_default_mcp_servers()

    def _register_default_mcp_servers(self):
        """Registers default Enterprise MCP Server tools."""
        # 1. PostgreSQL MCP Server Tools
        self.register_tool(MCPToolDefinition(
            server_name="postgres_mcp",
            tool_name="query_db_schema",
            description="Inspects PostgreSQL database tables, columns, and indexes.",
            input_schema={"type": "object", "properties": {"table_name": {"type": "string"}}},
            tags=["database", "postgres", "schema", "sql"]
        ))
        
        # 2. Prometheus MCP Server Tools
        self.register_tool(MCPToolDefinition(
            server_name="prometheus_mcp",
            tool_name="get_metric_series",
            description="Queries real-time Prometheus time-series metric data for CPU, Memory, and Disk.",
            input_schema={"type": "object", "properties": {"query": {"type": "string"}}},
            tags=["metrics", "prometheus", "cpu", "memory", "telemetry"]
        ))

        # 3. Kubernetes MCP Server Tools
        self.register_tool(MCPToolDefinition(
            server_name="k8s_mcp",
            tool_name="get_pod_logs",
            description="Retrieves live container pod logs from Kubernetes clusters.",
            input_schema={"type": "object", "properties": {"pod_name": {"type": "string"}}},
            tags=["k8s", "kubernetes", "pod", "logs", "container"]
        ))

    def register_tool(self, tool: MCPToolDefinition) -> None:
        """Registers a new MCP Tool into the gateway."""
        key = f"{tool.server_name}::{tool.tool_name}"
        self._registered_tools[key] = tool
        logger.info(f"[MCPAdapterGateway] Registered MCP Tool '{key}' [{', '.join(tool.tags)}]")

    def select_relevant_tools(self, query: str, top_k: int = 2) -> List[MCPToolDefinition]:
        """
        Anti-Context Rot Tool Selector:
        Selects only the top_k most relevant MCP tools based on query intent & tag matching
        to prevent prompt context window inflation.

        Args:
            query: User or voice operator query text.
            top_k: Maximum number of tools to select.

        Returns:
            List of relevant MCPToolDefinition objects.
        """
        if not query or not self._registered_tools:
            return []

        query_clean = query.lower()
        scored_tools: List[Tuple[int, MCPToolDefinition]] = []

        for tool in self._registered_tools.values():
            score = 0
            # Tag match
            for tag in tool.tags:
                if tag in query_clean:
                    score += 3
            # Name & description match
            if tool.tool_name.lower() in query_clean or tool.server_name.lower() in query_clean:
                score += 5
            for word in re.findall(r"\w+", tool.description.lower()):
                if len(word) > 3 and word in query_clean:
                    score += 1

            if score > 0:
                scored_tools.append((score, tool))

        # Sort by score descending
        scored_tools.sort(key=lambda x: x[0], reverse=True)
        selected = [tool for _, tool in scored_tools[:top_k]]
        
        # If no tags matched, return lightweight default set
        if not selected and self._registered_tools:
            selected = list(self._registered_tools.values())[:top_k]

        logger.info(f"[MCPAdapterGateway] Anti-Context Rot selected {len(selected)} tools for query '{query[:30]}...'")
        self.sync_selected_tools_to_n8n(query, selected)
        return selected

    def sync_selected_tools_to_n8n(self, query: str, selected_tools: List[MCPToolDefinition]) -> Dict[str, Any]:
        """Dispatches selected MCP tool schemas to n8n Webhook Node (Phase 2)."""
        try:
            try:
                from SERVER.integration.n8n.n8n_dispatcher import get_dispatcher
            except ImportError:
                from integration.n8n.n8n_dispatcher import get_dispatcher
            dispatcher = get_dispatcher()
            tool_payloads = [
                {
                    "server_name": t.server_name,
                    "tool_name": t.tool_name,
                    "description": t.description,
                    "tags": t.tags,
                }
                for t in selected_tools
            ]
            return dispatcher.dispatch_action(
                action_id="N8N_TOOL_REGISTRY",
                payload={"query": query, "tools": tool_payloads, "count": len(selected_tools)},
                target_device="MCP_GATEWAY"
            )
        except Exception as e:
            logger.warning(f"[MCPAdapterGateway] n8n tool registry sync failed: {e}")
            return {"status": "FALLBACK_LOCAL", "error": str(e)}

    def execute_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> MCPExecutionResult:
        """
        Executes an MCP Tool call via subprocess JSON-RPC protocol.

        Spawns the target MCP server process, sends a `tools/call` JSON-RPC request,
        reads the response, and returns the real execution output.

        Args:
            server_name: Name of the target MCP server.
            tool_name: Tool function name.
            arguments: Dict of execution arguments.

        Returns:
            MCPExecutionResult with real execution output or structured error.
        """
        key = f"{server_name}::{tool_name}"
        tool = self._registered_tools.get(key)
        if not tool:
            return MCPExecutionResult(
                server_name=server_name,
                tool_name=tool_name,
                status="FAILED",
                output=None,
                error_message=f"MCP Tool '{key}' not registered in gateway."
            )

        logger.info(f"[MCPAdapterGateway] Executing MCP Tool '{key}' with args: {arguments}")

        # Resolve MCP server command based on server_name
        server_commands = {
            "postgres_mcp": ["npx", "-y", "@modelcontextprotocol/server-postgres"],
            "prometheus_mcp": ["npx", "-y", "@modelcontextprotocol/server-prometheus"],
            "k8s_mcp": ["npx", "-y", "@modelcontextprotocol/server-kubernetes"],
        }

        cmd = server_commands.get(server_name)
        if not cmd:
            return MCPExecutionResult(
                server_name=server_name,
                tool_name=tool_name,
                status="FAILED",
                output=None,
                error_message=f"No MCP server command configured for '{server_name}'."
            )

        # Build MCP JSON-RPC request
        jsonrpc_request = json.dumps({
            "jsonrpc": "2.0",
            "id": 1,
            "method": "tools/call",
            "params": {
                "name": tool_name,
                "arguments": arguments,
            }
        }) + "\n"

        try:
            env = os.environ.copy()
            # Pass through relevant connection env vars
            for env_key in ["DATABASE_URL", "PROMETHEUS_URL", "KUBECONFIG"]:
                if env_key in os.environ:
                    env[env_key] = os.environ[env_key]

            proc = subprocess.run(
                cmd,
                input=jsonrpc_request,
                capture_output=True,
                text=True,
                timeout=30,
                env=env,
            )

            if proc.returncode != 0:
                error_msg = proc.stderr.strip() if proc.stderr else f"Process exited with code {proc.returncode}"
                logger.error(f"[MCPAdapterGateway] MCP server '{server_name}' failed: {error_msg}")
                return MCPExecutionResult(
                    server_name=server_name,
                    tool_name=tool_name,
                    status="FAILED",
                    output=None,
                    error_message=f"MCP execution error: {error_msg[:500]}"
                )

            # Parse JSON-RPC response
            stdout = proc.stdout.strip()
            if stdout:
                # MCP servers may output multiple JSON lines; take the last valid one
                response_lines = [line for line in stdout.split("\n") if line.strip().startswith("{")]
                if response_lines:
                    response_data = json.loads(response_lines[-1])
                    result = response_data.get("result", response_data)
                    logger.info(
                        f"[MCPAdapterGateway] MCP Tool '{key}' executed successfully. "
                        f"Response size: {len(stdout)} bytes"
                    )
                    return MCPExecutionResult(
                        server_name=server_name,
                        tool_name=tool_name,
                        status="SUCCESS",
                        output=result,
                        error_message=None
                    )

            # No parseable output
            return MCPExecutionResult(
                server_name=server_name,
                tool_name=tool_name,
                status="SUCCESS",
                output={"raw_stdout": stdout, "executed_at": datetime.now(timezone.utc).isoformat()},
                error_message=None
            )

        except subprocess.TimeoutExpired:
            logger.error(f"[MCPAdapterGateway] MCP Tool '{key}' execution timed out (30s).")
            return MCPExecutionResult(
                server_name=server_name,
                tool_name=tool_name,
                status="FAILED",
                output=None,
                error_message="MCP execution timed out after 30 seconds."
            )
        except FileNotFoundError:
            logger.error(f"[MCPAdapterGateway] MCP server binary not found: {cmd[0]}. Install Node.js and npx.")
            return MCPExecutionResult(
                server_name=server_name,
                tool_name=tool_name,
                status="FAILED",
                output=None,
                error_message=f"MCP server binary '{cmd[0]}' not found. Ensure Node.js/npx is installed."
            )
        except Exception as e:
            logger.error(f"[MCPAdapterGateway] MCP Tool execution error: {e}")
            return MCPExecutionResult(
                server_name=server_name,
                tool_name=tool_name,
                status="FAILED",
                output=None,
                error_message=f"MCP execution exception: {str(e)[:500]}"
            )

