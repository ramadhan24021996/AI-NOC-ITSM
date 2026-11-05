import logging
import asyncio
import os
import json
import time
import urllib.request
import urllib.error
import importlib
from typing import Optional, Dict, Any, List
try:
    genai: Any = importlib.import_module("google.genai")
except Exception:
    genai = None
from cryptography.fernet import Fernet
import re

logger = logging.getLogger("LLM_ENTERPRISE_ROUTER")

# ── Token Circuit Breaker Config ──────────────────────────────────────────────
MAX_TOKENS_PER_INCIDENT = int(os.getenv("LLM_MAX_TOKENS_PER_INCIDENT", "50000"))
TOKEN_ESTIMATE_RATIO    = 4   # 1 token ≈ 4 karakter
TOKEN_BUDGET_TTL_SEC    = 3600

# ── 9 Provider Registry ───────────────────────────────────────────────────────
OPENAI_COMPATIBLE_PROVIDERS = {
    "groq":       "https://api.groq.com/openai/v1/chat/completions",
    "deepseek":   "https://api.deepseek.com/v1/chat/completions",
    "openrouter": "https://openrouter.ai/api/v1/chat/completions",
    "mistral":    "https://api.mistral.ai/v1/chat/completions",
    "together":   "https://api.together.xyz/v1/chat/completions",
    "openai":     "https://api.openai.com/v1/chat/completions",
    "huggingface":"https://api-inference.huggingface.co/v1/chat/completions",
    "anthropic":  None,  # Dedicated Anthropic API
    "ollama":     "http://localhost:11434/v1/chat/completions", # Local — no key required
}

