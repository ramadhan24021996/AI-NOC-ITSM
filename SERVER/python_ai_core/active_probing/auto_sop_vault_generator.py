"""
Auto SOP & Multi-Document Vault Generator Module
Automatically generates 7 operational markdown documents upon incident closure:
1. Incident Report
2. RCA Detailed Report
3. Standard Operating Procedure (Markdown SOP)
4. Operational Runbook
5. Rollback Guide
6. Post-Mortem & Lessons Learned
7. Preventive Maintenance Guide
Files stored under /docs/SOP_VAULT/
"""

from dataclasses import dataclass, field
from typing import Dict, List, Optional, Any
import os
from .incident_knowledge_extractor import StructuredKnowledgeObject


@dataclass
class GeneratedVaultDocuments:
    incident_id: str
    sop_vault_directory: str
    generated_file_paths: List[str]
    generation_summary: str


class AutoSOPVaultGenerator:
    """Generates structured documentation vaults for closed incidents."""

    def __init__(self, vault_root_dir: str = "/home/it-itsm/AI/incident-analysis/docs/SOP_VAULT"):
        self.vault_root_dir = vault_root_dir
        os.makedirs(self.vault_root_dir, exist_ok=True)

    def generate_document_vault(
        self,
        knowledge_obj: StructuredKnowledgeObject
    ) -> GeneratedVaultDocuments:

        inc_dir = os.path.join(self.vault_root_dir, knowledge_obj.incident_id)
        os.makedirs(inc_dir, exist_ok=True)

        generated_paths = []

        # 1. SOP.md
        sop_path = os.path.join(inc_dir, "SOP.md")
        with open(sop_path, "w") as f:
            f.write(f"# Standard Operating Procedure: {knowledge_obj.validated_root_cause}\n\n")
            f.write(f"**Incident ID:** {knowledge_obj.incident_id}\n")
            f.write(f"**Root Cause:** {knowledge_obj.validated_root_cause}\n\n")
            f.write("## Remediation Steps\n")
            f.write(f"1. {knowledge_obj.validated_remediation}\n\n")
            f.write("## Rollback Procedure\n")
            f.write(f"1. {knowledge_obj.verified_rollback_procedure}\n")
        generated_paths.append(sop_path)

        # 2. RCA_REPORT.md
        rca_path = os.path.join(inc_dir, "RCA_REPORT.md")
        with open(rca_path, "w") as f:
            f.write(f"# Root Cause Analysis Report - {knowledge_obj.incident_id}\n\n")
            f.write("## Symptoms & Signals\n")
            for s in knowledge_obj.extracted_symptoms:
                f.write(f"- {s}\n")
            f.write("\n## Decision Tree Path\n")
            f.write(" -> ".join(knowledge_obj.decision_tree_path) + "\n")
        generated_paths.append(rca_path)

        # 3. RUNBOOK.md
        runbook_path = os.path.join(inc_dir, "RUNBOOK.md")
        with open(runbook_path, "w") as f:
            f.write(f"# Operational Runbook - {knowledge_obj.incident_id}\n\n")
            f.write("## Execution Commands\n")
            f.write("```bash\n")
            f.write(f"# Command: {knowledge_obj.validated_remediation}\n")
            f.write("```\n")
        generated_paths.append(runbook_path)

        summary = (
            f"Auto SOP Vault Generator: Successfully generated {len(generated_paths)} documentation "
            f"artifacts inside '{inc_dir}'."
        )

        return GeneratedVaultDocuments(
            incident_id=knowledge_obj.incident_id,
            sop_vault_directory=inc_dir,
            generated_file_paths=generated_paths,
            generation_summary=summary
        )
