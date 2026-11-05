"""
SERVER.orchestrator.coordinator — NOC Execution Coordinator
============================================================
Tahap 2.5 — Dashboard AI NOC Wiring & Pre-LLM Cognitive Pipeline

Implementasi konkret dari ExecutionCoordinator.
Menjadi PUSAT WORKFLOW dengan alur Pre-LLM Pipeline:
  1. Receive Request (IncidentQueryContract)
  2. Publish Event: STARTED (EventBus sebagai observer)
  3. Track Selection (severity → ExecutionTrack)
  4. Retrieve Knowledge (RAGDispatcher)
  5. Conversation Manager: Ambil riwayat percakapan multi-turn
  6. Context Builder: Gabungkan query + history + RAG + telemetry
  7. Context Analyzer: Evaluasi token budget, deduplikasi RAG, deteksi missing NOC entity
  8. Conversation Planner: Tentukan strategi (Direct, Clarification, CoT, Action)
  9. Invoke LLM (LLMDispatcher) atau tangani preset response
  10. Record turn ke Conversation Manager
  11. Publish Event: COMPLETED (EventBus)
  12. Return DTO (IncidentResponseContract)
"""
import logging
import time
import uuid
from typing import Optional, Dict, Any, List

from SERVER.contracts.schemas import IncidentQueryContract, IncidentResponseContract
from SERVER.shared.enums import ExecutionTrack
from SERVER.orchestrator.coordinator.execution_coordinator import ExecutionCoordinator
from SERVER.orchestrator.conversation.conversation_manager import ConversationManager
from SERVER.orchestrator.context.context_builder import ContextBuilder
from SERVER.orchestrator.context.context_analyzer import ContextAnalyzer
from SERVER.orchestrator.conversation.conversation_planner import ConversationPlanner, ConversationPlan

logger = logging.getLogger("orchestrator.coordinator.noc")


# ── Severity → ExecutionTrack Mapping ─────────────────────────────────────────
_SEVERITY_TRACK_MAP = {
    "critical": ExecutionTrack.CRITICAL_TRACK,
    "high":     ExecutionTrack.CRITICAL_TRACK,
    "medium":   ExecutionTrack.STANDARD_TRACK,
    "low":      ExecutionTrack.FAST_TRACK,
    "":         ExecutionTrack.STANDARD_TRACK,
}


