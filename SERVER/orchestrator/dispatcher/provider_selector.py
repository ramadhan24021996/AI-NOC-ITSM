"""
SERVER.orchestrator.dispatcher.provider_selector
================================================
Tahap 2.3 — LLM & Knowledge Router (Dispatcher Layer)

KOMPONEN:
  ProviderSelector — menentukan provider dan model optimal berdasarkan:
    1. Severity Score (tier: critical / medium / low)
    2. Ketersediaan provider (availability check via LLMDispatcher)
    3. Latency budget & token budget

PRINSIP:
  - Komponen routing policy murni. Tidak memanggil provider secara langsung.
  - Bisa diuji secara unit tanpa koneksi jaringan sama sekali.
  - Backward compatible: mengambil routing logic dari LLMRouter tanpa mengubahnya.
"""
import logging
from typing import Any, Dict, List, Optional
from enum import Enum

logger = logging.getLogger("orchestrator.dispatcher.provider_selector")


class ProviderTier(str, Enum):
    CRITICAL = "critical"
    MEDIUM = "medium"
    LOW = "low"


class SelectedProvider:
    """Hasil pemilihan provider oleh ProviderSelector."""

    def __init__(
        self,
        provider: str,
        model: str,
        tier: ProviderTier,
        latency_budget_ms: int,
        token_budget: int,
        fallback_chain: List[Dict[str, str]],
    ):
        self.provider = provider
        self.model = model
        self.tier = tier
        self.latency_budget_ms = latency_budget_ms
        self.token_budget = token_budget
        self.fallback_chain = fallback_chain

    def to_dict(self) -> Dict[str, Any]:
        return {
            "provider": self.provider,
            "model": self.model,
            "tier": self.tier.value,
            "latency_budget_ms": self.latency_budget_ms,
            "token_budget": self.token_budget,
            "fallback_chain": self.fallback_chain,
        }


# ── Routing Table ─────────────────────────────────────────────────────────────
#
# Tabel ini HARUS KONSISTEN dengan _plan_route() di LLMRouter.
# Jika routing policy berubah, cukup ubah satu tempat: tabel ini atau LLMRouter.
# Tabel ini digunakan untuk pengambilan keputusan statis (tanpa memanggil LLM).
#
ROUTING_TABLE: Dict[str, Dict[str, Any]] = {
    ProviderTier.CRITICAL: {
        "primary": {"provider": "deepseek", "model": "deepseek-reasoner"},
        "fallback": [
            {"provider": "gemini", "model": "gemini-1.5-pro"},
        ],
        "latency_budget_ms": 15000,
        "token_budget": 128000,
    },
    ProviderTier.MEDIUM: {
        "primary": {"provider": "gemini", "model": "gemini-1.5-flash"},
        "fallback": [
            {"provider": "deepseek", "model": "deepseek-chat"},
        ],
        "latency_budget_ms": 10000,
        "token_budget": 32000,
    },
    ProviderTier.LOW: {
        "primary": {"provider": "groq", "model": "llama-3.1-8b-instant"},
        "fallback": [
            {"provider": "gemini", "model": "gemini-1.5-flash"},
        ],
        "latency_budget_ms": 5000,
        "token_budget": 8000,
    },
}


class ProviderSelector:
    """
    Menentukan provider dan model terbaik berdasarkan severity score dan
    ketersediaan provider saat ini.

    Contoh penggunaan (tanpa memanggil LLM):
        selector = ProviderSelector()
        result = selector.select(severity_score=85, available_providers=["gemini", "groq"])
        print(result.to_dict())
        # {"provider": "gemini", "model": "gemini-1.5-pro", "tier": "critical", ...}
    """

    @staticmethod
    def score_to_tier(severity_score: int) -> ProviderTier:
        """Konversi severity score 0–100 ke tier routing."""
        if severity_score >= 85:
            return ProviderTier.CRITICAL
        elif severity_score >= 60:
            return ProviderTier.MEDIUM
        else:
            return ProviderTier.LOW

    def select(
        self,
        severity_score: int,
        available_providers: Optional[List[str]] = None,
    ) -> SelectedProvider:
        """
        Memilih provider optimal. Jika primary provider tidak tersedia,
        otomatis memilih dari fallback chain.

        Args:
            severity_score: 0–100. Menentukan tier routing.
            available_providers: List provider yang tersedia saat ini
                                 (e.g., ["gemini", "groq"]).
                                 Jika None, semua dianggap tersedia.

        Returns:
            SelectedProvider: Provider dan model yang dipilih beserta budget-nya.
        """
        tier = self.score_to_tier(severity_score)
        table_entry = ROUTING_TABLE[tier]

        primary = table_entry["primary"]
        fallback_chain = table_entry["fallback"]
        latency_budget = table_entry["latency_budget_ms"]
        token_budget = table_entry["token_budget"]

        # Tentukan provider yang benar-benar tersedia
        all_candidates = [primary] + fallback_chain
        chosen = None

        if available_providers is None:
            # Anggap semua tersedia → pilih primary
            chosen = primary
        else:
            for candidate in all_candidates:
                if candidate["provider"] in available_providers:
                    chosen = candidate
                    break

        if chosen is None:
            # Semua provider tidak tersedia → rule engine fallback
            logger.warning(
                f"[ProviderSelector] No available provider for tier={tier.value}. "
                f"Falling back to offline rule engine."
            )
            chosen = {"provider": "rule_engine", "model": "offline-rule-engine"}

        logger.info(
            f"[ProviderSelector] Selected: {chosen['provider']}/{chosen['model']} "
            f"| tier={tier.value} | severity={severity_score}"
        )

        return SelectedProvider(
            provider=chosen["provider"],
            model=chosen["model"],
            tier=tier,
            latency_budget_ms=latency_budget,
            token_budget=token_budget,
            fallback_chain=fallback_chain,
        )

    def describe_routing_table(self) -> Dict[str, Any]:
        """Kembalikan routing table lengkap untuk inspeksi / audit."""
        return {
            tier.value: {
                "primary": ROUTING_TABLE[tier]["primary"],
                "fallback_chain": ROUTING_TABLE[tier]["fallback"],
                "latency_budget_ms": ROUTING_TABLE[tier]["latency_budget_ms"],
                "token_budget": ROUTING_TABLE[tier]["token_budget"],
            }
            for tier in ProviderTier
        }
