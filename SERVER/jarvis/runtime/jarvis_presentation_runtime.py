"""
SERVER.jarvis.runtime - Jarvis Presentation Runtime (v2.0)
==========================================================
End-to-end presentation runtime: STT → Intent Router → NOC Bridge → Safety Gate
→ Response DTO → Persona Acknowledgment → TTS.

STRICTLY COMPLIANT WITH ADR-005: Zero direct DB/Repository imports in this domain.
All requests pass strictly through Integration Gateway or JarvisNOCBridge.
"""
import logging
import time
from typing import Any, Dict, Optional

from SERVER.contracts.schemas import (
    IncidentQueryContract, IncidentResponseContract, StructuredActionContext
)
from SERVER.integration.gateway.unified_gateway import UnifiedGateway
from SERVER.jarvis.audit.command_audit import JarvisCommandAudit
from SERVER.jarvis.avatar.avatar_state_manager import AvatarStateManager, AvatarState
from SERVER.jarvis.cognition.knowledge_graph_bridge import (
    JarvisBusinessImpactBridge, JarvisKnowledgeGraphBridge
)
from SERVER.jarvis.cognition.nlu_bridge import JarvisNLUBridge, JarvisOpeningBridge
from SERVER.jarvis.cognition.phonetic_corrector import JarvisPhoneticCorrector
from SERVER.jarvis.command.intent_router import JarvisCommandIntentRouter, JarvisIntent
from SERVER.jarvis.command.noc_keywords_id import NOCKeywordsID
from SERVER.jarvis.conversation.conversation_manager import ConversationManager
from SERVER.jarvis.diagnostics.deep_diagnostics_adapter import (
    JarvisBrowserMonitorBridge, JarvisDeepDiagnosticsAdapter
)
from SERVER.jarvis.hitl.hitl_feedback import HITLDecision, JarvisHITLFeedback
from SERVER.jarvis.interfaces.presentation_dtos import (
    ConversationContextDTO, VoiceAudioPayloadDTO, VoiceLatencyBreakdownDTO
)
from SERVER.jarvis.knowledge.knowledge_learning_bridge import JarvisKnowledgeLearningBridge
from SERVER.jarvis.noc.noc_bridge import JarvisNOCBridge
from SERVER.jarvis.personas.persona_registry import PersonaRegistry
from SERVER.jarvis.planning.action_catalog_validator import JarvisActionCatalogValidator
from SERVER.jarvis.prompt.prompt_template_manager import PresentationPromptManager
from SERVER.jarvis.remote.browser_control_bridge import JarvisBrowserControlBridge
from SERVER.jarvis.session.multi_turn_session_memory import get_multi_turn_memory_manager_v31
from SERVER.jarvis.remote.remote_session_manager import JarvisRemoteSessionManager
from SERVER.jarvis.runtime.intent_action_handler import IntentActionHandlerMixin
from SERVER.jarvis.runtime.intent_chat_handler import IntentChatHandlerMixin
from SERVER.jarvis.runtime.intent_query_handler import IntentQueryHandlerMixin
from SERVER.jarvis.runtime.startup_reporter import JarvisStartupReporter
from SERVER.jarvis.sessions.session_manager import SessionManager
from SERVER.jarvis.voice.stt_service import STTService
from SERVER.jarvis.voice.tts_service import TTSService
from SERVER.jarvis.voice.wake_word_detector import WakeWordDetector
from SERVER.shared.enums import ExecutionTrack

logger = logging.getLogger("jarvis.runtime")


