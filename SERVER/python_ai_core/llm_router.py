"""
Unified LLM Router Compatibility Facade (`SERVER/python_ai_core/llm_router.py`)
Consolidates both `llm_router` and `engines.llm_router` into a single canonical implementation.
"""

try:
    from .engines.llm_router import (
        LLMRouter,
        get_router,
        decrypt_key,
        parse_keys,
        load_keys_for_provider,
        load_ai_config,
        OPENAI_COMPATIBLE_PROVIDERS,
        MAX_TOKENS_PER_INCIDENT,
        TOKEN_ESTIMATE_RATIO,
        TOKEN_BUDGET_TTL_SEC,
        genai,
    )
except ImportError:
    from engines.llm_router import (  # type: ignore[no-redef]
        LLMRouter,
        get_router,
        decrypt_key,
        parse_keys,
        load_keys_for_provider,
        load_ai_config,
        OPENAI_COMPATIBLE_PROVIDERS,
        MAX_TOKENS_PER_INCIDENT,
        TOKEN_ESTIMATE_RATIO,
        TOKEN_BUDGET_TTL_SEC,
        genai,
    )

__all__ = [
    "LLMRouter",
    "get_router",
    "decrypt_key",
    "parse_keys",
    "load_keys_for_provider",
    "load_ai_config",
    "OPENAI_COMPATIBLE_PROVIDERS",
    "MAX_TOKENS_PER_INCIDENT",
    "TOKEN_ESTIMATE_RATIO",
    "TOKEN_BUDGET_TTL_SEC",
    "genai",
]
