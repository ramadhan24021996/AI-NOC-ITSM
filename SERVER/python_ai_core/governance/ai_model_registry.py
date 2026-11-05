"""
Enterprise AI Model Registry
Tracks versions, rollbacks, and active deployments of LLM models, Cross-Encoders, Rerankers, and Embedding models.
"""

import logging
import time
from typing import Dict, Any, Optional

logger = logging.getLogger("AI_MODEL_REGISTRY")

class AIModelRegistry:
    """
    Enterprise AI Model Registry
    Audits deployed model versions, metadata, and handles version rollbacks.
    """

    def __init__(self):
        self.registry: Dict[str, Dict[str, Any]] = {
            "embedding_model": {"version": "v1.4.0", "name": "text-embedding-004", "status": "ACTIVE"},
            "reranker_model": {"version": "v2.1.0", "name": "ms-marco-MiniLM-L-6-v2", "status": "ACTIVE"},
            "llm_model": {"version": "v3.6.0", "name": "Gemini 3.6 Flash", "status": "ACTIVE"}
        }

    def register_model_version(self, model_type: str, name: str, version: str) -> bool:
        """Registers new model version into registry."""
        self.registry[model_type] = {
            "version": version,
            "name": name,
            "status": "ACTIVE",
            "registered_at": time.strftime("%Y-%m-%dT%H:%M:%SZ")
        }
        logger.info("[MODEL REGISTRY] Registered new model %s version %s", name, version)
        return True

    def get_active_model(self, model_type: str) -> Dict[str, Any]:
        """Returns active model details for model_type."""
        return self.registry.get(model_type, {"version": "v1.0.0", "name": "default", "status": "UNKNOWN"})
