"""
SERVER.jarvis Domain Package — v2.2 (Full Architecture & LLM Voice Command Integration)
==========================================================================================
Presentation Layer: Voice STT/TTS, Personas, Session Manager, Avatar Stream, Runtime, LLM Translator.
STRICTLY COMPLIANT WITH ADR-005: Zero direct DB/Repository/Knowledge/Memory/Tool imports.
All requests pass strictly through Integration Gateway, NOC Bridge, or Cognition Bridges.

Complete P1-P19 Feature Matrix:
  P1: JarvisCommandIntentRouter      — 6-kategori intent (command/)
  P2: JarvisNOCBridge                — Bridge ke dashboard API (noc/)
  P3: StructuredActionContext        — Structured response contract (contracts/schemas.py)
  P4: JarvisHITLFeedback            — HITL feedback loop (hitl/)
  P5: JarvisStartupReporter         — Auto startup report (runtime/startup_reporter.py)
  P6: JarvisRemoteSessionManager     — Remote session management (remote/)
  P7: PersonaRegistry + Acks        — Command acknowledgment templates (personas/)
  P8: NOCKeywordsID                 — 177 Bahasa Indonesia keywords (command/)
  P9: JarvisCommandAudit            — Command audit trail (audit/)
  P10: JarvisTelegramGateway         — Full Telegram bot integration (integration/telegram/)
  P11: JarvisNLUBridge               — NLUEngine bridge (cognition/)
  P12: JarvisOpeningBridge           — JarvisOpeningEngine bridge (cognition/)
  P13: JarvisKnowledgeLearningBridge — Auto-SOP builder bridge (knowledge/)
  P14: JarvisKnowledgeGraphBridge    — KnowledgeGraph Causal Graph & Blast Radius (cognition/)
  P15: JarvisActionCatalogValidator  — PreApprovedActionCatalog validator (planning/)
  P16: JarvisBusinessImpactBridge    — Asset Criticality & SLA (cognition/)
  P18: JarvisBrowserMonitorBridge    — Browser extension monitoring (diagnostics/)
  P19: JarvisDeepDiagnosticsAdapter  — 10-section deep diagnostics (diagnostics/)
  P20: LLMVoiceCommandTranslator     — LLM Voice-to-Intent structured JSON translator (cognition/)
"""
# ── Core Presentation ─────────────────────────────────────────────────────────
from SERVER.jarvis.interfaces.presentation_dtos import (
    ConversationContextDTO, DecisionTraceSummaryDTO, VoiceAudioPayloadDTO
)
from SERVER.jarvis.sessions.session_manager import SessionManager
from SERVER.jarvis.personas.persona_registry import PersonaRegistry, PersonaConfig
from SERVER.jarvis.prompt.prompt_template_manager import PresentationPromptManager
from SERVER.jarvis.conversation.conversation_manager import ConversationManager, ConversationTurn
from SERVER.jarvis.conversation.opening_engine import ConversationOpeningEngine
from SERVER.jarvis.avatar.avatar_state_manager import AvatarStateManager, AvatarState
from SERVER.jarvis.voice.stt_service import STTService
from SERVER.jarvis.voice.tts_service import TTSService
from SERVER.jarvis.voice.wake_word_detector import WakeWordDetector
from SERVER.jarvis.runtime.jarvis_presentation_runtime import JarvisPresentationRuntime

# ── P1: Intent Router ─────────────────────────────────────────────────────────
from SERVER.jarvis.command.intent_router import JarvisCommandIntentRouter, JarvisIntent, IntentResult

# ── P2: NOC Bridge ────────────────────────────────────────────────────────────
from SERVER.jarvis.noc.noc_bridge import JarvisNOCBridge, NOCBridgeResponse

# ── P4: HITL Feedback ─────────────────────────────────────────────────────────
from SERVER.jarvis.hitl.hitl_feedback import JarvisHITLFeedback, HITLQueueItem, HITLDecision

