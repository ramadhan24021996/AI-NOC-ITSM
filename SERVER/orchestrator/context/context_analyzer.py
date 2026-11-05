"""
SERVER.orchestrator.context.context_analyzer
=============================================
Component 3 of Pre-LLM Pipeline: Context Analyzer

Tugas:
  - Mengevaluasi StructuredContextPayload dari Context Builder.
  - Memeriksa budget token & deteksi token overflow.
  - Melakukan deduplikasi RAG chunks dan riwayat berulang (Redundancy Pruning).
  - Mendeteksi entitas penting yang hilang (Missing Entity / Ambiguity Check).
  - Menyediakan ContextAnalysisResult untuk dikonsumsi Conversation Planner.
"""
import re
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Set, Optional, Tuple
from SERVER.orchestrator.context.context_builder import StructuredContextPayload

logger = logging.getLogger("orchestrator.context.analyzer")

# Default token budget per severity tier
DEFAULT_TOKEN_BUDGETS = {
    "critical": 8000,
    "high": 4000,
    "medium": 2000,
    "low": 1000,
}

# Entitas NOC kritis yang disimak jika user menanyakan insiden/diagnosa
CRITICAL_NOC_ENTITIES = ["ip", "host", "hostname", "service", "node", "interface", "port", "cluster"]


@dataclass
class ContextAnalysisResult:
    """Hasil analisis kontekstual sebelum dikirim ke Conversation Planner."""
    payload: StructuredContextPayload
    severity_label: str
    token_budget: int
    estimated_tokens: int
    token_budget_usage_pct: float
    is_token_overflow: bool
    deduplicated_rag_chunks: List[Dict[str, Any]] = field(default_factory=list)
    missing_entities: List[str] = field(default_factory=list)
    has_ambiguity: bool = False
    rag_relevance_score: float = 1.0
    quality_score: float = 1.0  # 0.0 - 1.0 context health score


class ContextAnalyzer:
    """
    Diagnostic Analyzer untuk mengevaluasi kesehatan dan efisiensi konteks.
    """

    def __init__(self, token_budgets: Optional[Dict[str, int]] = None):
        self.token_budgets = token_budgets or DEFAULT_TOKEN_BUDGETS

    def analyze(
        self,
        payload: StructuredContextPayload,
        severity_label: str = "medium",
    ) -> ContextAnalysisResult:
        """
        Menganalisis payload konteks dan mengembalikan ContextAnalysisResult.
        """
        severity_key = (severity_label or "medium").lower()
        budget = self.token_budgets.get(severity_key, 2000)

        est_tokens = payload.estimated_token_count
        usage_pct = (est_tokens / budget) * 100.0 if budget > 0 else 0.0
        is_overflow = est_tokens > budget

        # 1. Deduplikasi RAG Chunks
        dedup_rag = self._deduplicate_rag_chunks(payload.rag_chunks)

        # 2. Hitung RAG Relevance Score
        avg_relevance = self._calculate_rag_relevance(dedup_rag)

        # 3. Deteksi missing NOC Entities
        missing_ents, is_ambiguous = self._detect_missing_entities(payload)

        # 4. Hitung overall Quality Score
        quality = 1.0
        if is_overflow:
            quality -= 0.2
        if is_ambiguous:
            quality -= 0.3
        if avg_relevance < 0.5 and dedup_rag:
            quality -= 0.2
        quality = max(0.1, min(1.0, quality))

        result = ContextAnalysisResult(
            payload=payload,
            severity_label=severity_key,
            token_budget=budget,
            estimated_tokens=est_tokens,
            token_budget_usage_pct=usage_pct,
            is_token_overflow=is_overflow,
            deduplicated_rag_chunks=dedup_rag,
            missing_entities=missing_ents,
            has_ambiguity=is_ambiguous,
            rag_relevance_score=avg_relevance,
            quality_score=quality,
        )

        logger.debug(
            f"[ContextAnalyzer] Analyzed conv context | quality={quality:.2f} | overflow={is_overflow} | ambiguous={is_ambiguous}"
        )
        return result

    def _deduplicate_rag_chunks(
        self, chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """Menghapus chunk RAG yang duplikat atau sangat mirip berdasarkan teks."""
        seen_hashes: Set[int] = set()
        unique_chunks: List[Dict[str, Any]] = []

        for chunk in chunks:
            text = (chunk.get("content") or chunk.get("text") or str(chunk)).strip()
            # Normalisasi whitespace untuk deduplikasi hash
            normalized = re.sub(r"\s+", " ", text.lower())
            text_hash = hash(normalized)

            if text_hash not in seen_hashes:
                seen_hashes.add(text_hash)
                unique_chunks.append(chunk)

        return unique_chunks

    def _calculate_rag_relevance(self, chunks: List[Dict[str, Any]]) -> float:
        if not chunks:
            return 1.0
        scores: List[float] = []
        for c in chunks:
            raw_score = c.get("score") if c.get("score") is not None else c.get("relevance", 1.0)
            try:
                scores.append(float(raw_score) if raw_score is not None else 1.0)
            except (ValueError, TypeError):
                scores.append(1.0)
        return sum(scores) / len(scores)

    def _detect_missing_entities(
        self, payload: StructuredContextPayload
    ) -> Tuple[List[str], bool]:
        """
        Deteksi apakah query insiden tampak ambigu karena kekurangan entitas NOC spesifik
        (seperti IP, Hostname, atau Service Name) baik di query maupun di telemetry.
        """
        text_to_check = (
            payload.query_text.lower()
            + " "
            + str(payload.telemetry_context).lower()
        )

        # Cek apakah query berupa diagnosa / analisis insiden
        diagnostic_keywords = ["diagnosa", "troubleshoot", "investigasi", "kenapa", "solusi", "down", "error", "spike"]
        is_diagnostic_query = any(kw in payload.query_text.lower() for kw in diagnostic_keywords)

        if not is_diagnostic_query:
            return [], False

        # Cek ketersediaan entitas
        has_entity = any(ent in text_to_check for ent in CRITICAL_NOC_ENTITIES)
        # Juga cek regex IP address sederhana
        has_ip = bool(re.search(r"\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}\b", text_to_check))

        missing = []
        if not (has_entity or has_ip):
            missing.append("Target Node/IP/Service Name")

        has_ambiguity = len(missing) > 0
        return missing, has_ambiguity
