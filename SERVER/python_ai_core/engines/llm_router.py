import logging
import asyncio
import os
import json
import time
import urllib.request
import importlib
try:
    genai: Any = importlib.import_module("google.genai")
except Exception:
    genai = None
from cryptography.fernet import Fernet
import re
from typing import Optional, Dict, Any, List

logger = logging.getLogger("LLM_ENTERPRISE_ROUTER")

# ── Token Circuit Breaker Config ──────────────────────────────────────────────
MAX_TOKENS_PER_INCIDENT = int(os.getenv("LLM_MAX_TOKENS_PER_INCIDENT", "50000"))
TOKEN_ESTIMATE_RATIO    = 4   # 1 token ≈ 4 karakter (heuristik universal)
TOKEN_BUDGET_TTL_SEC    = 3600  # reset budget setelah 1 jam

def decrypt_key(encrypted_val: Optional[str]) -> str:
    if not encrypted_val:
        return ""
    if encrypted_val.startswith("gAAAAA"):
        sec_key = os.getenv("OSI_SECURITY_KEY")
        if not sec_key:
            logger.error("OSI_SECURITY_KEY environment variable not set. Cannot decrypt Fernet-encrypted API key (fail closed).")
            return ""
        try:
            f = Fernet(sec_key.strip("'\"").encode())
            return f.decrypt(encrypted_val.encode()).decode()
        except Exception as e:
            logger.error(f"Failed to decrypt Fernet token: {e}. Failing closed.")
            return ""
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
        for part in re.split(r'[;,\n]+', raw_val):
            part_clean = part.strip().strip("'\"")
            if part_clean:
                k = decrypt_key(part_clean)
                if k and k not in keys:
                    keys.append(k)
    return keys

def load_keys_for_provider(provider: str, config: dict) -> List[str]:
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

class KeyPoolManager:
    def __init__(self):
        self.pools: Dict[str, List[str]] = {}
        self.indexes: Dict[str, int] = {}
        self.cooldowns: Dict[str, Dict[str, float]] = {}

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
    """Membersihkan prompt dari data yang tidak perlu sebelum dikirim ke LLM"""
    @staticmethod
    def normalize(prompt: str) -> str:
        if not prompt: 
            return ""
        clean = prompt.strip()
        # Hapus spasi kosong berlebihan
        clean = re.sub(r'\n{3,}', '\n\n', clean)
        # Redaksi sederhana jika ada secret key tidak sengaja masuk log
        clean = re.sub(r'(?i)bearer\s+[a-zA-Z0-9_\-\.]+', 'bearer [REDACTED]', clean)
        clean = re.sub(r'(?i)(api[_\-]?key)["\':\s]+[a-zA-Z0-9_\-]+', r'\1" : "[REDACTED]"', clean)
        return clean

# ── Feature 2: Incident Scorer ────────────────────────────────────────────────
class IncidentScorer:
    """
    Menghitung Budget (Token & Cost & Latency) berdasarkan tingkat keparahan insiden.
    """
    @staticmethod
    def score(severity_score: int) -> dict:
        budget = {
            "token_budget": 8000,
            "latency_budget_ms": 5000,
            "cost_budget_usd": 0.002,
            "preferred_tier": "low"
        }
        
        if severity_score >= 85: # CRITICAL
            budget["token_budget"] = 128000
            budget["latency_budget_ms"] = 15000
            budget["cost_budget_usd"] = 0.05
            budget["preferred_tier"] = "critical"
        elif severity_score >= 60: # HIGH / MEDIUM
            budget["token_budget"] = 32000
            budget["latency_budget_ms"] = 10000
            budget["cost_budget_usd"] = 0.01
            budget["preferred_tier"] = "medium"
            
        return budget

# ── Process-Wide Shared Singletons (Avoid Re-Initializing SQLite & Key Pools per Incident) ──
_SHARED_INIT_LOCK = __import__("threading").RLock()
_SHARED_COGNITIVE: Dict[str, Any] = {}
_ROUTER_SINGLETON: Optional["LLMRouter"] = None