# ── P5: Startup Reporter ──────────────────────────────────────────────────────
from SERVER.jarvis.runtime.startup_reporter import JarvisStartupReporter

# ── P6: Remote Session Manager & Browser Control ──────────────────────────────
from SERVER.jarvis.remote.remote_session_manager import JarvisRemoteSessionManager, RemoteSession
from SERVER.jarvis.remote.browser_control_bridge import JarvisBrowserControlBridge

# ── P8: Bahasa Indonesia Keywords ────────────────────────────────────────────
from SERVER.jarvis.command.noc_keywords_id import NOCKeywordsID

# ── P9: Command Audit Trail ───────────────────────────────────────────────────
from SERVER.jarvis.audit.command_audit import JarvisCommandAudit, AuditRecord

# ── P10: Telegram Gateway ─────────────────────────────────────────────────────
from SERVER.integration.telegram.telegram_bot_adapter import JarvisTelegramGateway, TelegramBotAdapter

# ── P11 & P12 & P20: Cognition Bridges & LLM Translator ────────────────────────
from SERVER.jarvis.cognition.nlu_bridge import JarvisNLUBridge, JarvisOpeningBridge
from SERVER.jarvis.cognition.phonetic_corrector import JarvisPhoneticCorrector
from SERVER.jarvis.cognition.llm_command_translator import LLMVoiceCommandTranslator, VoiceActionDTO

# ── P13: Knowledge Learning ───────────────────────────────────────────────────
from SERVER.jarvis.knowledge.knowledge_learning_bridge import JarvisKnowledgeLearningBridge

# ── P14 & P16: Knowledge Graph & Business Impact ──────────────────────────────
from SERVER.jarvis.cognition.knowledge_graph_bridge import (
    JarvisKnowledgeGraphBridge, JarvisBusinessImpactBridge
)

# ── P15: Action Catalog Validator ─────────────────────────────────────────────
from SERVER.jarvis.planning.action_catalog_validator import JarvisActionCatalogValidator

# ── P18 & P19: Diagnostics & Browser ─────────────────────────────────────────
from SERVER.jarvis.diagnostics.deep_diagnostics_adapter import (
    JarvisDeepDiagnosticsAdapter, JarvisBrowserMonitorBridge
)

__all__ = [
    # Core
    "ConversationContextDTO", "DecisionTraceSummaryDTO", "VoiceAudioPayloadDTO",
    "SessionManager", "PersonaRegistry", "PersonaConfig",
    "PresentationPromptManager", "ConversationManager", "ConversationTurn",
    "ConversationOpeningEngine", "AvatarStateManager", "AvatarState",
    "STTService", "TTSService", "WakeWordDetector", "JarvisPresentationRuntime",
    # P1
    "JarvisCommandIntentRouter", "JarvisIntent", "IntentResult",
    # P2
    "JarvisNOCBridge", "NOCBridgeResponse",
    # P4
    "JarvisHITLFeedback", "HITLQueueItem", "HITLDecision",
    # P5
    "JarvisStartupReporter",
    # P6
    "JarvisRemoteSessionManager", "RemoteSession", "JarvisBrowserControlBridge",
    # P8
    "NOCKeywordsID",
    # P9
    "JarvisCommandAudit", "AuditRecord",
    # P10
    "JarvisTelegramGateway", "TelegramBotAdapter",
    # P11, P12, P20
    "JarvisNLUBridge", "JarvisOpeningBridge", "JarvisPhoneticCorrector",
    "LLMVoiceCommandTranslator", "VoiceActionDTO",
    # P13
    "JarvisKnowledgeLearningBridge",
    # P14 & P16
    "JarvisKnowledgeGraphBridge", "JarvisBusinessImpactBridge",
    # P15
    "JarvisActionCatalogValidator",
    # P18 & P19
    "JarvisDeepDiagnosticsAdapter", "JarvisBrowserMonitorBridge",
]
