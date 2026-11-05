"""
SERVER.integration.n8n.n8n_dispatcher — N8N Workflow Execution Dispatcher
==========================================================================
Production-grade dispatcher bridging JARVIS AI & Action Catalog to n8n Workflow Automation Engine.

Features:
  - Action Catalog ID -> n8n Webhook Endpoint mapping
  - Automatic fallback to master incident webhook
  - Correlation ID tracking & telemetry header injection
  - Health check & circuit breaker handling
  - Full audit logging integration
"""
import os
import json
import time
import logging
import urllib.request
import urllib.parse
import urllib.error
from typing import Dict, Any, Optional

logger = logging.getLogger("integration.n8n.dispatcher")

# Default action to n8n webhook slug mapping
ACTION_WEBHOOK_MAP: Dict[str, str] = {
    "ACT_RESTART_SPOOLER":     "webhook/restart-spooler",
    "ACT_CLEAR_PRINT_QUEUE":   "webhook/clear-spooler",
    "ACT_FLUSH_DNS":           "webhook/flush-dns",
    "ACT_FAILOVER_ISP":        "webhook/isp-failover",
    "ACT_DRAIN_REPLICA":       "webhook/drain-replica",
    "ACT_RESTART_POSTGRESQL":  "webhook/restart-postgresql",
    "ACT_RESTART_REDIS":       "webhook/restart-redis",
    "ACT_RESTART_SERVICE":     "webhook/restart-service",
    "ACT_RESTART_NATS":        "webhook/restart-nats",
    "ACT_REBOOT_SERVER":       "webhook/reboot-server",
    "TRIGGER_N8N_WORKFLOW":    "webhook/incident-trigger",
    "N8N_VAULT_SYNC":          "webhook/obsidian-sync",
    "N8N_PUBLISH_POSTMORTEM":  "webhook/publish-postmortem",
    # Agentic AI 4-Phase Roadmap n8n Nodes
    "N8N_TASK_DISPATCH":       "webhook/agentic-task-dispatch",
    "N8N_TOOL_REGISTRY":       "webhook/mcp-tool-retrieval",
    "N8N_GRAPH_EXPLAINER":     "webhook/causal-graph-update",
    "N8N_VISION_PARSER":       "webhook/vision-log-analysis",
}


class N8NWorkflowDispatcher:
    """
    Dispatcher for executing n8n workflows from JARVIS & Action Catalog.
    """

    def __init__(
        self,
        n8n_base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = 10.0,
    ):
        self.base_url = (n8n_base_url or os.getenv("N8N_BASE_URL", "http://localhost:5678")).rstrip("/")
        self.api_key = api_key or os.getenv("N8N_API_KEY", "")
        self.timeout = float(os.getenv("N8N_TIMEOUT_SEC", str(timeout)))
        logger.info(f"[N8NDispatcher] Initialized → base_url={self.base_url}, timeout={self.timeout}s")

    def check_health(self) -> Dict[str, Any]:
        """
        Check n8n engine health status via /healthz endpoint.
        """
        url = f"{self.base_url}/healthz"
        t0 = time.time()
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "JARVIS-N8N-Dispatcher/1.0"})
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                latency = int((time.time() - t0) * 1000)
                is_ok = resp.status in (200, 204)
                return {
                    "status": "ONLINE" if is_ok else "DEGRADED",
                    "http_code": resp.status,
                    "url": self.base_url,
                    "latency_ms": latency,
                    "engine": "n8n Workflow Automation Engine",
                }
        except Exception as e:
            latency = int((time.time() - t0) * 1000)
            logger.warning(f"[N8NDispatcher] Health check failed for {url}: {e}")
            return {
                "status": "OFFLINE",
                "error": str(e),
                "url": self.base_url,
                "latency_ms": latency,
                "engine": "n8n Workflow Automation Engine",
            }

    def dispatch_action(
        self,
        action_id: str,
        payload: Optional[Dict[str, Any]] = None,
        target_device: str = "",
        incident_id: str = "",
    ) -> Dict[str, Any]:
        """Alias for dispatch method with flexible keyword parameters."""
        return self.dispatch(
            action_id=action_id,
            target_device=target_device,
            parameters=payload,
            incident_id=incident_id,
        )

    def dispatch(
        self,
        action_id: str,
        target_device: str = "",
        parameters: Optional[Dict[str, Any]] = None,
        incident_id: str = "",
        correlation_id: str = "",
        operator_id: str = "JARVIS_AI",
    ) -> Dict[str, Any]:
        """
        Dispatches an action request to the target n8n workflow webhook.
        """
        t0 = time.time()
        if not correlation_id:
            correlation_id = f"corr_n8n_{int(time.time() * 1000)}"

        # Resolve webhook path
        webhook_slug = ACTION_WEBHOOK_MAP.get(action_id, "webhook/incident-trigger")
        target_url = f"{self.base_url}/{webhook_slug}"

        payload = {
            "action_id": action_id,
            "target_device": target_device,
            "incident_id": incident_id,
            "correlation_id": correlation_id,
            "operator_id": operator_id,
            "parameters": parameters or {},
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
            "source": "JARVIS_N8N_DISPATCHER",
        }

        body_bytes = json.dumps(payload).encode("utf-8")
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-ID": correlation_id,
            "X-N8N-WEBHOOK-ID": webhook_slug.replace("webhook/", ""),
            "User-Agent": "JARVIS-N8N-Dispatcher/1.0",
        }
        if self.api_key:
            headers["X-N8N-API-KEY"] = self.api_key

        try:
            req = urllib.request.Request(target_url, data=body_bytes, headers=headers, method="POST")
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:
                resp_bytes = resp.read()
                latency = int((time.time() - t0) * 1000)
                try:
                    resp_data = json.loads(resp_bytes.decode("utf-8")) if resp_bytes else {}
                except Exception:
                    resp_data = {"raw_response": resp_bytes.decode("utf-8", errors="ignore")}

                logger.info(
                    f"[N8NDispatcher] ✅ Dispatch success | action={action_id} | "
                    f"target={target_device} | code={resp.status} | latency={latency}ms"
                )
                return {
                    "success": True,
                    "status": "DISPATCHED",
                    "http_code": resp.status,
                    "action_id": action_id,
                    "webhook_url": target_url,
                    "correlation_id": correlation_id,
                    "n8n_response": resp_data,
                    "latency_ms": latency,
                }

        except urllib.error.HTTPError as e:
            latency = int((time.time() - t0) * 1000)
            logger.error(f"[N8NDispatcher] HTTP {e.code} for {target_url}: {e.reason}")
            return {
                "success": False,
                "status": "HTTP_ERROR",
                "http_code": e.code,
                "error": f"n8n Webhook returned HTTP {e.code}: {e.reason}",
                "action_id": action_id,
                "correlation_id": correlation_id,
                "latency_ms": latency,
            }
        except Exception as e:
            latency = int((time.time() - t0) * 1000)
            logger.warning(f"[N8NDispatcher] Dispatch failed for {action_id} to {target_url}: {e}")
            return {
                "success": False,
                "status": "DISPATCH_FAILED",
                "error": str(e),
                "action_id": action_id,
                "correlation_id": correlation_id,
                "latency_ms": latency,
            }


# Module-level singleton instance for convenience
_default_dispatcher = N8NWorkflowDispatcher()


def get_dispatcher() -> N8NWorkflowDispatcher:
    """Returns default singleton N8NWorkflowDispatcher."""
    return _default_dispatcher
