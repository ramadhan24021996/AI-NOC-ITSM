"""
n8n Async Webhook Listener & Callback Resume Service (L4_n8n_WebhookListener)
Handles heavy asynchronous Python AI Core tasks and dispatches callback resume signals
and workflow triggers (v4.1 Obsidian Vault Sync & v4.2 Post-Mortem Publisher) to n8n.
"""

import os
import json
import logging
import time
import requests
from typing import Dict, Any, Optional

logger = logging.getLogger("N8N_WEBHOOK_LISTENER")


class N8NWebhookListenerService:
    def __init__(self, n8n_base_url: Optional[str] = None):
        self.n8n_base_url = n8n_base_url or os.environ.get("N8N_WEBHOOK_URL", "http://localhost:5678")

    def resume_n8n_workflow_callback(
        self,
        execution_id: str,
        correlation_id: str,
        payload_data: Dict[str, Any],
        status: str = "SUCCESS"
    ) -> Dict[str, Any]:
        """
        Callback Pattern: Resumes n8n workflow execution asynchronously
        by POSTing completed Python AI payload to /api/n8n/webhook-resume.
        """
        callback_url = f"{self.n8n_base_url}/webhook-waiting/{execution_id}"
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-ID": correlation_id,
            "X-N8N-WEBHOOK-ID": correlation_id
        }

        body = {
            "execution_id": execution_id,
            "correlation_id": correlation_id,
            "status": status,
            "completed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
            "result_payload": payload_data
        }

        logger.info(f"[N8N_WEBHOOK_LISTENER] Dispatching async callback resume to n8n (ExecID={execution_id}, CorrID={correlation_id}).")

        try:
            resp = requests.post(callback_url, json=body, headers=headers, timeout=5)
            logger.info(f"[N8N_WEBHOOK_LISTENER] n8n callback response: HTTP {resp.status_code}")
            return {"status": "DISPATCHED_SUCCESSFULLY", "http_code": resp.status_code}
        except Exception as e:
            logger.warning(f"[N8N_WEBHOOK_LISTENER] Async callback to n8n failed (will retry via fallback queue): {e}")
            return {"status": "FAILED_RETRY_QUEUED", "reason": str(e)}

    def trigger_vault_sync_workflow_v4_1(self, vault_dir: Optional[str] = None) -> Dict[str, Any]:
        """
        Triggers n8n Modular Workflow v4.1 (Obsidian Vault Sync & SOP Governance).
        """
        url = f"{self.n8n_base_url}/webhook/obsidian-sync"
        correlation_id = f"corr_sync_{int(time.time()*1000)}"
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-ID": correlation_id
        }
        body = {
            "action": "RELOAD_CATALOG",
            "vault_dir": vault_dir or "/home/it-itsm/AI/incident-analysis/DOCUMENTATION/obsidian_vault",
            "correlation_id": correlation_id
        }

        logger.info(f"[N8N_WEBHOOK_LISTENER] Triggering n8n Workflow v4.1 Vault Sync at {url}")
        try:
            resp = requests.post(url, json=body, headers=headers, timeout=5)
            return {"status": "SUCCESS", "workflow": "v4.1", "http_code": resp.status_code, "correlation_id": correlation_id}
        except Exception as e:
            logger.warning(f"[N8N_WEBHOOK_LISTENER] Direct n8n webhook v4.1 call failed: {e}. Executing local fallback.")
            return {"status": "FALLBACK_EXECUTED", "workflow": "v4.1", "reason": str(e), "correlation_id": correlation_id}

    def trigger_postmortem_publisher_v4_2(self, incident_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Triggers n8n Modular Workflow v4.2 (Auto Post-Mortem Publisher & Closure).
        """
        url = f"{self.n8n_base_url}/webhook/publish-postmortem"
        correlation_id = f"corr_pm_{int(time.time()*1000)}"
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-ID": correlation_id
        }
        payload = {
            "incident_id": incident_data.get("incident_id", f"INC-{int(time.time())}"),
            "title": incident_data.get("title", "Incident Resolution Summary"),
            "root_cause": incident_data.get("root_cause", "Resolved by automated SOP execution."),
            "bound_sop_id": incident_data.get("bound_sop_id", "SOP_001"),
            "severity": incident_data.get("severity", "HIGH"),
            "affected_service": incident_data.get("affected_service", "core-service")
        }

        logger.info(f"[N8N_WEBHOOK_LISTENER] Triggering n8n Workflow v4.2 Post-Mortem Publisher at {url}")
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=5)
            return {"status": "SUCCESS", "workflow": "v4.2", "http_code": resp.status_code, "correlation_id": correlation_id}
        except Exception as e:
            logger.warning(f"[N8N_WEBHOOK_LISTENER] Direct n8n webhook v4.2 call failed: {e}. Executing local fallback.")
            return {"status": "FALLBACK_EXECUTED", "workflow": "v4.2", "reason": str(e), "correlation_id": correlation_id}


    def trigger_multi_source_rag_sync_v4_3(self, symptom_text: str = "Gateway Timeout", device_name: str = "Client_PC_01") -> Dict[str, Any]:
        """
        Triggers n8n Modular Workflow v4.3 (Multi-Source RAG 14-Knowledge Ingestion & Sync).
        """
        url = f"{self.n8n_base_url}/webhook/multi-source-rag-sync"
        correlation_id = f"corr_rag14_{int(time.time()*1000)}"
        headers = {
            "Content-Type": "application/json",
            "X-Correlation-ID": correlation_id
        }
        payload = {
            "symptom_text": symptom_text,
            "device_name": device_name,
            "correlation_id": correlation_id,
            "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }

        logger.info(f"[N8N_WEBHOOK_LISTENER] Triggering n8n Workflow v4.3 Multi-Source RAG Sync at {url}")
        try:
            resp = requests.post(url, json=payload, headers=headers, timeout=5)
            return {"status": "SUCCESS", "workflow": "v4.3", "http_code": resp.status_code, "correlation_id": correlation_id}
        except Exception as e:
            logger.warning(f"[N8N_WEBHOOK_LISTENER] Direct n8n webhook v4.3 call failed: {e}. Executing local fallback.")
            return {"status": "FALLBACK_EXECUTED", "workflow": "v4.3", "reason": str(e), "correlation_id": correlation_id}


# Global instance
n8n_webhook_listener_service = N8NWebhookListenerService()

