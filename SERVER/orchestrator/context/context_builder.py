"""
SERVER.orchestrator.context.context_builder
============================================
Component 2 of Pre-LLM Pipeline: Context Builder

Tugas:
  - Menggabungkan data heterogen (query, history, RAG chunks, telemetry, user role)
    menjadi struktur tunggal StructuredContextPayload.
  - Memformat tiap bagian secara konsisten untuk dikonsumsi Context Analyzer & Conversation Planner.
"""
import logging
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional

logger = logging.getLogger("orchestrator.context.builder")


@dataclass
class StructuredContextPayload:
    """Standardized context container yang siap di-analisis dan dikirim ke planner."""
    query_text: str
    conversation_history: List[Dict[str, Any]] = field(default_factory=list)
    rag_chunks: List[Dict[str, Any]] = field(default_factory=list)
    telemetry_context: Dict[str, Any] = field(default_factory=dict)
    user_role: str = "NOC Engineer"
    site_location: str = ""
    # Formatted sections
    formatted_history: str = ""
    formatted_rag: str = ""
    formatted_telemetry: str = ""
    estimated_token_count: int = 0


class ContextBuilder:
    """
    Context Aggregator yang menggabungkan multi-source operational data
    menjadi StructuredContextPayload.
    """

    def __init__(self, avg_chars_per_token: float = 4.0):
        self.avg_chars_per_token = avg_chars_per_token

    def build(
        self,
        query_text: str,
        conversation_history: Optional[List[Dict[str, Any]]] = None,
        rag_chunks: Optional[List[Dict[str, Any]]] = None,
        telemetry_context: Optional[Dict[str, Any]] = None,
        user_role: str = "NOC Engineer",
        site_location: str = "",
    ) -> StructuredContextPayload:
        """
        Membangun dan memformat StructuredContextPayload dari parameter input.
        """
        history = conversation_history or []
        chunks = rag_chunks or []
        telemetry = telemetry_context or {}

        formatted_hist = self._format_history(history)
        formatted_rag = self._format_rag(chunks)
        formatted_telem = self._format_telemetry(telemetry)

        # Estimasi total token dari seluruh komponen
        raw_text = (
            query_text
            + formatted_hist
            + formatted_rag
            + formatted_telem
            + user_role
            + site_location
        )
        est_tokens = int(len(raw_text) / self.avg_chars_per_token)

        payload = StructuredContextPayload(
            query_text=query_text,
            conversation_history=history,
            rag_chunks=chunks,
            telemetry_context=telemetry,
            user_role=user_role,
            site_location=site_location,
            formatted_history=formatted_hist,
            formatted_rag=formatted_rag,
            formatted_telemetry=formatted_telem,
            estimated_token_count=est_tokens,
        )

        logger.debug(
            f"[ContextBuilder] Built payload | est_tokens={est_tokens} | RAG chunks={len(chunks)} | History turns={len(history)}"
        )
        return payload

    def _format_history(self, history: List[Dict[str, Any]]) -> str:
        if not history:
            return ""
        lines = ["--- RIWAYAT PERCAKAPAN ---"]
        for turn in history:
            role = "User" if turn.get("role") == "user" else "Assistant"
            lines.append(f"[{role}]: {turn.get('content', '')}")
        return "\n".join(lines)

    def _format_rag(self, chunks: List[Dict[str, Any]]) -> str:
        if not chunks:
            return ""
        lines = ["--- DOKUMEN / KNOWLEDGE BASE (RAG) ---"]
        for idx, chunk in enumerate(chunks, 1):
            title = chunk.get("title") or chunk.get("source") or f"Doc-{idx}"
            content = chunk.get("content") or chunk.get("text") or str(chunk)
            score = chunk.get("score") or chunk.get("relevance", 1.0)
            lines.append(f"[{idx}] {title} (relevance={score}):\n{content}")
        return "\n\n".join(lines)

    def _format_telemetry(self, telemetry: Dict[str, Any]) -> str:
        if not telemetry:
            return ""
        lines = ["--- METRIK & TELEMETRI NOC ---"]
        for k, v in telemetry.items():
            lines.append(f"- {k}: {v}")
        return "\n".join(lines)
