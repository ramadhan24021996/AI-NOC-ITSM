"""
Post-Mortem Vault Exporter Engine.
Formats incident resolution summaries into valid Obsidian Markdown documents (.md)
with YAML Frontmatter and bi-directional backlinks to SOPs and Infrastructure Topologies.
"""

import os
import logging
import time
from pathlib import Path
from typing import Dict, Any, Optional, List

logger = logging.getLogger("PostMortemVaultExporter")


class PostMortemVaultExporter:
    """
    Exports incident post-mortems and root cause analyses to Obsidian Vault.
    Guarantees production-ready file writing with safe directory creation.
    """

    def __init__(self, vault_dir: Optional[str] = None):
        self.vault_dir = vault_dir or os.getenv("OBSIDIAN_VAULT_DIR", "/home/it-itsm/AI/incident-analysis/DOCUMENTATION/obsidian_vault")
        self.incidents_dir = os.path.join(self.vault_dir, "incidents")
        os.makedirs(self.incidents_dir, exist_ok=True)

    def export_postmortem_to_vault(
        self,
        incident_id: str,
        title: str,
        root_cause: str,
        bound_sop_id: Optional[str] = None,
        severity: str = "HIGH",
        affected_service: str = "core-service",
        tags: Optional[List[str]] = None,
        backlinks: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Formats and persists an incident post-mortem into Obsidian Vault.
        """
        date_str = time.strftime("%Y-%m-%d")
        safe_inc_id = incident_id.replace("/", "_").replace("\\", "_")
        filename = f"{safe_inc_id}.md"
        file_path = os.path.join(self.incidents_dir, filename)

        tag_list = tags or ["incident", "postmortem", affected_service]
        link_list = backlinks or []
        if bound_sop_id and bound_sop_id not in link_list:
            link_list.append(bound_sop_id)

        # Build YAML Frontmatter
        frontmatter = f"""---
incident_id: {safe_inc_id}
title: "{title}"
severity: {severity}
affected_service: {affected_service}
date: {date_str}
tags:
"""
        for t in tag_list:
            frontmatter += f"  - {t}\n"
        frontmatter += "---\n\n"

        # Build Markdown Body with Backlinks
        body = f"# Incident Report: {title}\n\n"
        body += f"**Incident ID:** `{safe_inc_id}`  \n"
        body += f"**Severity:** `{severity}`  \n"
        body += f"**Affected Service:** `{affected_service}`  \n"
        body += f"**Date:** {date_str}  \n\n"

        body += "## Root Cause Analysis\n"
        body += f"{root_cause}\n\n"

        body += "## Remediation & Related SOPs\n"
        if bound_sop_id:
            body += f"Executed bound pre-approved SOP: [[{bound_sop_id}]]\n\n"

        if link_list:
            body += "## Associated Topologies & Documents\n"
            for link in link_list:
                body += f"- [[{link}]]\n"
            body += "\n"

        full_content = frontmatter + body

        try:
            with open(file_path, "w", encoding="utf-8") as f:
                f.write(full_content)
            logger.info("[POSTMORTEM EXPORTER] Successfully exported Post-Mortem '%s' to '%s'", safe_inc_id, file_path)
            return {
                "status": "SUCCESS",
                "incident_id": safe_inc_id,
                "file_path": file_path,
                "file_name": filename,
                "backlinks": link_list,
                "timestamp": time.time()
            }
        except Exception as e:
            logger.error("[POSTMORTEM EXPORTER] Failed to write post-mortem file '%s': %s", file_path, e)
            return {
                "status": "FAILED",
                "reason": str(e)
            }


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    exporter = PostMortemVaultExporter()
    res = exporter.export_postmortem_to_vault(
        incident_id="INC-2026-TEST01",
        title="NATS Message Broker Packet Loss",
        root_cause="High consumer lag caused by network socket buffer overflow.",
        bound_sop_id="SOP_003",
        affected_service="nats-cluster"
    )
    print("Export Result:", res)