class NOCExecutionCoordinator(ExecutionCoordinator):
    """
    Implementasi konkret ExecutionCoordinator untuk AI NOC Platform.
    Menerima IncidentQueryContract, mengorkestrasikan Pre-LLM Cognitive Pipeline:
    ConversationManager → ContextBuilder → ContextAnalyzer → ConversationPlanner → LLMDispatcher
    """

    def __init__(
        self,
        llm_dispatcher=None,
        rag_dispatcher=None,
        tool_dispatcher=None,
        event_bus=None,
        conversation_manager: Optional[ConversationManager] = None,
        context_builder: Optional[ContextBuilder] = None,
        context_analyzer: Optional[ContextAnalyzer] = None,
        conversation_planner: Optional[ConversationPlanner] = None,
    ):
        """
        Dependency injection untuk dispatcher dan pre-LLM cognitive pipeline.
        Jika pre-LLM pipeline tidak diinject, komponen default di-instansiasi secara otomatis.
        """
        self._llm = llm_dispatcher
        self._rag = rag_dispatcher
        self._tool = tool_dispatcher
        self._event_bus = event_bus

        # Pre-LLM Cognitive Pipeline Components
        self._conv_manager = conversation_manager or ConversationManager()
        self._context_builder = context_builder or ContextBuilder()
        self._context_analyzer = context_analyzer or ContextAnalyzer()
        self._conv_planner = conversation_planner or ConversationPlanner()

    @classmethod
    def from_container(cls, container) -> "NOCExecutionCoordinator":
        """
        Factory method: membangun koordinator dari DIContainer.
        """
        from SERVER.orchestrator.dispatcher.llm_dispatcher import LLMDispatcher
        from SERVER.orchestrator.dispatcher.rag_dispatcher import RAGDispatcher
        from SERVER.tools.dispatcher.tool_dispatcher import ToolDispatcher
        from SERVER.ai_kernel.message_bus.event_bus_interface import EventBusInterface

        def _safe_resolve(t):
            try:
                return container.resolve(t)
            except (KeyError, Exception):
                return None

        return cls(
            llm_dispatcher=_safe_resolve(LLMDispatcher),
            rag_dispatcher=_safe_resolve(RAGDispatcher),
            tool_dispatcher=_safe_resolve(ToolDispatcher),
            event_bus=_safe_resolve(EventBusInterface),
            conversation_manager=_safe_resolve(ConversationManager),
            context_builder=_safe_resolve(ContextBuilder),
            context_analyzer=_safe_resolve(ContextAnalyzer),
            conversation_planner=_safe_resolve(ConversationPlanner),
        )

    # ── Synchronous API ────────────────────────────────────────────────────────

    def coordinate_execution(
        self, query_contract: IncidentQueryContract
    ) -> IncidentResponseContract:
        return self.execute(query_contract)

    def execute(self, query_contract: IncidentQueryContract) -> IncidentResponseContract:
        """
        Synchronous execution pipeline dengan Pre-LLM Cognitive Processing.
        """
        t0 = time.monotonic()
        query_contract = self._ensure_correlation_ids(query_contract)

        logger.info(
            f"[NOCCoordinator] STARTED | query_id={query_contract.query_id} | "
            f"trace_id={query_contract.trace_id} | conv_id={query_contract.conversation_id or query_contract.session_id}"
        )

        self._publish_event("noc.incident.analysis.started", query_contract)

        # 1. Track Selection
        track = self._select_track(query_contract)

        # 2. Retrieve Knowledge (sync)
        rag_context = self._retrieve_knowledge_sync(query_contract)
        rag_chunks = rag_context.get("results", []) or []

        # 3. Pre-LLM Cognitive Pipeline
        conv_id = query_contract.conversation_id or query_contract.session_id or query_contract.query_id
        plan = self._run_pre_llm_pipeline(query_contract, conv_id, rag_chunks)

        # 4. Invoke LLM or use Preset Response
        if plan.should_bypass_llm and plan.preset_response:
            answer_text = plan.preset_response
            llm_result = {"response": answer_text, "completion_tokens": 10}
            logger.info(f"[NOCCoordinator] Bypassed LLM | strategy={plan.strategy.value}")
        else:
            final_prompt = f"{plan.system_instructions}\n\n{plan.optimized_prompt}"
            llm_result = self._invoke_llm_sync(query_contract, final_prompt)
            answer_text = llm_result.get("response", "Analysis unavailable.")

        # 5. Record Turn ke Conversation Manager
        self._record_conversation_turns(conv_id, query_contract.query_text, answer_text, query_contract.trace_id, plan)

        # 6. Build response
        processing_ms = int((time.monotonic() - t0) * 1000)
        response = IncidentResponseContract(
            query_id=query_contract.query_id,
            execution_track=track,
            answer_text=answer_text,
            evidence_score=self._calculate_evidence_score(llm_result),
            requires_hitl=(track == ExecutionTrack.CRITICAL_TRACK),
            request_id=query_contract.request_id,
            trace_id=query_contract.trace_id,
            processing_ms=processing_ms,
        )

        self._publish_event("noc.incident.analysis.completed", query_contract, response)

        logger.info(
            f"[NOCCoordinator] COMPLETED | query_id={query_contract.query_id} | "
            f"track={track.value} | strategy={plan.strategy.value} | ms={processing_ms}"
        )
        return response

    # ── Asynchronous API ───────────────────────────────────────────────────────

    async def execute_async(
        self, query_contract: IncidentQueryContract
    ) -> IncidentResponseContract:
        """
        Asynchronous execution pipeline dengan Pre-LLM Cognitive Processing.
        """
        t0 = time.monotonic()
        query_contract = self._ensure_correlation_ids(query_contract)

        logger.info(
            f"[NOCCoordinator] ASYNC STARTED | query_id={query_contract.query_id} | "
            f"trace_id={query_contract.trace_id}"
        )

        self._publish_event("noc.incident.analysis.started", query_contract)

        # 1. Track Selection
        track = self._select_track(query_contract)

        # 2. Retrieve Knowledge (async)
        rag_context = await self._retrieve_knowledge_async(query_contract)
        rag_chunks = rag_context.get("results", []) or []

        # 3. Pre-LLM Cognitive Pipeline
        conv_id = query_contract.conversation_id or query_contract.session_id or query_contract.query_id
        plan = self._run_pre_llm_pipeline(query_contract, conv_id, rag_chunks)

        # 4. Invoke LLM or use Preset Response
        if plan.should_bypass_llm and plan.preset_response:
            answer_text = plan.preset_response
            llm_result = {"response": answer_text, "completion_tokens": 10}
            logger.info(f"[NOCCoordinator] ASYNC Bypassed LLM | strategy={plan.strategy.value}")
        else:
            final_prompt = f"{plan.system_instructions}\n\n{plan.optimized_prompt}"
            severity_score = self._severity_to_score(query_contract)
            llm_result = {}
            if self._llm:
                try:
                    llm_result = await self._llm.dispatch_async(
                        severity_score=severity_score,
                        prompt=final_prompt,
                        incident_id=query_contract.query_id,
                    )
                except Exception as exc:
                    logger.warning(f"[NOCCoordinator] LLM async failed: {exc} — using fallback")
            answer_text = llm_result.get("response", "Analysis unavailable.")

        # 5. Record Turn ke Conversation Manager
        self._record_conversation_turns(conv_id, query_contract.query_text, answer_text, query_contract.trace_id, plan)

        # 6. Build response
        processing_ms = int((time.monotonic() - t0) * 1000)
        response = IncidentResponseContract(
            query_id=query_contract.query_id,
            execution_track=track,
            answer_text=answer_text,
            evidence_score=self._calculate_evidence_score(llm_result),
            requires_hitl=(track == ExecutionTrack.CRITICAL_TRACK),
            request_id=query_contract.request_id,
            trace_id=query_contract.trace_id,
            processing_ms=processing_ms,
        )

        self._publish_event("noc.incident.analysis.completed", query_contract, response)

        logger.info(
            f"[NOCCoordinator] ASYNC COMPLETED | query_id={query_contract.query_id} | ms={processing_ms}"
        )
        return response

    # ── Pre-LLM Cognitive Pipeline Helper ────────────────────────────────────

    def _run_pre_llm_pipeline(
        self,
        contract: IncidentQueryContract,
        conv_id: str,
        rag_chunks: List[Dict[str, Any]],
    ) -> ConversationPlan:
        """
        Menjalankan 4 komponen Pre-LLM Pipeline:
        1. ConversationManager -> Ambil riwayat percakapan
        2. ContextBuilder -> Rakit payload konteks
        3. ContextAnalyzer -> Evaluasi kesehatan & budget konteks
        4. ConversationPlanner -> Formulasi strategi & prompt
        """
        # Step 1: Conversation History
        history = self._conv_manager.get_history(conv_id)

        # Step 2: Context Builder
        payload = self._context_builder.build(
            query_text=contract.query_text,
            conversation_history=history,
            rag_chunks=rag_chunks,
            telemetry_context=contract.telemetry_context,
            user_role=contract.user_role,
            site_location=contract.site_location or "",
        )

        # Step 3: Context Analyzer
        severity = str(contract.telemetry_context.get("severity", "medium")).lower()
        analysis_result = self._context_analyzer.analyze(
            payload=payload,
            severity_label=severity,
        )

        # Step 4: Conversation Planner
        plan = self._conv_planner.plan(analysis_result)
        return plan

    def _record_conversation_turns(
        self,
        conv_id: str,
        query_text: str,
        answer_text: str,
        trace_id: str,
        plan: ConversationPlan,
    ) -> None:
        """Simpan turn user dan assistant ke Conversation Manager."""
        try:
            self._conv_manager.add_turn(
                conversation_id=conv_id,
                role="user",
                content=query_text,
                trace_id=trace_id,
            )
            self._conv_manager.add_turn(
                conversation_id=conv_id,
                role="assistant",
                content=answer_text,
                trace_id=trace_id,
                metadata=plan.dispatch_metadata,
            )
        except Exception as exc:
            logger.warning(f"[NOCCoordinator] Failed recording conv turns: {exc}")

    # ── Internal Helpers ───────────────────────────────────────────────────────

    def _ensure_correlation_ids(
        self, contract: IncidentQueryContract
    ) -> IncidentQueryContract:
        if not contract.request_id:
            contract.request_id = f"REQ-{uuid.uuid4().hex[:8].upper()}"
        if not contract.trace_id:
            contract.trace_id = f"TRC-{uuid.uuid4().hex[:12].upper()}"
        return contract

    def _select_track(self, contract: IncidentQueryContract) -> ExecutionTrack:
        severity = str(
            contract.telemetry_context.get("severity", "") or ""
        ).lower()
        track = _SEVERITY_TRACK_MAP.get(severity, ExecutionTrack.STANDARD_TRACK)
        logger.debug(f"[NOCCoordinator] Track: {track.value} (severity={severity})")
        return track

    def _retrieve_knowledge_sync(self, contract: IncidentQueryContract) -> Dict[str, Any]:
        if not self._rag:
            return {}
        try:
            return self._rag.retrieve_sync(contract.query_text, limit=3)
        except Exception as exc:
            logger.warning(f"[NOCCoordinator] RAG sync failed: {exc} — continuing without context")
            return {}

    async def _retrieve_knowledge_async(self, contract: IncidentQueryContract) -> Dict[str, Any]:
        if not self._rag:
            return {}
        try:
            return await self._rag.retrieve_async(contract.query_text, limit=3)
        except Exception as exc:
            logger.warning(f"[NOCCoordinator] RAG async failed: {exc} — continuing without context")
            return {}

    def _invoke_llm_sync(
        self, contract: IncidentQueryContract, prompt: str
    ) -> Dict[str, Any]:
        if not self._llm:
            return {"response": "[No LLM configured] " + contract.query_text, "completion_tokens": 0}
        try:
            severity_score = self._severity_to_score(contract)
            return self._llm.dispatch_sync(severity_score=severity_score, prompt=prompt)
        except Exception as exc:
            logger.warning(f"[NOCCoordinator] LLM sync failed: {exc} — using fallback response")
            return {"response": f"Fallback analysis: {contract.query_text}", "completion_tokens": 0}

    @staticmethod
    def _calculate_evidence_score(llm_result: Dict[str, Any]) -> float:
        raw_tokens = llm_result.get("completion_tokens", 0)
        try:
            tokens_val = float(raw_tokens) if raw_tokens is not None else 0.0
        except (ValueError, TypeError):
            tokens_val = 0.0
        return min(1.0, (tokens_val / 500.0) + 0.5)

    @staticmethod
    def _severity_to_score(contract: IncidentQueryContract) -> int:
        severity = str(
            contract.telemetry_context.get("severity", "") or ""
        ).lower()
        mapping = {"critical": 90, "high": 75, "medium": 55, "low": 25}
        return mapping.get(severity, 50)

    def _publish_event(
        self,
        event_type: str,
        contract: IncidentQueryContract,
        response: Optional[IncidentResponseContract] = None,
    ) -> None:
        if not self._event_bus:
            return
        payload: Dict[str, Any] = {
            "event_type": event_type,
            "query_id": contract.query_id,
            "trace_id": contract.trace_id,
            "request_id": contract.request_id,
        }
        if response:
            payload["processing_ms"] = response.processing_ms
            payload["track"] = response.execution_track.value
        try:
            self._event_bus.publish(event_type, payload)
        except Exception as exc:
            logger.warning(f"[NOCCoordinator] Event publish failed (non-fatal): {exc}")