# ── Core Component: LLM Router ───────────────────────────────────────────────
class LLMRouter:
    def __init__(self, db_conn=None):
        self.db = db_conn
        self._redis = None
        self.normalizer = PromptNormalizer()
        self.scorer = IncidentScorer()

        with _SHARED_INIT_LOCK:
            if "key_manager" not in _SHARED_COGNITIVE:
                km = KeyPoolManager()
                config = load_ai_config()
                all_providers = ["gemini", "groq", "deepseek", "openrouter", "mistral", "together", "openai", "anthropic", "ollama"]
                provider_keys_map = {}
                for p in all_providers:
                    if p == "ollama":
                        provider_keys_map[p] = [""]
                    else:
                        provider_keys_map[p] = load_keys_for_provider(p, config)
                for p, klist in provider_keys_map.items():
                    km.register_provider_keys(p, klist)
                _SHARED_COGNITIVE["key_manager"] = km
                _SHARED_COGNITIVE["config"] = config
                _SHARED_COGNITIVE["provider_keys_map"] = provider_keys_map

            self.key_manager = _SHARED_COGNITIVE["key_manager"]
            config = _SHARED_COGNITIVE["config"]
            provider_keys_map = _SHARED_COGNITIVE["provider_keys_map"]

        self.keys = {p: (klist[0] if klist else "") for p, klist in provider_keys_map.items()}
        
        self.urls = {
            "groq": config.get("groq", {}).get("api_url", "https://api.groq.com/openai/v1/chat/completions"),
            "deepseek": config.get("deepseek", {}).get("api_url", "https://api.deepseek.com/beta/chat/completions"),
        }
        
        # Identifikasi ketersediaan provider
        self.availability = {
            "gemini": bool(provider_keys_map["gemini"]),
            "groq": bool(provider_keys_map["groq"]),
            "deepseek": bool(provider_keys_map["deepseek"]),
            "openrouter": True,
            "mistral": bool(provider_keys_map["mistral"]),
            "together": bool(provider_keys_map["together"]),
            "openai": bool(provider_keys_map["openai"]),
            "anthropic": bool(provider_keys_map["anthropic"]),
            "ollama": True,
        }
        
        # Resilience: Circuit Breakers for each provider (shared across instances)
        from resilience.circuit_breaker import CircuitBreaker
        with _SHARED_INIT_LOCK:
            if "circuit_breakers" not in _SHARED_COGNITIVE:
                _SHARED_COGNITIVE["circuit_breakers"] = {
                    "gemini": CircuitBreaker(failure_threshold=3, recovery_timeout_sec=30),
                    "groq": CircuitBreaker(failure_threshold=3, recovery_timeout_sec=30),
                    "deepseek": CircuitBreaker(failure_threshold=3, recovery_timeout_sec=30),
                }
            self.circuit_breakers = _SHARED_COGNITIVE["circuit_breakers"]
        
        self.gemini_client = None
        if self.availability["gemini"] and genai is not None:
            try:
                active_gem_key = self.key_manager.get_active_key("gemini") or self.keys["gemini"]
                self.gemini_client = genai.Client(api_key=active_gem_key)
            except Exception as e:
                self.availability["gemini"] = False
                logger.error(f"Failed to configure Gemini SDK: {e}")

        # Cognitive Enhancements Engine Initialization (Once per process)
        with _SHARED_INIT_LOCK:
            if "cognitive_initialized" not in _SHARED_COGNITIVE:
                _SHARED_COGNITIVE["cognitive_initialized"] = True
                try:
                    from learning.ai_memory_graph import AIMemoryGraph
                    try:
                        from python_ai_core.knowledge.knowledge_auto_builder import KnowledgeAutoBuilder
                    except ImportError:
                        from knowledge.knowledge_auto_builder import KnowledgeAutoBuilder
                    from learning.model_evaluator_pipeline import ModelEvaluatorPipeline
                    _SHARED_COGNITIVE["memory_graph"] = AIMemoryGraph()
                    _SHARED_COGNITIVE["auto_builder"] = KnowledgeAutoBuilder()
                    _SHARED_COGNITIVE["model_evaluator"] = ModelEvaluatorPipeline()
                    logger.info("AI Memory Graph, Knowledge Auto-Builder, and Model Evaluator initialized (singleton).")
                except Exception as e:
                    _SHARED_COGNITIVE["memory_graph"] = None
                    _SHARED_COGNITIVE["auto_builder"] = None
                    _SHARED_COGNITIVE["model_evaluator"] = None
                    logger.warning(f"Cognitive enhancements engines fallback initialization: {e}")

        self.memory_graph = _SHARED_COGNITIVE.get("memory_graph")
        self.auto_builder = _SHARED_COGNITIVE.get("auto_builder")
        self.model_evaluator = _SHARED_COGNITIVE.get("model_evaluator")

    @property
    def gemini_ready(self) -> bool:
        return self.availability.get("gemini", False)

    @property
    def deepseek_ready(self) -> bool:
        return self.availability.get("deepseek", False)

    @property
    def groq_ready(self) -> bool:
        return self.availability.get("groq", False)

    def execute_groq(self, prompt: str, model_name: str = "llama-3.1-8b-instant", timeout: int = 5000) -> dict:
        url = self.urls.get("groq", "https://api.groq.com/openai/v1/chat/completions")
        key = self.keys.get("groq", "")
        return self._execute_openai_compatible("groq", url, key, model_name, prompt, timeout)

    def execute_deepseek(self, prompt: str, model_name: str = "deepseek-reasoner", timeout: int = 10000) -> dict:
        url = self.urls.get("deepseek", "https://api.deepseek.com/chat/completions")
        key = self.keys.get("deepseek", "")
        return self._execute_openai_compatible("deepseek", url, key, model_name, prompt, timeout)

    # ─────────────────────────────────────────────────────────────
    # INTERNAL EXECUTORS
    # ─────────────────────────────────────────────────────────────
    def _execute_openai_compatible(self, provider: str, url: str, api_key: str, model_name: str, prompt: str, timeout: int) -> dict:
        if not api_key and provider != "local":
            return {"status": "FAILED", "error": f"{provider} Key not configured"}
            
        headers = {"Content-Type": "application/json"}
        if api_key:
            headers["Authorization"] = f"Bearer {api_key}"
            
        data = {
            "model": model_name,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.3
        }
        req = urllib.request.Request(url, data=json.dumps(data).encode("utf-8"), headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=timeout/1000.0) as response:
                resp_data = json.loads(response.read().decode("utf-8"))
                text = resp_data["choices"][0]["message"]["content"]
                
                usage = resp_data.get("usage", {})
                return {
                    "status": "SUCCESS", 
                    "model": model_name, 
                    "response": text,
                    "prompt_tokens": int(usage.get("prompt_tokens", 0)),
                    "completion_tokens": int(usage.get("completion_tokens", 0))
                }
        except Exception as e:
            return {"status": "FAILED", "error": f"{provider} request failed: {e}"}

    def _execute_gemini(self, model_name: str, prompt: str) -> dict:
        if not self.availability["gemini"]:
            return {"status": "FAILED", "error": "Gemini not available"}
        # Replace retired Gemini 1.5 model IDs with active Gemini 3.1 / 2.5 models
        if model_name in ("gemini-1.5-flash", "gemini-1.5-pro", "gemini-3.5-flash"):
            model_name = "gemini-3.1-flash-lite-preview"

        gem_keys = self.key_manager.pools.get("gemini", []) or ([self.keys["gemini"]] if self.keys.get("gemini") else [])
        last_err = "No active Gemini key"
        for _ in range(max(1, len(gem_keys))):
            active_key = self.key_manager.get_active_key("gemini") or (gem_keys[0] if gem_keys else "")
            if not active_key:
                break
            try:
                client = genai.Client(api_key=active_key) if genai is not None else self.gemini_client
                if not client:
                    break
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
                    "response": resp.text,
                    "prompt_tokens": p_tok,
                    "completion_tokens": c_tok
                }
            except Exception as e:
                last_err = str(e)
                if "429" in last_err or "RESOURCE_EXHAUSTED" in last_err or "quota" in last_err.lower():
                    self.key_manager.mark_key_rate_limited("gemini", active_key, cooldown_sec=60.0)
                    continue
                break
        return {"status": "FAILED", "error": f"Gemini request failed: {last_err}"}

    async def _dispatch_call(self, provider: str, model_name: str, prompt: str, latency_budget_ms: int) -> dict:
        if provider == "gemini":
            try:
                return await asyncio.wait_for(asyncio.to_thread(self._execute_gemini, model_name, prompt), timeout=latency_budget_ms/1000.0)
            except asyncio.TimeoutError:
                return {"status": "FAILED", "error": "Timeout budget exceeded"}
        elif provider in ["groq", "deepseek"]:
            return await asyncio.to_thread(
                self._execute_openai_compatible, 
                provider, 
                self.urls[provider], 
                self.keys.get(provider, ""), 
                model_name, 
                prompt, 
                latency_budget_ms
            )
        return {"status": "FAILED", "error": "Unknown provider"}

    def rule_engine_fallback(self, prompt):
        prompt_lower = prompt.lower()
        if "cpu" in prompt_lower:
            resolution = "RULE_ENGINE_FALLBACK: Windows CPU sustained >95%. Rekomendasi: Identifikasi wmiprvse atau msmpeng, restart Service Winmgmt via Command Relay."
        elif "ram" in prompt_lower or "memory" in prompt_lower:
            resolution = "RULE_ENGINE_FALLBACK: Memory leaks detected. Rekomendasi: Tutup aplikasi non-kritis atau lakukan force restart client process."
        elif "disk" in prompt_lower or "storage" in prompt_lower:
            resolution = "RULE_ENGINE_FALLBACK: Disk primary C: hampir penuh. Rekomendasi: Bersihkan temp files (%TEMP%), IIS Log lama, dan Windows Update cache."
        elif "nats" in prompt_lower:
            resolution = "RULE_ENGINE_FALLBACK: NATS Stream timeout. Rekomendasi: Pastikan service nats-server aktif di master node port 4222."
        elif "printer" in prompt_lower:
            resolution = "RULE_ENGINE_FALLBACK: Printer queue stalled. Rekomendasi: Jalankan restart service Spooler pada host Windows tujuan."
        else:
            resolution = "RULE_ENGINE_FALLBACK: Peringatan telemetri umum. Rekomendasi: Periksa system events log dan hubungi NOC Engineer."
            
        return {
            "status": "SUCCESS",
            "model": "offline-rule-engine",
            "response": resolution,
            "prompt_tokens": 0,
            "completion_tokens": 0
        }

    # ─────────────────────────────────────────────────────────────
    # BUDGET TRACKING & LOGGING
    # ─────────────────────────────────────────────────────────────
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
                logger.warning("[LLM BUDGET] Circuit OPEN | incident=%s used=%d estimated=%d limit=%d", incident_id, used, estimated_tokens, MAX_TOKENS_PER_INCIDENT)
                return False
            r.incrby(key, estimated_tokens)
            r.expire(key, TOKEN_BUDGET_TTL_SEC)
            return True
        except Exception:
            return True

    def _log_call(self, incident_id: str, model: str, prompt: str, response: str, latency_ms: int, status: str, exact_p_tokens: int = 0, exact_c_tokens: int = 0):
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

    # ─────────────────────────────────────────────────────────────
    # ROUTING LOGIC
    # ─────────────────────────────────────────────────────────────
    def _plan_route(self, preferred_tier: str) -> list:
        if preferred_tier == "critical":
            return [
                {"provider": "gemini", "model": "gemini-3.1-flash-lite-preview"},
                {"provider": "groq", "model": "llama-3.3-70b-versatile"},
                {"provider": "deepseek", "model": "deepseek-reasoner"},
                {"provider": "gemini", "model": "gemini-2.5-flash"},
            ]
        elif preferred_tier == "medium":
            return [
                {"provider": "gemini", "model": "gemini-3.1-flash-lite-preview"},
                {"provider": "groq", "model": "llama-3.1-8b-instant"},
                {"provider": "deepseek", "model": "deepseek-chat"},
            ]
        else:
            return [
                {"provider": "groq", "model": "llama-3.1-8b-instant"},
                {"provider": "gemini", "model": "gemini-3.1-flash-lite-preview"},
            ]

    async def execute_with_retry(self, severity_score: int, prompt: str, max_retries: int = 2, incident_id: str = ""):
        # 1. Normalizer Pipeline
        clean_prompt = self.normalizer.normalize(prompt)
        
        # Inject Tahap 8: Learning Plane Curriculum Rules
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
                import logging; logging.getLogger(__name__).debug(f'Learning Plane fetch error: {e}')
                
        estimated_tokens = self._estimate_tokens(clean_prompt)
        
        # 2. Incident Scorer & Budget Calculator
        budget = self.scorer.score(severity_score)
        
        # Token circuit breaker
        if not self._check_budget(incident_id, estimated_tokens):
            logger.warning(f"[LLM ROUTER] Token budget exhausted for incident={incident_id}. Using rule engine.")
            return self.rule_engine_fallback(clean_prompt)
            
        # Semantic Cache Layer
        try:
            from core.cache_manager import get_cache_manager
            cache_mgr = get_cache_manager()
            cached_val = cache_mgr.get_llm_cache(clean_prompt)
            if cached_val:
                logger.info("[LLM ROUTER] Prompt hit semantic cache.")
                return cached_val
        except ImportError:
            cache_mgr = None

        # 3. Intelligent Provider Routing
        route_plan = self._plan_route(budget["preferred_tier"])
        last_error = None
        
        for attempt in range(1, max_retries + 1):
            for provider_info in route_plan:
                provider_name = provider_info["provider"]
                model_name = provider_info["model"]
                
                # Check provider availability
                if not self.availability.get(provider_name):
                    continue

                # Resilience: Circuit Breaker Check
                cb = self.circuit_breakers.get(provider_name)
                if cb:
                    try:
                        cb.check()
                    except Exception:
                        logger.warning(f"[LLM ROUTER] {provider_name} Circuit OPEN. Skipping.")
                        continue
                        
                logger.info(f"[LLM ROUTER] Routing Attempt {attempt}: {provider_name} ({model_name}) | Budget: {budget['latency_budget_ms']}ms")
                t0 = time.monotonic()
                try:
                    res = await self._dispatch_call(provider_name, model_name, clean_prompt, budget["latency_budget_ms"])
                    ms = int((time.monotonic() - t0) * 1000)
                    
                    if res and isinstance(res, dict) and res.get("status") == "SUCCESS":
                        if cb: cb.record_success()
                        self._log_call(incident_id, model_name, clean_prompt, res.get("response", ""), ms, "SUCCESS", res.get("prompt_tokens",0), res.get("completion_tokens",0))
                        if cache_mgr:
                            cache_mgr.set_llm_cache(clean_prompt, res)
                        return res
                    else:
                        if cb: cb.record_failure()
                        err_msg = res.get('error') if (res and isinstance(res, dict)) else 'Unknown error or null response'
                        logger.warning(f"[LLM ROUTER] {provider_name} returned non-success: {err_msg}")
                except Exception as e:
                    if cb: cb.record_failure()
                    last_error = e
                    logger.warning(f"[LLM ROUTER] Provider {provider_name} execution failed: {e}")
                    
            delay = 1.0 * (2 ** (attempt - 1))
            logger.warning(f"[LLM ROUTER] All route plan providers failed on attempt {attempt}. Retrying in {delay}s...")
            await asyncio.sleep(delay)
            
        logger.warning(f"[LLM ROUTER] All LLM providers failed after {max_retries} attempts. Falling back to local Rule Engine.")
        return self.rule_engine_fallback(clean_prompt)
            
    def rule_engine_fallback(self, clean_prompt: str) -> Dict[str, Any]:
        """
        Fallback when all LLM APIs are offline / budget exhausted.
        Uses LocalDecisionTreeEngine (Random Forest / Decision Tree trained on 298+ historical incidents).
        """
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

    def route_incident(self, severity_score: int) -> str:
        budget = self.scorer.score(severity_score)
        if budget["preferred_tier"] == "critical":
            return "gemini-2.5-flash"
        return "gemini-3.1-flash-lite-preview"

    def generate(
        self,
        prompt: str,
        system_instruction: str = "",
        max_tokens: int = 1024,
        temperature: float = 0.3,
    ) -> Optional[str]:
        """Synchronous generation helper with multi-key Gemini + Groq failover."""
        full_prompt = f"{system_instruction}\n\n{prompt}".strip() if system_instruction else prompt
        if self.availability.get("gemini"):
            res = self._execute_gemini("gemini-3.1-flash-lite-preview", full_prompt)
            if res.get("status") == "SUCCESS" and res.get("response"):
                return str(res["response"]).strip()
        if self.availability.get("groq"):
            res = self.execute_groq(full_prompt, "llama-3.1-8b-instant")
            if res.get("status") == "SUCCESS" and res.get("response"):
                return str(res["response"]).strip()
        return None


def get_router() -> LLMRouter:
    global _ROUTER_SINGLETON
    if _ROUTER_SINGLETON is None:
        with _SHARED_INIT_LOCK:
            if _ROUTER_SINGLETON is None:
                _ROUTER_SINGLETON = LLMRouter()
    return _ROUTER_SINGLETON
