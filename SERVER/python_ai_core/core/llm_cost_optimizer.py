"""
Enterprise LLM Cost Optimizer
Implements Prompt Compression, Token Budgeting, Context Window Optimization, and Semantic Response Caching
to control inference costs and prevent context token inflation.
"""

import logging
import hashlib
from typing import Dict, Any, Optional

logger = logging.getLogger("LLM_COST_OPTIMIZER")

class LLMCostOptimizer:
    """
    Enterprise Cost Optimizer
    Compresses verbose prompts, enforces token budgets, and caches LLM response output.
    """

    def __init__(self, max_token_budget: int = 4096):
        self.max_token_budget = max_token_budget
        self.semantic_cache: Dict[str, Dict[str, Any]] = {}

    def compress_prompt_context(self, raw_prompt: str, target_max_chars: int = 8000) -> str:
        """
        Compresses repetitive lines and whitespace in prompt context
        to fit within target character/token budget.
        """
        if len(raw_prompt) <= target_max_chars:
            return raw_prompt

        lines = raw_prompt.split("\n")
        unique_lines = []
        seen = set()

        for line in lines:
            trimmed = line.strip()
            if trimmed and trimmed not in seen:
                seen.add(trimmed)
                unique_lines.append(line)

        compressed = "\n".join(unique_lines)
        if len(compressed) > target_max_chars:
            compressed = compressed[:target_max_chars] + "\n[CONTEXT TRUNCATED FOR TOKEN BUDGET]"

        logger.info("[COST OPTIMIZER] Compressed prompt length from %d to %d chars", len(raw_prompt), len(compressed))
        return compressed

    def get_cached_response(self, prompt: str) -> Optional[Dict[str, Any]]:
        """Checks semantic response cache using prompt hash."""
        h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        return self.semantic_cache.get(h)

    def cache_response(self, prompt: str, response_payload: Dict[str, Any]):
        """Stores LLM response payload in semantic cache."""
        h = hashlib.sha256(prompt.encode("utf-8")).hexdigest()
        self.semantic_cache[h] = response_payload
