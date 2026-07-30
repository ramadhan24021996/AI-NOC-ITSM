"""
Enterprise Model Registry Module for AIOps Output Adapter & LLM Router.

Provides centralized vendor-decoupled Model Lifecycle Management across providers:
Google (Gemini), DeepSeek, Groq, Anthropic (Claude), OpenAI, and Rule Engine.
"""

import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Any, List, Optional


class ModelDeploymentStatus(str, Enum):
    EXPERIMENTAL = "EXPERIMENTAL"
    CANARY = "CANARY"
    PRODUCTION = "PRODUCTION"
    DEPRECATED = "DEPRECATED"


@dataclass
class ModelMetadata:
    model_id: str
    provider: str
    version: str
    temperature: float = 0.3
    top_p: float = 0.9
    max_tokens: int = 1024
    evaluation_score: float = 85.0
    deployment_status: ModelDeploymentStatus = ModelDeploymentStatus.PRODUCTION
    rollback_target: str = "offline-rule-engine"
    created_at: str = "2026-07-21"
    author: str = "AIOps Architecture Board"


class ModelRegistry:
    """Centralized Registry for LLM Model Configurations and Hyperparameters."""

    MODELS: Dict[str, ModelMetadata] = {
        "gemini-1.5-flash": ModelMetadata(
            model_id="gemini-1.5-flash",
            provider="google",
            version="1.5.0",
            temperature=0.3,
            top_p=0.9,
            max_tokens=1024,
            evaluation_score=88.5,
            deployment_status=ModelDeploymentStatus.PRODUCTION,
            rollback_target="offline-rule-engine"
        ),
        "deepseek-chat": ModelMetadata(
            model_id="deepseek-chat",
            provider="deepseek",
            version="v3.0",
            temperature=0.2,
            top_p=0.95,
            max_tokens=1024,
            evaluation_score=91.2,
            deployment_status=ModelDeploymentStatus.CANARY,
            rollback_target="gemini-1.5-flash"
        ),
        "groq-llama-3": ModelMetadata(
            model_id="groq-llama-3",
            provider="groq",
            version="70b-v1",
            temperature=0.1,
            top_p=0.9,
            max_tokens=1024,
            evaluation_score=87.0,
            deployment_status=ModelDeploymentStatus.PRODUCTION,
            rollback_target="offline-rule-engine"
        ),
        "claude-3-5-sonnet": ModelMetadata(
            model_id="claude-3-5-sonnet",
            provider="anthropic",
            version="20241022",
            temperature=0.2,
            top_p=0.9,
            max_tokens=1024,
            evaluation_score=93.5,
            deployment_status=ModelDeploymentStatus.EXPERIMENTAL,
            rollback_target="gemini-1.5-flash"
        ),
        "offline-rule-engine": ModelMetadata(
            model_id="offline-rule-engine",
            provider="local",
            version="1.0.0",
            temperature=0.0,
            top_p=0.0,
            max_tokens=512,
            evaluation_score=75.0,
            deployment_status=ModelDeploymentStatus.PRODUCTION,
            rollback_target="offline-rule-engine"
        )
    }

    @classmethod
    def get_model(cls, model_id: str = "gemini-1.5-flash") -> ModelMetadata:
        """Retrieves model configuration metadata by model_id."""
        return cls.MODELS.get(model_id, cls.MODELS["gemini-1.5-flash"])

    @classmethod
    def register_model(cls, metadata: ModelMetadata):
        """Registers a new model version into the registry."""
        cls.MODELS[metadata.model_id] = metadata

    @classmethod
    def get_production_models(cls) -> List[ModelMetadata]:
        """Returns all models currently marked as PRODUCTION."""
        return [m for m in cls.MODELS.values() if m.deployment_status == ModelDeploymentStatus.PRODUCTION]
