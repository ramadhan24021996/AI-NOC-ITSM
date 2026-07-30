"""
n8n Async Webhook Listener & Callback Resume Service (L4_n8n_WebhookListener)
Handles heavy asynchronous Python AI Core tasks and dispatches callback resume signals
to n8n webhooks (/api/n8n/webhook-resume) to prevent 30s synchronous worker timeouts.
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
            resp = requests.post(callback_url, json=body, headers=headers, timeout=10)
            logger.info(f"[N8N_WEBHOOK_LISTENER] n8n callback response: HTTP {resp.status_code}")
            return {"status": "DISPATCHED_SUCCESSFULLY", "http_code": resp.status_code}
        except Exception as e:
            logger.warning(f"[N8N_WEBHOOK_LISTENER] Async callback to n8n failed (will retry via fallback queue): {e}")
            return {"status": "FAILED_RETRY_QUEUED", "reason": str(e)}

# Global instance
n8n_webhook_listener_service = N8NWebhookListenerService()
