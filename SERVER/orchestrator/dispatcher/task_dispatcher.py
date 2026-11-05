"""
SERVER.orchestrator - Task Dispatcher
Dispatches planned execution steps to target engines.

Tahap 2.3 Extension:
  LLMDispatcher, RAGDispatcher, EmbeddingDispatcher, ProviderSelector
  are all available from this module.
"""
from abc import ABC, abstractmethod
from typing import Dict, Any

class TaskDispatcher(ABC):
    """Abstract task dispatcher interface."""
    @abstractmethod
    def dispatch(self, step_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        pass

# ── Tahap 2.3: LLM & Knowledge Router (Dispatcher Layer) ──────────────────────
# Re-exported here for convenient single-import access:
#   from SERVER.orchestrator.dispatcher.task_dispatcher import LLMDispatcher
from SERVER.orchestrator.dispatcher.llm_dispatcher import LLMDispatcher
from SERVER.orchestrator.dispatcher.rag_dispatcher import RAGDispatcher
from SERVER.orchestrator.dispatcher.embedding_dispatcher import EmbeddingDispatcher
from SERVER.orchestrator.dispatcher.provider_selector import ProviderSelector, ProviderTier

__all__ = [
    "TaskDispatcher",
    "LLMDispatcher",
    "RAGDispatcher",
    "EmbeddingDispatcher",
    "ProviderSelector",
    "ProviderTier",
]
