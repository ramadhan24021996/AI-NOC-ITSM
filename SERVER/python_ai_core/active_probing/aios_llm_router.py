"""
Policy-Aware Multi-LLM Router Module
Decouples Agent logic from LLM models and routes requests based on Policy + Data Sensitivity:
- Sensitive Config / Internal RCA -> Local Model Only (Ollama / Local DeepSeek)
- General SOP Generation / Documentation -> Cloud Allowed (Gemini / Claude)
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Any


@dataclass
class LLMRoutingDecision:
    task_type: str
    data_sensitivity: str  # "HIGH_SENSITIVE_LOCAL_ONLY", "MEDIUM_CONFIDENTIAL", "LOW_PUBLIC"
    selected_model_backend: str
    model_provider: str
    policy_enforced_reason: str


class AIOSLLMRouter:
    """Policy-aware router mapping LLM tasks to appropriate local or cloud inference backends."""

    def route_llm_request(
        self,
        task_type: str,
        contains_sensitive_credentials: bool = False
    ) -> LLMRoutingDecision:

        if contains_sensitive_credentials or "internal_rca" in task_type.lower() or "secret" in task_type.lower():
            return LLMRoutingDecision(
                task_type=task_type,
                data_sensitivity="HIGH_SENSITIVE_LOCAL_ONLY",
                selected_model_backend="deepseek-r1-local-7b",
                model_provider="Ollama_Local_Inference",
                policy_enforced_reason="Data Sensitivity Policy: Credentials/Internal RCA restricted to local Ollama inference"
            )

        if "sop" in task_type.lower() or "documentation" in task_type.lower():
            return LLMRoutingDecision(
                task_type=task_type,
                data_sensitivity="LOW_PUBLIC",
                selected_model_backend="gemini-1.5-flash",
                model_provider="Google_Cloud_Vertex_AI",
                policy_enforced_reason="Cloud Allowed: High-performance cloud LLM authorized for SOP generation"
            )

        return LLMRoutingDecision(
            task_type=task_type,
            data_sensitivity="MEDIUM_CONFIDENTIAL",
            selected_model_backend="gemini-1.5-flash",
            model_provider="Google_Cloud_Vertex_AI",
            policy_enforced_reason="Standard Routing: Gemini 1.5 Flash selected"
        )
