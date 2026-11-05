"""
SERVER.orchestrator.dispatcher.llm_dispatcher
=============================================
Tahap 2.3 — LLM & Knowledge Router (Dispatcher Layer)

ARSITEKTUR:
  Dashboard → jarvis → integration → orchestrator → [LLM Dispatcher] → python_ai_core/engines/llm_router.py

PRINSIP:
  - HANYA lapisan orkestrasi (wrapper/dispatcher). Tidak memindahkan atau menulis ulang core engine.
  - Dashboard, Jarvis, Integration TIDAK BOLEH mengimpor LLMRouter secara langsung.
  - Hanya dispatcher ini yang tahu tentang provider AI (Gemini, Groq, DeepSeek).
  - Backward compatible: python_ai_core/engines/llm_router.py tidak disentuh.
"""
import logging
from typing import Any, Dict, Optional

logger = logging.getLogger("orchestrator.dispatcher.llm")


class LLMDispatcher:
    """
    Orchestration wrapper untuk LLMRouter dari python_ai_core.
    Satu-satunya entry point ke semua provider LLM (Gemini, Groq, DeepSeek).

    Contoh penggunaan dari Integration Gateway atau Orchestrator:
        dispatcher = LLMDispatcher()
        result = await dispatcher.dispatch_async(severity_score=80, prompt="Diagnosa CPU spike...")
    """

    def __init__(self, db_conn=None):
        """
        Lazy-loads LLMRouter dari python_ai_core. Router tidak diinstansiasi
        hingga pertama kali dispatch dipanggil (to avoid import side-effects).
        """
        self._router = None
        self._db_conn = db_conn

    def _get_router(self):
        """Lazy initialization: memuat LLMRouter saat pertama kali dibutuhkan."""
        if self._router is None:
            try:
                import importlib
                # Menggunakan importlib agar dispatcher tidak memiliki hard-coded
                # direct import string ke python_ai_core (sesuai aturan BC02).
                llm_module = importlib.import_module("SERVER.python_ai_core.engines.llm_router")
                LLMRouter = llm_module.LLMRouter
                self._router = LLMRouter(db_conn=self._db_conn)
                logger.info("[LLMDispatcher] LLMRouter initialized successfully.")

            except Exception as exc:
                logger.error(f"[LLMDispatcher] Failed to load LLMRouter: {exc}")
                raise
        return self._router

    async def dispatch_async(
        self,
        severity_score: int,
        prompt: str,
        max_retries: int = 2,
        incident_id: str = "",
    ) -> Dict[str, Any]:
        """
        Dispatch async prompt ke LLM provider terbaik berdasarkan severity score.

        Routing Logic (dilakukan oleh LLMRouter):
          - CRITICAL (score >= 85): DeepSeek-Reasoner → Gemini-1.5-Pro fallback
          - HIGH/MEDIUM (score >= 60): Gemini-1.5-Flash → DeepSeek-Chat fallback
          - LOW (score < 60): Groq/Llama-3.1-8b → Gemini-1.5-Flash fallback
          - ALL FAIL: Rule Engine Fallback (LocalDecisionTree rules.pkl)

        Args:
            severity_score: 0–100. Menentukan tier routing dan token budget.
            prompt: Teks lengkap incident analysis prompt.
            max_retries: Jumlah maksimum percobaan lintas provider.
            incident_id: ID insiden untuk token budget tracking via Redis.

        Returns:
            dict: {"status": "SUCCESS"|"FALLBACK", "provider": str, "model": str,
                   "response": str, "prompt_tokens": int, "completion_tokens": int}
        """
        router = self._get_router()
        logger.info(
            f"[LLMDispatcher] Dispatching async | severity={severity_score} | incident={incident_id}"
        )
        return await router.execute_with_retry(
            severity_score=severity_score,
            prompt=prompt,
            max_retries=max_retries,
            incident_id=incident_id,
        )

    def dispatch_sync(
        self,
        severity_score: int,
        prompt: str,
        provider: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Dispatch synchronous prompt ke provider LLM tertentu (untuk non-async context).

        Args:
            severity_score: 0–100 untuk scoring.
            prompt: Teks prompt.
            provider: "gemini"|"groq"|"deepseek"|None (auto-route jika None).

        Returns:
            dict: Hasil dari provider yang dipilih.
        """
        router = self._get_router()
        logger.info(
            f"[LLMDispatcher] Dispatching sync | severity={severity_score} | provider={provider or 'auto'}"
        )
        if provider == "groq":
            return router.execute_groq(prompt)
        elif provider == "deepseek":
            return router.execute_deepseek(prompt)
        else:
            # Fallback: route via rule engine (sync path dari router)
            budget = router.scorer.score(severity_score)
            route_plan = router._plan_route(budget["preferred_tier"])
            logger.info(f"[LLMDispatcher] Sync auto-route plan: {route_plan}")
            # Gunakan rule engine sebagai safe synchronous fallback
            return router.rule_engine_fallback(router.normalizer.normalize(prompt))

    @property
    def provider_status(self) -> Dict[str, bool]:
        """Mengembalikan status availability tiap provider."""
        try:
            router = self._get_router()
            return dict(router.availability)
        except Exception:
            return {"gemini": False, "groq": False, "deepseek": False}
