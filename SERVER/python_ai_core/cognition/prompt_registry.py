"""
Prompt Registry & Versioning Engine (L4_PromptRegistry) - Centralized LLM Prompt Registry for AI Ops
Provides zero-downtime prompt management, versioning (v1.0, v1.1), A/B testing variations, and instant rollbacks.
"""

import logging
import time
import json
from typing import Dict, List, Any, Optional

logger = logging.getLogger("PROMPT_REGISTRY")

class PromptRegistryEngine:
    def __init__(self):
        self._prompts: Dict[str, Dict[str, Any]] = {}
        self._seed_default_prompts()
        logger.info("[PROMPT_REGISTRY] Prompt Registry & Versioning Engine initialized.")

    def _seed_default_prompts(self):
        default_prompts = [
            {
                "prompt_id": "prompt_intent_classifier",
                "version": "v2.1",
                "description": "System prompt for LLM Router to classify telemetry intent.",
                "template": "You are an AI Ops Intent Classifier. Analyze the telemetry payload: {telemetry_json}. Classify into: INCIDENT_TRIAGE, CHAOS_EXPERIMENT, or ROUTINE_LOG.",
                "active": True
            },
            {
                "prompt_id": "prompt_causal_dag_root_cause",
                "version": "v1.4",
                "description": "System prompt for Causal DAG engine to identify root cause.",
                "template": "Analyze graph nodes: {nodes}. Identify root cause for anomaly: {anomaly_description}. Output strictly JSON with confidence score.",
                "active": True
            },
            {
                "prompt_id": "prompt_ai_planner_action",
                "version": "v3.0",
                "description": "System prompt for AI Planner to generate Plan A, B, C.",
                "template": "Formulate 3 remediation plans (Plan A, Plan B, Plan C) for incident {incident_id}. Consider Blast Radius: {blast_radius}.",
                "active": True
            },
            {
                "prompt_id": "prompt_ai_reflector_postmortem",
                "version": "v2.0",
                "description": "System prompt for AI Reflector 3-stage evidence-driven postmortem.",
                "template": "Perform 3-stage postmortem for execution {execution_id}. Extract new SOP recommendations and save to Cognitive Memory DB.",
                "active": True
            }
        ]
        for p in default_prompts:
            self.register_prompt(
                prompt_id=str(p["prompt_id"]),
                version=str(p["version"]),
                template=str(p["template"]),
                description=str(p["description"]),
                active=bool(p["active"])
            )

    def register_prompt(
        self,
        prompt_id: str,
        version: str,
        template: str,
        description: str = "",
        active: bool = True
    ) -> Dict[str, Any]:
        """Registers or updates a prompt version in the registry."""
        timestamp = time.strftime("%Y-%m-%dT%H:%M:%SZ")
        if prompt_id not in self._prompts:
            self._prompts[prompt_id] = {
                "active_version": version,
                "versions": {}
            }

        self._prompts[prompt_id]["versions"][version] = {
            "version": version,
            "template": template,
            "description": description,
            "registered_at": timestamp,
            "active": active
        }
        if active:
            self._prompts[prompt_id]["active_version"] = version

        logger.info(f"[PROMPT_REGISTRY] Prompt '{prompt_id}' version '{version}' registered successfully.")
        return {
            "prompt_id": prompt_id,
            "active_version": version,
            "status": "REGISTERED_SUCCESSFUL"
        }

    def get_prompt(self, prompt_id: str, version: Optional[str] = None) -> Dict[str, Any]:
        """Retrieves active prompt template or specific version for zero-downtime execution."""
        if prompt_id not in self._prompts:
            logger.warning(f"[PROMPT_REGISTRY] Prompt '{prompt_id}' not found. Returning fallback default.")
            return {
                "prompt_id": prompt_id,
                "version": "v1.0-fallback",
                "template": "Default AI Ops System Prompt: {input}",
                "status": "FALLBACK"
            }

        target_version = version or self._prompts[prompt_id]["active_version"]
        prompt_data = self._prompts[prompt_id]["versions"].get(target_version)

        if not prompt_data:
            logger.warning(f"[PROMPT_REGISTRY] Version '{target_version}' for prompt '{prompt_id}' not found.")
            return {
                "prompt_id": prompt_id,
                "version": "v1.0-fallback",
                "template": "Default AI Ops System Prompt: {input}",
                "status": "FALLBACK"
            }

        return {
            "prompt_id": prompt_id,
            "version": target_version,
            "template": prompt_data["template"],
            "description": prompt_data["description"],
            "status": "ACTIVE_VERSION_LOADED"
        }

    def rollback_prompt_version(self, prompt_id: str, target_version: str) -> Dict[str, Any]:
        """Instantly rolls back active prompt version without restarting server."""
        if prompt_id in self._prompts and target_version in self._prompts[prompt_id]["versions"]:
            self._prompts[prompt_id]["active_version"] = target_version
            logger.info(f"[PROMPT_REGISTRY] Prompt '{prompt_id}' active version rolled back to '{target_version}'.")
            return {
                "prompt_id": prompt_id,
                "new_active_version": target_version,
                "status": "ROLLBACK_SUCCESSFUL"
            }
        return {"status": "FAILED", "reason": "Prompt or version not found"}

    def render_dynamic_prompt(self, prompt_id: str, context: Dict[str, Any], version: Optional[str] = None) -> str:
        """
        AdaptPrompt Framework Dynamic Contextualization:
        Dynamically injects {current_hour}, {severity_level}, {device_history}, {business_impact}
        and enforces conditional prompt instructions based on severity (P0 speed vs P3 safety).
        """
        prompt_info = self.get_prompt(prompt_id, version)
        template = prompt_info.get("template", "AI Ops Task: {input}")

        severity = str(context.get("severity_level", context.get("severity", "MEDIUM"))).upper()
        current_hour = context.get("current_hour", time.localtime().tm_hour)
        device_name = context.get("pc_name", context.get("device_name", "UNKNOWN_HOST"))
        device_history = context.get("device_history", "No recent incidents recorded.")
        business_impact = context.get("business_impact", "Standard Retail Operations")

        # Conditional instructions based on severity & time of day
        conditional_instructions = []
        if severity in ["P0", "CRITICAL", "HIGH"]:
            conditional_instructions.append("PRIORITAKAN KECEPATAN PEMULIHAN (<30s). Abaikan investigasi sekunder.")
        else:
            conditional_instructions.append("PRIORITAKAN KEAMANAN & VERIFIKASI GANDA. Sertakan analisis mendalam.")

        if 10 <= current_hour <= 21:
            conditional_instructions.append("PERINGATAN: Jam Sibuk Ritel (10:00-21:00 WIB). Lakukan remedi minim gangguan.")

        # Build dynamic prompt block
        dynamic_block = f"""
[CONTEXTUAL ADAPTIVE PARAMETERS]
- Current Local Hour: {current_hour}:00 WIB
- Incident Severity: {severity}
- Target Device: {device_name}
- Business Impact: {business_impact}
- Device History (Context Carry-Forward): {device_history}
- Adaptive Execution Strategy: {' | '.join(conditional_instructions)}
"""
        rendered_prompt = f"{template}\n{dynamic_block}"
        return rendered_prompt

# Global instance
prompt_registry_engine = PromptRegistryEngine()
