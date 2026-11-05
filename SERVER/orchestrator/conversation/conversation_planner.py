"""
SERVER.orchestrator.conversation.conversation_planner
======================================================
Component 4 of Pre-LLM Pipeline: Conversation Planner

Tugas:
  - Mengambil ContextAnalysisResult dari Context Analyzer.
  - Menentukan strategi percakapan (DialogueStrategy):
      * DIRECT_ANSWER
      * CLARIFICATION_REQUIRED
      * CHAIN_OF_THOUGHT
      * ACTION_EXECUTION
      * SUMMARIZATION_COMPACT
  - Memformulasi System Instructions yang telah di-optimize dan prompt akhir untuk LLMDispatcher.
"""
from enum import Enum
import logging
from dataclasses import dataclass, field
from typing import Dict, Any, Optional
from SERVER.orchestrator.context.context_analyzer import ContextAnalysisResult

logger = logging.getLogger("orchestrator.conversation.planner")


class DialogueStrategy(str, Enum):
    DIRECT_ANSWER = "DIRECT_ANSWER"
    CLARIFICATION_REQUIRED = "CLARIFICATION_REQUIRED"
    CHAIN_OF_THOUGHT = "CHAIN_OF_THOUGHT"
    ACTION_EXECUTION = "ACTION_EXECUTION"
    SUMMARIZATION_COMPACT = "SUMMARIZATION_COMPACT"


@dataclass
class ConversationPlan:
    """Hasil perencanaan strategi percakapan sebelum LLM Dispatcher dipanggil."""
    strategy: DialogueStrategy
    system_instructions: str
    optimized_prompt: str
    dispatch_metadata: Dict[str, Any] = field(default_factory=dict)
    should_bypass_llm: bool = False
    preset_response: Optional[str] = None


class ConversationPlanner:
    """
    Strategic Planner yang menentukan bagaimana prompt dan instruksi LLM harus disiapkan.
    """

    def plan(self, analysis: ContextAnalysisResult) -> ConversationPlan:
        """
        Membuat ConversationPlan berdasarkan ContextAnalysisResult.
        """
        payload = analysis.payload
        severity = analysis.severity_label

        # 1. Tentukan Strategi Utama
        strategy = DialogueStrategy.DIRECT_ANSWER

        # Kasus A: Token Overflow -> Compact Summarization
        if analysis.is_token_overflow:
            strategy = DialogueStrategy.SUMMARIZATION_COMPACT

        # Kasus B: Deteksi Intent Eksekusi Aksi NOC
        elif self._is_action_intent(payload.query_text):
            strategy = DialogueStrategy.ACTION_EXECUTION

        # Kasus C: Ambigu / Missing Entity -> Clarification Required
        elif analysis.has_ambiguity and severity not in ["critical", "high"]:
            strategy = DialogueStrategy.CLARIFICATION_REQUIRED

        # Kasus D: Severity Critical/High -> Chain of Thought RCA
        elif severity in ["critical", "high"]:
            strategy = DialogueStrategy.CHAIN_OF_THOUGHT

        # 2. Susun System Instructions dan Prompt Teroptimasi
        sys_instructions = self._build_system_instructions(strategy, payload.user_role, severity)
        optimized_prompt = self._build_optimized_prompt(strategy, analysis)

        # 3. Handle preset response jika CLARIFICATION_REQUIRED
        preset_resp = None
        should_bypass = False

        if strategy == DialogueStrategy.CLARIFICATION_REQUIRED and analysis.missing_entities:
            missing_str = ", ".join(analysis.missing_entities)
            preset_resp = (
                f"Mohon berikan informasi tambahan mengenai {missing_str} yang sedang diinvestigasi "
                "agar analisis diagnosa NOC dapat dilakukan secara presisi."
            )
            should_bypass = True

        plan_obj = ConversationPlan(
            strategy=strategy,
            system_instructions=sys_instructions,
            optimized_prompt=optimized_prompt,
            dispatch_metadata={
                "strategy": strategy.value,
                "severity_label": severity,
                "quality_score": analysis.quality_score,
                "token_budget_usage_pct": analysis.token_budget_usage_pct,
                "missing_entities": analysis.missing_entities,
            },
            should_bypass_llm=should_bypass,
            preset_response=preset_resp,
        )

        logger.debug(
            f"[ConversationPlanner] Planned strategy={strategy.value} | bypass={should_bypass} | severity={severity}"
        )
        return plan_obj

    def _is_action_intent(self, query: str) -> bool:
        action_keywords = ["restart", "reboot", "clear cache", "isolate", "block port", "failover", "scale"]
        query_lower = query.lower()
        return any(kw in query_lower for kw in action_keywords)

    def _build_system_instructions(self, strategy: DialogueStrategy, user_role: str, severity: str) -> str:
        base = (
            f"Anda adalah AI NOC & ITSM Specialist enterprise. Pengguna yang bertanya memiliki peran: {user_role}. "
            f"Tingkat keparahan insiden saat ini: {severity.upper()}.\n"
        )

        if strategy == DialogueStrategy.CHAIN_OF_THOUGHT:
            base += (
                "ATURAN REASONING (Chain-of-Thought):\n"
                "1. Analisis gejala awal (symptoms) & metrik telemetri secara berurutan.\n"
                "2. Identifikasi Akar Masalah (Root Cause Analysis - RCA).\n"
                "3. Berikan rekomendasi tindakan pemulihan (Mitigation Steps) konkret & bertahap.\n"
            )
        elif strategy == DialogueStrategy.SUMMARIZATION_COMPACT:
            base += (
                "ATURAN RINGKASAN RINGKAS:\n"
                "Jawab langsung pada inti masalah secara ringkas, padat, dan to-the-point tanpa pendahuluan panjang.\n"
            )
        elif strategy == DialogueStrategy.ACTION_EXECUTION:
            base += (
                "ATURAN EKSEKUSI OPERASIONAL:\n"
                "Identifikasi tindakan operasional yang diminta, verifikasi parameter prasyarat, dan cantumkan persetujuan HITL jika relevan.\n"
            )
        else:
            base += "Berikan jawaban komprehensif, tepat sasaran, dan profesional sesuai standar ITIL/NOC.\n"

        return base

    def _build_optimized_prompt(self, strategy: DialogueStrategy, analysis: ContextAnalysisResult) -> str:
        payload = analysis.payload
        sections = []

        # 1. Riwayat Percakapan
        if payload.formatted_history and strategy != DialogueStrategy.SUMMARIZATION_COMPACT:
            sections.append(payload.formatted_history)

        # 2. RAG Knowledge (gunakan deduplicated jika ada)
        if analysis.deduplicated_rag_chunks:
            formatted_rag_lines = ["--- DOKUMEN / KNOWLEDGE BASE (DEDUPLICATED RAG) ---"]
            for idx, chunk in enumerate(analysis.deduplicated_rag_chunks, 1):
                title = chunk.get("title") or chunk.get("source") or f"Doc-{idx}"
                content = chunk.get("content") or chunk.get("text") or str(chunk)
                formatted_rag_lines.append(f"[{idx}] {title}:\n{content}")
            sections.append("\n\n".join(formatted_rag_lines))
        elif payload.formatted_rag:
            sections.append(payload.formatted_rag)

        # 3. Telemetri & Metrik
        if payload.formatted_telemetry:
            sections.append(payload.formatted_telemetry)

        # 4. Prompt Utama User
        sections.append(f"--- QUERY USER ---\n{payload.query_text}")

        return "\n\n".join(sections)