class JarvisPresentationRuntime(
    IntentQueryHandlerMixin,
    IntentActionHandlerMixin,
    IntentChatHandlerMixin,
):
    """
    Jarvis Presentation Runtime Orchestrator v2.0.
    Consumes ONLY UnifiedGateway, JarvisNOCBridge, and Contract DTOs.
    """

    def __init__(
        self,
        gateway: Optional[UnifiedGateway] = None,
        stt_service: Optional[STTService] = None,
        tts_service: Optional[TTSService] = None,
        noc_bridge: Optional[JarvisNOCBridge] = None,
    ):
        if gateway is None:
            try:
                from SERVER.integration.gateway.noc_integration_gateway import NOCIntegrationGateway
                gateway = NOCIntegrationGateway()
            except Exception:
                gateway = None
        self.gateway = gateway
        self.stt_service = stt_service
        self.tts_service = tts_service

        # Core presentation components
        self.session_mgr = SessionManager()
        self.persona_reg = PersonaRegistry()
        self.prompt_mgr = PresentationPromptManager()
        self.conv_mgr = ConversationManager()
        self.avatar_mgr = AvatarStateManager()
        self.wake_word_detector = WakeWordDetector()

        # P1: Intent Router
        self.intent_router = JarvisCommandIntentRouter()

        # P2: NOC Bridge
        self.noc_bridge = noc_bridge or JarvisNOCBridge()

        # P4: HITL Feedback Loop
        self.hitl_feedback = JarvisHITLFeedback(
            notify_callback=self._hitl_notify
        )

        # P5: Startup Reporter
        self.startup_reporter = JarvisStartupReporter(noc_bridge=self.noc_bridge)

        # P6: Remote Session Manager & Browser Control
        self.remote_mgr = JarvisRemoteSessionManager(noc_bridge=self.noc_bridge)
        self.browser_control = JarvisBrowserControlBridge()

        # P9: Audit Trail
        self.audit = JarvisCommandAudit()

        # P10-P19 Bridges & Validators
        from SERVER.jarvis.cognition.llm_command_translator import LLMVoiceCommandTranslator
        from SERVER.jarvis.remediation.one_click_remediator import JarvisOneClickRemediator
        from SERVER.jarvis.telegram.field_dispatcher import TelegramFieldDispatcher
        from SERVER.jarvis.sandbox.sandbox_verifier import JarvisSandboxVerifier
        from SERVER.jarvis.proactive.predictive_forecaster import PredictiveAnomalyForecaster

        self.voice_translator = LLMVoiceCommandTranslator()
        self.nlu_bridge = JarvisNLUBridge()
        self.opening_bridge = JarvisOpeningBridge()
        self.kg_bridge = JarvisKnowledgeGraphBridge()
        self.bi_bridge = JarvisBusinessImpactBridge()
        self.catalog_validator = JarvisActionCatalogValidator()
        self.deep_diag_adapter = JarvisDeepDiagnosticsAdapter(noc_bridge=self.noc_bridge)
        self.browser_bridge = JarvisBrowserMonitorBridge(noc_bridge=self.noc_bridge)
        self.kb_learning_bridge = JarvisKnowledgeLearningBridge(noc_bridge=self.noc_bridge)

        # Enterprise AI NOC v3.0 Next-Gen Modules
        self.one_click_remediator = JarvisOneClickRemediator()
        self.field_dispatcher = TelegramFieldDispatcher(noc_bridge=self.noc_bridge)
        self.sandbox_verifier = JarvisSandboxVerifier(noc_bridge=self.noc_bridge)
        self.predictive_forecaster = PredictiveAnomalyForecaster()

        # ── SENIOR AI MODULES (Chain-of-Thought + Episodic Memory) ──────────
        self._cot_engine = None
        self._episodic_memory = None
        try:
            from SERVER.jarvis.cognition.chain_of_thought_engine import ChainOfThoughtEngine
            self._cot_engine = ChainOfThoughtEngine(noc_bridge=self.noc_bridge)
            logger.info("[JarvisRuntime] ✅ Chain-of-Thought Engine connected.")
        except Exception as _cot_err:
            logger.warning("[JarvisRuntime] CoT Engine not available: %s", _cot_err)

        try:
            from SERVER.jarvis.memory.episodic_memory import get_episodic_memory
            self._episodic_memory = get_episodic_memory()
            logger.info("[JarvisRuntime] ✅ Episodic Memory connected (%d devices known).",
                        len(self._episodic_memory._devices))
        except Exception as _mem_err:
            logger.warning("[JarvisRuntime] Episodic Memory not available: %s", _mem_err)

        # ── PHASE 2 SENIOR AI: Alert Dedup + Task Planner + Shift Handoff + Correlation ──
        self._alert_dedup = None
        self._task_planner = None
        self._shift_briefer = None
        self._event_correlator = None

        try:
            from SERVER.jarvis.proactive.alert_dedup_engine import get_alert_dedup_engine
            self._alert_dedup = get_alert_dedup_engine()
            logger.info("[JarvisRuntime] ✅ Alert Dedup Engine connected.")
        except Exception as _e:
            logger.warning("[JarvisRuntime] Alert Dedup not available: %s", _e)

        try:
            from SERVER.jarvis.planning.autonomous_task_planner import get_task_planner
            self._task_planner = get_task_planner(noc_bridge=self.noc_bridge)
            logger.info("[JarvisRuntime] ✅ Autonomous Task Planner connected.")
        except Exception as _e:
            logger.warning("[JarvisRuntime] Task Planner not available: %s", _e)

        try:
            from SERVER.jarvis.runtime.shift_handoff_briefer import get_shift_briefer
            self._shift_briefer = get_shift_briefer(noc_bridge=self.noc_bridge)
            logger.info("[JarvisRuntime] ✅ Shift Handoff Briefer connected.")
        except Exception as _e:
            logger.warning("[JarvisRuntime] Shift Briefer not available: %s", _e)

        try:
            from python_ai_core.engines.event_correlation_engine import get_correlation_engine
            self._event_correlator = get_correlation_engine()
            logger.info("[JarvisRuntime] ✅ Event Correlation Engine connected.")
        except Exception as _e:
            logger.warning("[JarvisRuntime] Event Correlator not available: %s", _e)

        # ── PHASE 3 SENIOR AI: MultiLang, XAI, Capacity, VendorDiag ─────────
        self._multilang = None
        self._xai_engine = None
        self._capacity_planner = None
        self._vendor_diag = None

        try:
            from SERVER.jarvis.cognition.multilang_normalizer import get_multilang_normalizer
            self._multilang = get_multilang_normalizer()
            logger.info("[JarvisRuntime] ✅ MultiLang Normalizer connected (ID+EN seamless).")
        except Exception as _e:
            logger.warning("[JarvisRuntime] MultiLang not available: %s", _e)

        try:
            from python_ai_core.engines.xai_engine import get_xai_engine
            self._xai_engine = get_xai_engine(episodic_memory=self._episodic_memory)
            logger.info("[JarvisRuntime] ✅ XAI Engine connected (explainable decisions).")
        except Exception as _e:
            logger.warning("[JarvisRuntime] XAI Engine not available: %s", _e)

        try:
            from python_ai_core.planning.capacity_planner import get_capacity_planner
            self._capacity_planner = get_capacity_planner()
            logger.info("[JarvisRuntime] ✅ Capacity Planner connected (self-healing forecast).")
        except Exception as _e:
            logger.warning("[JarvisRuntime] Capacity Planner not available: %s", _e)

        try:
            from python_ai_core.services.vendor_diagnostics_engine import get_vendor_diagnostics_engine
            self._vendor_diag = get_vendor_diagnostics_engine()
            logger.info("[JarvisRuntime] ✅ Vendor Diagnostics Engine connected (%d vendor profiles).",
                        len(self._vendor_diag._profiles))
        except Exception as _e:
            logger.warning("[JarvisRuntime] Vendor Diagnostics not available: %s", _e)

        logger.info("[JarvisRuntime v3.3] All modules initialized: CoT, EpisodicMemory, "
                    "AlertDedup, TaskPlanner, ShiftHandoff, EventCorrelation, "
                    "MultiLang, XAI, CapacityPlanner, VendorDiag.")

        # ── PILAR AGENTIC AI v4.0: LLM Tool Calling + Multi-Turn Memory + Proactive Reasoning ──
        # Inisialisasi lazy & graceful — tidak merusak apapun jika Gemini tidak tersedia
        self._agentic_dispatcher = None
        try:
            from SERVER.jarvis.agentic.agentic_dispatcher import AgenticDispatcher
            self._agentic_dispatcher = AgenticDispatcher(runtime_instance=self)
            if self._agentic_dispatcher._enabled:
                logger.info("[JarvisRuntime] ✅ AgenticDispatcher ACTIVE — Gemini Tool Calling + Multi-Turn Memory + Proactive Reasoning enabled.")
            else:
                logger.info("[JarvisRuntime] AgenticDispatcher loaded (Gemini key not set — fallback-only mode).")
        except Exception as _agentic_err:
            logger.warning("[JarvisRuntime] AgenticDispatcher not available: %s", _agentic_err)

    def process_voice_query(
        self, session_id: str, audio_payload: VoiceAudioPayloadDTO
    ) -> Dict[str, Any]:
        """
        Main pipeline: STT → MultiLang → IntentRouter → Dispatch → PersonaFormat → TTS → Audit.
        """
        t_start = time.time()
        self.avatar_mgr.set_state(AvatarState.LISTENING)

        # 1. STT
        t_stt_start = time.time()
        raw_text: str = ""
        if self.stt_service:
            raw_text = self.stt_service.transcribe(audio_payload) or ""
        if not raw_text:
            raw_text = audio_payload.text_caption or "status sistem"

        # 1b. MultiLang Normalization (ID+EN seamless)
        if self._multilang:
            try:
                normalized_text, detected_lang = self._multilang.normalize(raw_text)
                if detected_lang != "id" and normalized_text != raw_text:
                    logger.debug("[MultiLang] Normalized %r → %r (lang=%s)",
                                 raw_text, normalized_text, detected_lang)
                    raw_text = normalized_text
            except Exception as _ml_err:
                logger.debug("[MultiLang] Normalize error: %s", _ml_err)

        # 2. Wake Word Detection, Strip & Phonetic Auto-Correction
        t_translate_start = time.time()
        stt_ms = int((t_translate_start - t_stt_start) * 1000)


        is_wake_detected, detected_word = self.wake_word_detector.detect_in_text(raw_text)
        stripped_text = self.wake_word_detector.strip_wake_word(raw_text)

        session_context = self.conv_mgr.get_context_dict(session_id)
        voice_dto = self.voice_translator.translate(stripped_text, session_context=session_context)
        query_text = voice_dto.sanitized_transcript or stripped_text

        # 2b. Multi-Turn Anaphora & Reference Resolution V3.2
        memory_mgr = get_multi_turn_memory_manager_v31()
        resolved_query, session_mem, was_resolved, binding, clarification, inv_type = memory_mgr.resolve_query_context_v31(session_id, query_text)

        if clarification:
            logger.info(f"[PresentationRuntime V3.1] Ambiguous context or clarification requested: '{clarification}'")
            return {
                "session_id": session_id,
                "query_text": query_text,
                "intent": "clarification",
                "answer_text": clarification,
                "spoken_text": clarification,
                "audio_bytes": None,
                "audio_mime": "audio/wav",
                "action_context": StructuredActionContext(
                    detected_intent="clarification",
                    intent_confidence=0.5,
                    risk_level="LOW",
                    execution_status="CLARIFICATION_REQUIRED"
                ),
                "latency": VoiceLatencyBreakdownDTO(
                    stt_ms=stt_ms, translate_ms=0, dispatch_ms=0, tts_ms=0,
                    total_ms=int((time.time() - t_stt_start) * 1000)
                ),
                "execution_status": "CLARIFICATION_REQUIRED"
            }

        if was_resolved:
            logger.info(f"[PresentationRuntime V3.1] Resolved anaphora: '{query_text}' -> '{resolved_query}' (Binding: {binding.entity if binding else None})")
            query_text = resolved_query

        # 3. Session & Persona Resolution
        t_dispatch_start = time.time()
        translate_ms = int((t_dispatch_start - t_translate_start) * 1000)

        session = self.session_mgr.get_session(session_id)
        is_new_session = session is None
        if not session:
            session = self.session_mgr.create_session(session_id, user_id="voice_user")
        persona = self.persona_reg.get(session.active_persona_id or "noc_engineer")

        # 4. Add User Turn
        self.conv_mgr.add_turn(session_id, "user", query_text)
        self.avatar_mgr.set_state(AvatarState.THINKING)

        # 5. P1: Intent Classification
        intent_result = self.intent_router.classify(query_text)
        intent = intent_result.intent

        # 6. Dispatch Berdasarkan Intent
        action_context = StructuredActionContext(
            detected_intent=intent.value if hasattr(intent, "value") else str(intent),
            intent_confidence=intent_result.confidence if hasattr(intent_result, "confidence") else 0.95,
            risk_level="LOW",
        )

        answer_text, action_context = self._dispatch_by_intent(
            intent=intent,
            intent_result=intent_result,
            query_text=query_text,
            session_id=session_id,
            session=session,
            persona=persona,
            action_context=action_context,
        )

        # 6b. Record Multi-Turn Memory Context V3.1 with Provenance Binding
        memory_mgr.record_turn(
            session_id=session_id,
            speaker="user",
            raw_query=stripped_text,
            resolved_query=query_text,
            jarvis_answer=answer_text,
            target_device=getattr(intent_result, "target_device", None),
            target_incident=getattr(intent_result, "target_incident", None),
            target_site=getattr(intent_result, "target_site", None),
            intent=str(intent),
            binding=binding
        )

        # 6c. ── CHAIN-OF-THOUGHT ENHANCEMENT (Senior AI upgrade) ────────────
        # Enhance respons dengan reasoning, confidence scoring, dan pola — non-blocking
        target_dev = getattr(intent_result, "target_device", "") or ""
        if self._cot_engine and answer_text:
            try:
                cot_result = self._cot_engine.enhance_response(
                    raw_response=answer_text,
                    query=query_text,
                    live_data={},
                )
                answer_text = cot_result.final_response
            except Exception as _cot_e:
                logger.debug("[JarvisRuntime] CoT enhance error (non-fatal): %s", _cot_e)

        # 6d. ── EPISODIC MEMORY UPDATE (Cross-session awareness) ─────────────
        if self._episodic_memory and target_dev and action_context.action_taken:
            try:
                issue_type = query_text[:60]
                self._episodic_memory.record_device_incident(
                    device_id=target_dev,
                    action=action_context.action_taken,
                    issue_type=issue_type,
                )
                # Inject memory context ke respons jika device punya history
                mem_ctx = self._episodic_memory.get_device_context(target_dev)
                if mem_ctx and mem_ctx not in answer_text:
                    answer_text = answer_text.rstrip() + f"\n\n🧠 {mem_ctx}"
            except Exception as _mem_e:
                logger.debug("[JarvisRuntime] Episodic memory update error: %s", _mem_e)

        t_tts_start = time.time()
        dispatch_ms = int((t_tts_start - t_dispatch_start) * 1000)

        # 7. Persona Speech Formatting
        session_turn_count = len(getattr(self.conv_mgr, "conversations", {}).get(session_id, []))
        is_first_turn = is_new_session or session_turn_count <= 1

        # BUG-1c fix: speak the actual answer. The persona acknowledgment template
        # (e.g. "Siap, memproses ... {target}...") is a pre-action ack and was
        # replacing the answer entirely, with an unfilled {target} placeholder.
        formatted_speech = answer_text

        # 8. P3: Response DTO
        self.conv_mgr.add_turn(session_id, "assistant", formatted_speech)

        # 9. TTS Synthesis
        self.avatar_mgr.set_state(AvatarState.SPEAKING)
        audio_out = None
        if self.tts_service:
            audio_out = self.tts_service.synthesize(
                formatted_speech, persona_id=session.active_persona_id or "noc_engineer"
            )

        t_end = time.time()
        tts_ms = int((t_end - t_tts_start) * 1000)
        total_ms = int((t_end - t_start) * 1000)
        self.avatar_mgr.set_state(AvatarState.IDLE)

        # 10. P9: Record Command Audit
        self.audit.record(
            session_id=session_id,
            operator_id=session.user_id if session else "voice_user",
            query_text=query_text,
            detected_intent=intent.value if hasattr(intent, "value") else str(intent),
            intent_confidence=intent_result.confidence if hasattr(intent_result, "confidence") else 0.95,
            query_text_raw=raw_text,
            target_device=getattr(intent_result, "target_device", None),
            risk_level=action_context.risk_level,
            execution_status=action_context.execution_status,
            action_taken=action_context.action_taken,
            response_text=formatted_speech,
            latency_ms=total_ms,
        )

        latency = VoiceLatencyBreakdownDTO(
            stt_ms=stt_ms,
            translate_ms=translate_ms,
            dispatch_ms=dispatch_ms,
            tts_ms=tts_ms,
            total_ms=total_ms,
        )

        return {
            "session_id": session_id,
            "query_text": query_text,
            "intent": intent.value if hasattr(intent, "value") else str(intent),
            "intent_confidence": intent_result.confidence if hasattr(intent_result, "confidence") else 0.95,
            "answer_text": answer_text,
            "spoken_text": formatted_speech,
            "audio_output": audio_out,
            "audio_bytes": getattr(audio_out, "audio_bytes", None) if audio_out else None,
            "audio_mime": (f"audio/{audio_out.audio_format}" if audio_out and audio_out.audio_format else "audio/wav"),
            "action_context": action_context,
            "latency": latency,
            "execution_status": action_context.execution_status,
        }

    def _dispatch_by_intent(
        self, intent, intent_result, query_text, session_id, session, persona, action_context
    ):
        """
        Route perintah ke handler yang sesuai berdasarkan intent.

        v4.0 Agentic AI: Mencoba AgenticDispatcher (Gemini Tool Calling) dulu.
        Jika Gemini tidak tersedia atau gagal → fallback ke existing IntentRouter lama.
        Semua handler lama tetap utuh dan menjadi "tool backend" yang dipanggil dispatcher.
        """
        # ── PILAR 1+2+3: Agentic Dispatch (Gemini Tool Calling + Multi-Turn Memory + Proactive) ──
        if self._agentic_dispatcher is not None:
            try:
                # Ambil conversation history untuk Deep Multi-Turn Memory (Pilar 2)
                conv_history = self.conv_mgr.get_messages_for_llm(session_id, limit=10)
                ctx_dict = self.conv_mgr.get_context_dict(session_id)

                agentic_answer, agentic_ctx = self._agentic_dispatcher.dispatch(
                    query_text=query_text,
                    session_id=session_id,
                    action_context=action_context,
                    conversation_history=conv_history,
                    context_dict=ctx_dict,
                )

                # Jika AgenticDispatcher berhasil (returned non-None answer)
                if agentic_answer is not None:
                    return agentic_answer, agentic_ctx

                # Jika dispatch() return (None, ctx) → sinyal untuk gunakan legacy router
                logger.debug("[JarvisRuntime] AgenticDispatcher signaled legacy fallback.")
            except Exception as _agentic_e:
                logger.warning(
                    "[JarvisRuntime] AgenticDispatcher exception (%s) — using legacy IntentRouter.",
                    _agentic_e
                )

        # ── FALLBACK: Legacy IntentRouter (existing regex/rules — ZERO DELETION) ──
        if intent == JarvisIntent.QUERY:
            return self._handle_query(query_text, intent_result, persona, action_context, session_id=session_id)

        elif intent == JarvisIntent.REMEDIATE:
            return self._handle_remediate(
                query_text, intent_result, session_id, session, action_context
            )

        elif intent == JarvisIntent.HITL:
            return self._handle_hitl(query_text, intent_result, session, action_context)

        elif intent == JarvisIntent.REMOTE:
            return self._handle_remote(query_text, intent_result, session, action_context)

        elif intent == JarvisIntent.CHAT:
            return self._handle_chat(query_text, intent_result, action_context)

        elif intent == JarvisIntent.ISSUE:
            return self._handle_issue(query_text, intent_result, action_context)

        else:
            return self._handle_gateway_fallback(
                query_text, session_id, session, action_context
            )
