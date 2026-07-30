#!/usr/bin/env python3
"""
n8n Workflow GitOps Sync Tool (Gap 8 / L6)
Exports all active n8n workflows from Docker volume / REST API into JSON files for Git version control.
"""

import os
import sys
import json
import logging
import urllib.request
import urllib.error

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("N8N_GITOPS_SYNC")

N8N_HOST = os.environ.get("N8N_HOST", "localhost")
N8N_PORT = os.environ.get("N8N_PORT", "5678")
N8N_API_KEY = os.environ.get("N8N_API_KEY", "")
OUTPUT_DIR = os.environ.get("GITOPS_OUTPUT_DIR", "n8n_docker/workflows_gitops")

def export_n8n_workflows():
    logger.info(f"Starting n8n GitOps sync to '{OUTPUT_DIR}'...")
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    if not N8N_API_KEY:
        logger.warning("N8N_API_KEY is not set. Saving placeholder sample workflow definition...")
        sample_wf = {
            "name": "Sample Enterprise Incident Orchestrator v3.0",
            "nodes": [
                {"parameters": {}, "name": "Start", "type": "n8n-nodes-base.start", "typeVersion": 1}
            ],
            "connections": {},
            "active": True,
            "settings": {},
            "versionId": "1"
        }
        out_file = os.path.join(OUTPUT_DIR, "sample_orchestrator_v3.json")
        with open(out_file, "w") as f:
            json.dump(sample_wf, f, indent=2)
        logger.info(f"Saved sample workflow to {out_file}")
        return

    url = f"http://{N8N_HOST}:{N8N_PORT}/api/v1/workflows"
    req = urllib.request.Request(url, headers={"X-N8N-API-KEY": N8N_API_KEY})

    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            workflows = data.get("data", [])
            for wf in workflows:
                wf_id = wf.get("id", "wf")
                wf_name = wf.get("name", "unnamed").replace(" ", "_").lower()
                file_path = os.path.join(OUTPUT_DIR, f"{wf_id}_{wf_name}.json")
                with open(file_path, "w") as f:
                    json.dump(wf, f, indent=2)
                logger.info(f"Exported workflow '{wf.get('name')}' -> {file_path}")
            logger.info(f"Successfully exported {len(workflows)} n8n workflows for GitOps tracking.")
    except urllib.error.URLError as e:
        logger.error(f"Failed to connect to n8n API ({url}): {e}")

if __name__ == "__main__":
    export_n8n_workflows()