def decrypt_key(encrypted_val: Optional[str]) -> str:
    if not encrypted_val:
        return ""
    if encrypted_val.startswith("gAAAAA"):
        sec_key = os.getenv("OSI_SECURITY_KEY")
        if not sec_key:
            logger.warning("OSI_SECURITY_KEY environment variable not set. Cannot decrypt API key.")
            return encrypted_val
        try:
            f = Fernet(sec_key.strip("'\"").encode())
            return f.decrypt(encrypted_val.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt Fernet token: {e}")
            return encrypted_val
    return encrypted_val

def parse_keys(raw_val: Any) -> List[str]:
    """Menguraikan satu key string, list key, atau multiple values untuk failover otomatis (Multi-Key Rotation Pool)"""
    keys = []
    if isinstance(raw_val, list):
        for item in raw_val:
            if isinstance(item, list):
                keys.extend(parse_keys(item))
            else:
                k = decrypt_key(str(item).strip().strip("'\""))
                if k and k not in keys:
                    keys.append(k)
    elif isinstance(raw_val, str) and raw_val.strip():
        # Bisa dipisahkan koma, titik koma, atau newline jika multiple keys dimasukkan
        for part in re.split(r'[;,\n]+', raw_val):
            part_clean = part.strip().strip("'\"")
            if part_clean:
                k = decrypt_key(part_clean)
                if k and k not in keys:
                    keys.append(k)
    return keys

def load_keys_for_provider(provider: str, config: dict) -> List[str]:
    """
    Mengumpulkan seluruh API Key untuk provider tertentu dari berbagai sumber:
    1. config[provider]["api_keys"] (list atau string)
    2. config[provider]["api_key"]  (list atau string)
    3. ENV: {PROVIDER}_API_KEYS
    4. ENV: {PROVIDER}_API_KEY
    5. ENV: {PROVIDER}_API_KEY_1, {PROVIDER}_API_KEY_2, dst.
    """
    keys = []
    p_upper = provider.upper()

    cfg_p = config.get(provider, {})
    if isinstance(cfg_p, dict):
        if "api_keys" in cfg_p:
            keys.extend(parse_keys(cfg_p.get("api_keys")))
        if "api_key" in cfg_p:
            keys.extend(parse_keys(cfg_p.get("api_key")))

    env_keys_plural = os.getenv(f"{p_upper}_API_KEYS")
    if env_keys_plural:
        keys.extend(parse_keys(env_keys_plural))

    env_key_singular = os.getenv(f"{p_upper}_API_KEY")
    if env_key_singular:
        keys.extend(parse_keys(env_key_singular))

    for idx in range(1, 50):
        env_num = os.getenv(f"{p_upper}_API_KEY_{idx}")
        if env_num:
            keys.extend(parse_keys(env_num))

    unique_keys = []
    for k in keys:
        if k and k not in unique_keys:
            unique_keys.append(k)
    return unique_keys

def load_ai_config():
    config_paths = ["/app/ai_config.json", "./ai_config.json", "./portal/ai_config.json", "../portal/ai_config.json"]
    for path in config_paths:
        if os.path.exists(path):
            try:
                with open(path, "r") as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Error loading config {path}: {e}")
    return dict()

# ── Feature 1: Prompt Normalizer ──────────────────────────────────────────────
class PromptNormalizer:
    @staticmethod
    def normalize(prompt: str) -> str:
        if not prompt:
            return ""
        clean = prompt.strip()
        clean = re.sub(r'\n{3,}', '\n\n', clean)
        clean = re.sub(r'(?i)bearer\s+[a-zA-Z0-9_\-\.]+', 'bearer [REDACTED]', clean)
        clean = re.sub(r'(?i)(api[_\-]?key)["\':\s]+[a-zA-Z0-9_\-]+', r'\1" : "[REDACTED]"', clean)
        return clean

# ── Feature 2: Incident Scorer ────────────────────────────────────────────────
class IncidentScorer:
    @staticmethod
    def score(severity_score: int) -> dict:
        budget = {
            "token_budget": 16000,
            "latency_budget_ms": 15000,
            "cost_budget_usd": 0.002,
            "preferred_tier": "low"
        }
        if severity_score >= 85:
            budget["token_budget"] = 128000
            budget["latency_budget_ms"] = 30000
            budget["cost_budget_usd"] = 0.05
            budget["preferred_tier"] = "critical"
        elif severity_score >= 60:
            budget["token_budget"] = 32000
            budget["latency_budget_ms"] = 20000
            budget["cost_budget_usd"] = 0.01
            budget["preferred_tier"] = "medium"
        return budget

# ── Feature 3: Multi-Key KeyPool Manager ──────────────────────────────────────
class KeyPoolManager:
    """
    Mengelola Multi-Key Rotation Pool per provider.
    Jika 1 Key terkena Rate Limit (429) atau Quota Exhausted (403/402),
    Key tersebut di-cooldown secara otomatis dan digantikan oleh Key berikutnya di pool.
    """
    def __init__(self):
        self.pools: Dict[str, List[str]] = {}
        self.indexes: Dict[str, int] = {}
        self.cooldowns: Dict[str, Dict[str, float]] = {} # provider -> {key: unblock_timestamp}

    def register_provider_keys(self, provider: str, keys: List[str]):
        self.pools[provider] = keys
        self.indexes[provider] = 0
        if provider not in self.cooldowns:
            self.cooldowns[provider] = {}
        if keys:
            logger.info(f"🔑 [KEY POOL] Registered {len(keys)} key(s) for provider '{provider}'.")

    def get_active_key(self, provider: str) -> Optional[str]:
        keys = self.pools.get(provider, [])
        if not keys:
            return "" if provider == "ollama" else None

        now = time.time()
        start_idx = self.indexes.get(provider, 0)
        n = len(keys)

        for i in range(n):
            idx = (start_idx + i) % n
            key = keys[idx]
            unblock = self.cooldowns[provider].get(key, 0)
            if now >= unblock:
                self.indexes[provider] = idx
                return key
        
        # Semua key dalam cooldown
        return None

    def mark_key_rate_limited(self, provider: str, key: str, cooldown_sec: float = 60.0):
        if not key: return
        unblock_time = time.time() + cooldown_sec
        if provider not in self.cooldowns:
            self.cooldowns[provider] = {}
        self.cooldowns[provider][key] = unblock_time
        logger.warning(f"🔑 [KEY POOL] Key for '{provider}' rate-limited/quota exhausted. Cooldown for {cooldown_sec}s. Switching to next key.")
        
        keys = self.pools.get(provider, [])
        if keys:
            self.indexes[provider] = (self.indexes.get(provider, 0) + 1) % len(keys)

# ── Core Component: 9-Provider Multi-Key Autonomous Gateway ──────────────────
class LLMRouter:
    def __init__(self, db_conn=None):
        self.db = db_conn
        self._redis = None
        self.normalizer = PromptNormalizer()
        self.scorer = IncidentScorer()
        self.key_manager = KeyPoolManager()

        config = load_ai_config()

        # Load keys untuk 9 Provider (Mendukung tak terbatas / berapapun Multi-Key per provider)
        all_providers = ["gemini", "groq", "deepseek", "openrouter", "mistral", "together", "openai", "anthropic", "ollama"]
        provider_keys_map = {}
        for p in all_providers:
            if p == "ollama":
                provider_keys_map[p] = [""]
            else:
                provider_keys_map[p] = load_keys_for_provider(p, config)

        for p, klist in provider_keys_map.items():
            self.key_manager.register_provider_keys(p, klist)

        self.urls = {**OPENAI_COMPATIBLE_PROVIDERS}
        for provider in OPENAI_COMPATIBLE_PROVIDERS:
            cfg_url = config.get(provider, {}).get("api_url")
            if cfg_url:
                self.urls[provider] = cfg_url

        self.availability = {
            "gemini":     bool(provider_keys_map["gemini"]),
            "groq":       bool(provider_keys_map["groq"]),
            "deepseek":   bool(provider_keys_map["deepseek"]),
            "openrouter": True,  # OpenRouter supports free tier models
            "mistral":    bool(provider_keys_map["mistral"]),
            "together":   bool(provider_keys_map["together"]),
            "openai":     bool(provider_keys_map["openai"]),
            "anthropic":  bool(provider_keys_map["anthropic"]),
            "ollama":     True, # Local always available
        }

        from resilience.circuit_breaker import CircuitBreaker
        self.circuit_breakers = {
            p: CircuitBreaker(failure_threshold=3, recovery_timeout_sec=30)
            for p in self.availability
        }

        self.gemini_client = None
        self._init_gemini_client()

        self.memory_graph: Optional[Any] = None
        self.auto_builder: Optional[Any] = None
        self.model_evaluator: Optional[Any] = None

        try:
            from learning.ai_memory_graph import AIMemoryGraph
            try:
                from python_ai_core.knowledge.knowledge_auto_builder import KnowledgeAutoBuilder
            except ImportError:
                from knowledge.knowledge_auto_builder import KnowledgeAutoBuilder
            from learning.model_evaluator_pipeline import ModelEvaluatorPipeline

            self.memory_graph = AIMemoryGraph()
            self.auto_builder = KnowledgeAutoBuilder()
            self.model_evaluator = ModelEvaluatorPipeline()
            logger.info("AI Memory Graph, Knowledge Auto-Builder, and Model Evaluator initialized.")
        except Exception as e:
            logger.warning(f"Cognitive enhancements engines fallback initialization: {e}")

        active = [p for p, v in self.availability.items() if v]
        logger.info(f"[LLM ROUTER] 9-Provider Multi-Key Autonomous Gateway ready. Active providers: {active}")

    def _init_gemini_client(self):
        active_key = self.key_manager.get_active_key("gemini")
        if active_key and genai is not None:
            try:
                self.gemini_client = genai.Client(api_key=active_key)
                self.availability["gemini"] = True
            except Exception as e:
                logger.error(f"Failed to configure Gemini SDK with key: {e}")
                self.availability["gemini"] = False

    def _execute_openai_compatible(self, provider: str, url: str, api_key: str, model_name: str, prompt: str, timeout: int) -> dict:
        if not url:
            return {"status": "FAILED", "error": f"{provider} URL not configured"}
        if not api_key and provider not in ("ollama", "openrouter"):
            return {"status": "FAILED", "error": f"{provider} active key unavailable"}

        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"

        if provider == "openrouter":
            headers["HTTP-Referer"] = "https://osi-system.internal"
            headers["X-Title"] = "OSI AI NOC Autonomous Gateway"

        data = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout / 1000.0) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                text = resp_data["choices"][0]["message"]["content"]
                usage = resp_data.get("usage", {})
                return {
                    "status": "SUCCESS",
                    "model": model_name,
                    "provider": provider,
                    "response": text,
                    "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                    "completion_tokens": int(usage.get("completion_tokens", 0))
                }
        except urllib.error.HTTPError as e:
            # Catch 429 Rate Limit or 403 Quota Limit to trigger Key Pool Rotation
            if e.code in (429, 403, 402):
                self.key_manager.mark_key_rate_limited(provider, api_key, cooldown_sec=120.0)
            return {"status": "FAILED", "error": f"{provider} HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"status": "FAILED", "error": f"{provider} request failed: {e}"}

    def _execute_gemini(self, model_name: str, prompt: str) -> dict:
        keys_pool = self.key_manager.pools.get("gemini", [])
        max_attempts = max(1, len(keys_pool))
        last_error = "Gemini active key unavailable"

        for _ in range(max_attempts):
            active_key = self.key_manager.get_active_key("gemini")
            if not active_key:
                break
            if genai is not None and hasattr(genai, "Client"):
                try:
                    client = genai.Client(api_key=active_key)
                    resp = client.models.generate_content(
                        model=model_name,
                        contents=prompt
                    )
                    p_tok = 0
                    c_tok = 0
                    if hasattr(resp, "usage_metadata") and resp.usage_metadata:
                        p_tok = getattr(resp.usage_metadata, "prompt_token_count", 0)
                        c_tok = getattr(resp.usage_metadata, "candidates_token_count", 0)
                    return {
                        "status": "SUCCESS",
                        "model": model_name,
                        "provider": "gemini",
                        "response": resp.text,
                        "prompt_tokens": p_tok,
                        "completion_tokens": c_tok
                    }
                except Exception as e:
                    err_str = str(e)
                    last_error = f"Gemini SDK error: {err_str}"
                    if any(code in err_str for code in ("429", "RESOURCE_EXHAUSTED", "403", "QUOTA_EXCEEDED", "PERMISSION_DENIED")):
                        self.key_manager.mark_key_rate_limited("gemini", active_key, cooldown_sec=180.0)
                        continue

            # REST API fallback
            url = f"https://generativelanguage.googleapis.com/v1beta/models/{model_name}:generateContent?key={active_key}"
            data = {"contents": [{"parts": [{"text": prompt}]}]}
            req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
            try:
                with urllib.request.urlopen(req, timeout=12.0) as response:
                    resp_data = json.loads(response.read().decode("utf-8"))
                    candidates = resp_data.get("candidates", [])
                    if candidates:
                        parts = candidates[0].get("text", "") if "text" in candidates[0] else ""
                        parts_list = candidates[0].get("content", {}).get("parts", [])
                        text = parts_list[0].get("text", "") if parts_list else parts
                        if text:
                            return {
                                "status": "SUCCESS",
                                "model": model_name,
                                "provider": "gemini",
                                "response": text,
                                "prompt_tokens": 100,
                                "completion_tokens": 100
                            }
                    last_error = "Gemini REST empty response"
            except urllib.error.HTTPError as e:
                last_error = f"Gemini HTTP {e.code}: {e.reason}"
                if e.code in (429, 403, 402):
                    self.key_manager.mark_key_rate_limited("gemini", active_key, cooldown_sec=180.0)
                    continue
            except Exception as e:
                last_error = f"Gemini request failed: {e}"

        return {"status": "FAILED", "error": last_error}

    def _execute_anthropic(self, model_name: str, prompt: str, timeout: int) -> dict:
        key = self.key_manager.get_active_key("anthropic")
        if not key:
            return {"status": "FAILED", "error": "Anthropic active key unavailable"}
        data = {
            "model": model_name,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}]
        }
        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=json.dumps(data).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "x-api-key": key,
                "anthropic-version": "2023-06-01"
            },
            method="POST"
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout / 1000.0) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                text = resp_data["content"][0]["text"]
                usage = resp_data.get("usage", {})
                return {
                    "status": "SUCCESS",
                    "model": model_name,
                    "provider": "anthropic",
                    "response": text,
                    "prompt_tokens": int(usage.get("input_tokens", 0)),
                    "completion_tokens": int(usage.get("output_tokens", 0))
                }
        except urllib.error.HTTPError as e:
            if e.code in (429, 403, 402):
                self.key_manager.mark_key_rate_limited("anthropic", key, cooldown_sec=120.0)
            return {"status": "FAILED", "error": f"Anthropic HTTP {e.code}: {e.reason}"}
        except Exception as e:
            return {"status": "FAILED", "error": f"Anthropic request failed: {e}"}

    async def _dispatch_call(self, provider: str, model_name: str, prompt: str, latency_budget_ms: int) -> dict:
        timeout_s = latency_budget_ms / 1000.0
        try:
            if provider == "gemini":
                return await asyncio.wait_for(
                    asyncio.to_thread(self._execute_gemini, model_name, prompt),
                    timeout=timeout_s
                )
            elif provider == "anthropic":
                return await asyncio.wait_for(
                    asyncio.to_thread(self._execute_anthropic, model_name, prompt, latency_budget_ms),
                    timeout=timeout_s
                )
            elif provider in OPENAI_COMPATIBLE_PROVIDERS:
                raw_url = self.urls.get(provider)
                url: str = raw_url if isinstance(raw_url, str) else ""
                key = self.key_manager.get_active_key(provider) or ""
                return await asyncio.wait_for(
                    asyncio.to_thread(
                        self._execute_openai_compatible,
                        provider, url, key, model_name, prompt, latency_budget_ms
                    ),
                    timeout=timeout_s
                )
            else:
                return {"status": "FAILED", "error": f"Unknown provider: {provider}"}
        except asyncio.TimeoutError:
            return {"status": "FAILED", "error": f"{provider} timeout ({latency_budget_ms}ms budget exceeded)"}

    # ─────────────────────────────────────────────────────────────
    # 9-PROVIDER WATERFALL ROUTE PLAN
    # ─────────────────────────────────────────────────────────────
    def _plan_route(self, preferred_tier: str) -> list:
        if preferred_tier == "critical":
            return [
                {"provider": "openrouter", "model": "openrouter/auto"},
                {"provider": "mistral",    "model": "mistral-small-latest"},
                {"provider": "groq",       "model": "llama-3.3-70b-versatile"},
                {"provider": "gemini",     "model": "gemini-2.0-flash"},
                {"provider": "deepseek",   "model": "deepseek-chat"},
            ]
        elif preferred_tier == "medium":
            return [
                {"provider": "openrouter", "model": "openrouter/auto"},
                {"provider": "mistral",    "model": "mistral-small-latest"},
                {"provider": "groq",       "model": "llama-3.3-70b-versatile"},
                {"provider": "gemini",     "model": "gemini-2.0-flash"},
                {"provider": "deepseek",   "model": "deepseek-chat"},
            ]
        else:
            return [
                {"provider": "openrouter", "model": "openrouter/auto"},
                {"provider": "mistral",    "model": "mistral-small-latest"},
                {"provider": "groq",       "model": "llama-3.3-70b-versatile"},
                {"provider": "gemini",     "model": "gemini-2.0-flash"},
            ]

    async def execute_with_retry(self, severity_score: int, prompt: str, max_retries: int = 2, incident_id: str = ""):
        clean_prompt = self.normalizer.normalize(prompt)

        if self.db:
            try:
                with self.db.cursor() as cur:
                    cur.execute("""
                        SELECT new_diagnostic_rule
                        FROM ai_learning_curriculum
                        WHERE status = 'LEARNED'
                        ORDER BY created_at DESC
                        LIMIT 5
                    """)
                    rules = cur.fetchall()
                    if rules:
                        curriculum_context = "\n[CRITICAL AI DIAGNOSTIC LESSONS LEARNED FROM PAST MISTAKES]:\n"
                        for (rule,) in rules:
                            curriculum_context += f"- {rule}\n"
                        clean_prompt = curriculum_context + "\n" + clean_prompt
            except Exception as e:
                logger.debug(f'Learning Plane fetch error: {e}')

        estimated_tokens = self._estimate_tokens(clean_prompt)
        budget = self.scorer.score(severity_score)

        if not self._check_budget(incident_id, estimated_tokens):
            logger.warning(f"[LLM ROUTER] Token budget exhausted for incident={incident_id}. Using rule engine.")
            return self.rule_engine_fallback(clean_prompt)

        semantic_cache = None
        try:
            from core.semantic_cache_manager import get_semantic_cache_manager
            semantic_cache = get_semantic_cache_manager()
            cached_val = semantic_cache.get(clean_prompt)
            if cached_val:
                logger.info("⚡ [LLM ROUTER] Prompt hit Semantic Cache (< 20ms | Cost: $0.00)")
                return cached_val
        except Exception as e:
            logger.debug(f"[LLM ROUTER] Semantic cache bypass: {e}")

        route_plan = self._plan_route(budget["preferred_tier"])

        for attempt in range(1, max_retries + 1):
            for provider_info in route_plan:
                provider_name = provider_info["provider"]
                model_name    = provider_info["model"]

                # Cek jika provider punya key aktif di KeyPool
                active_key = self.key_manager.get_active_key(provider_name)
                if active_key is None and provider_name != "ollama":
                    continue

                cb = self.circuit_breakers.get(provider_name)
                if cb:
                    try:
                        cb.check()
                    except Exception:
                        logger.warning(f"[LLM ROUTER] {provider_name} Circuit OPEN. Skipping.")
                        continue

                logger.info(f"[LLM ROUTER] Attempt {attempt}: {provider_name} ({model_name}) | Budget: {budget['latency_budget_ms']}ms")
                t0 = time.monotonic()
                try:
                    res = await self._dispatch_call(provider_name, model_name, clean_prompt, budget["latency_budget_ms"])
                    ms = int((time.monotonic() - t0) * 1000)

                    if res and isinstance(res, dict) and res.get("status") == "SUCCESS":
                        if cb: cb.record_success()
                        self._log_call(incident_id, model_name, clean_prompt, res.get("response", ""), ms, "SUCCESS",
                                       res.get("prompt_tokens", 0), res.get("completion_tokens", 0))
                        if semantic_cache:
                            semantic_cache.set(clean_prompt, res)
                        logger.info(f"✅ [LLM ROUTER] SUCCESS via {provider_name}/{model_name} in {ms}ms")
                        return res
                    else:
                        if cb: cb.record_failure()
                        err_msg = res.get("error") if (res and isinstance(res, dict)) else "Unknown error"
                        logger.warning(f"[LLM ROUTER] {provider_name} returned non-success: {err_msg}")
                except Exception as e:
                    if cb: cb.record_failure()
                    logger.warning(f"[LLM ROUTER] Provider {provider_name} execution failed: {e}")

            delay = 1.0 * (2 ** (attempt - 1))
            logger.warning(f"[LLM ROUTER] All route plan providers failed on attempt {attempt}. Retrying in {delay}s...")
            await asyncio.sleep(delay)

        logger.warning("[LLM ROUTER] All 9 LLM providers failed. Falling back to local Rule Engine.")
        return self.rule_engine_fallback(clean_prompt)

    def rule_engine_fallback(self, clean_prompt: str) -> Dict[str, Any]:
        try:
            from learning.local_decision_tree_engine import LocalDecisionTreeEngine
            dt_engine = LocalDecisionTreeEngine()
            intent, conf, reasoning = dt_engine.predict_offline_intent({}, clean_prompt)
            response_text = (
                f"OFFLINE RULE ENGINE FALLBACK (Random Forest Model rules.pkl):\n"
                f"- Diagnosed Intent: {intent} (Confidence: {conf*100:.1f}%)\n"
                f"- Model Reasoning : {reasoning}\n"
                f"- Recommendation  : Execute standard SOP for {intent} with automated rollback guard."
            )
            return {
                "status": "SUCCESS",
                "provider": "offline-rule-engine",
                "model": "RandomForestClassifier_rules.pkl",
                "response": response_text,
                "intent": intent,
                "confidence": conf,
                "prompt_tokens": 0,
                "completion_tokens": len(response_text) // 4
            }
        except Exception as e:
            logger.error(f"[LLM ROUTER] Local Decision Tree Fallback error: {e}")
            return {
                "status": "FALLBACK_FAILED",
                "provider": "offline-rule-engine",
                "response": f"Static Safe Fallback: Execute System Health Check for prompt: {clean_prompt[:50]}",
                "prompt_tokens": 0,
                "completion_tokens": 10
            }

    def _get_redis(self):
        if self._redis is None:
            try:
                import redis as redis_lib
                r = redis_lib.Redis(
                    password=os.getenv('REDIS_PASSWORD'),
                    host=os.getenv("REDIS_HOST", "redis"),
                    port=int(os.getenv("REDIS_PORT", "6379")),
                    decode_responses=True,
                    socket_connect_timeout=2,
                    protocol=2
                )
                r.ping()
                self._redis = r
            except Exception as e:
                logger.warning("[LLM BUDGET] Redis unavailable: %s", e)
        return self._redis

    def _estimate_tokens(self, text: str) -> int:
        return max(1, len(text) // TOKEN_ESTIMATE_RATIO)

    def _check_budget(self, incident_id: str, estimated_tokens: int) -> bool:
        if not incident_id:
            return True
        r = self._get_redis()
        if not r:
            return True
        try:
            key  = f"llm:budget:{incident_id}"
            used = int(r.get(key) or 0)
            if used + estimated_tokens > MAX_TOKENS_PER_INCIDENT:
                logger.warning("[LLM BUDGET] Circuit OPEN | incident=%s used=%d estimated=%d limit=%d",
                               incident_id, used, estimated_tokens, MAX_TOKENS_PER_INCIDENT)
                return False
            r.incrby(key, estimated_tokens)
            r.expire(key, TOKEN_BUDGET_TTL_SEC)
            return True
        except Exception:
            return True

    def _log_call(self, incident_id: str, model: str, prompt: str, response: str, latency_ms: int, status: str,
                  exact_p_tokens: int = 0, exact_c_tokens: int = 0):
        if not self.db:
            return
        try:
            p_tokens = exact_p_tokens if exact_p_tokens > 0 else self._estimate_tokens(prompt)
            r_tokens = exact_c_tokens if exact_c_tokens > 0 else self._estimate_tokens(response)
            with self.db.cursor() as cur:
                cur.execute(
                    "INSERT INTO llm_call_logs (incident_id, model, prompt_tokens, response_tokens, latency_ms, status, created_at) VALUES (%s, %s, %s, %s, %s, %s, NOW())",
                    (incident_id, model, p_tokens, r_tokens, latency_ms, status),
                )
            self.db.commit()
        except Exception as e:
            logger.debug("[LLM LOG] Could not write llm_call_logs: %s", e)

    def route_incident(self, severity_score: int) -> str:
        budget = self.scorer.score(severity_score)
        return "gemini-2.0-flash"

def get_router():
    return LLMRouter()
