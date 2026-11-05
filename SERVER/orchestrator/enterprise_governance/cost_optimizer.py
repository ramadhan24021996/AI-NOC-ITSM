"""
SERVER.orchestrator.enterprise_governance.cost_optimizer
=========================================================
Component: Cost Optimizer Router

Routes operational tasks to cost-effective LLM models by task complexity:
  Greeting -> Small Local Model
  RAG Chunk Parsing -> Gemini 1.5 Flash
  Reasoning / RCA -> Gemini 1.5 Pro
  Peer Review -> DeepSeek V3
  Consensus -> Grok 2
"""
import logging
from typing import Dict, Any

logger = logging.getLogger("orchestrator.governance.cost")


class CostOptimizerRouter:
    """
    Selects optimal LLM model tier based on task type to minimize API cost.
    """

    def select_model_for_task(self, task_type: str) -> str:
        t = task_type.lower()
        if "greeting" in t or "simple" in t:
            model = "Small-Local-Model-1B"
        elif "rag" in t or "parsing" in t:
            model = "Gemini-1.5-Flash"
        elif "peer" in t or "review" in t:
            model = "DeepSeek-V3"
        elif "consensus" in t:
            model = "Grok-2"
        else:
            model = "Gemini-1.5-Pro"

        logger.debug(f"[CostOptimizerRouter] Routed task '{task_type}' to model {model}")
        return model
