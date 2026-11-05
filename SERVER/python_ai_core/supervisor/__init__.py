"""
supervisor/__init__.py
----------------------
Public API untuk supervisor module.
"""
from .core import set_runtime_state, parse_rfc3339_or_unix, get_active_recovery_mode, get_active_consensus_pattern, NATS_URL
from .nats_bridge import NATSBridge
from .dispatcher import safe_dispatch, safe_dispatch_sync, safe_dispatch_with_cb, EngineCircuitBreaker
from .pipeline_logger import log_ai_pipeline, log_event_sourced
from .handlers.incident_handler import execute_validated_llm, message_handler, learning_handler, reanalyze_handler, ai_retry_handler
from .handlers.approval_handler import handle_escalate_request, handle_approval_decision, run_background_verification, verification_handler, chat_compaction_handler, apply_incident_transition
from .handlers.background_loops import autonomous_data_retention, heartbeat_loop, trust_evaluator_loop, sync_human_rejections_loop, world_model_loop_async, predictive_loop_async

__all__ = [
    "set_runtime_state",
    "parse_rfc3339_or_unix",
    "get_active_recovery_mode",
    "get_active_consensus_pattern",
    "NATS_URL",
    "NATSBridge",
    "safe_dispatch",
    "safe_dispatch_sync",
    "safe_dispatch_with_cb",
    "EngineCircuitBreaker",
    "log_ai_pipeline",
    "log_event_sourced",
    "execute_validated_llm",
    "message_handler",
    "learning_handler",
    "reanalyze_handler",
    "ai_retry_handler",
    "handle_escalate_request",
    "handle_approval_decision",
    "run_background_verification",
    "verification_handler",
    "chat_compaction_handler",
    "apply_incident_transition",
    "autonomous_data_retention",
    "heartbeat_loop",
    "trust_evaluator_loop",
    "sync_human_rejections_loop",
    "world_model_loop_async",
    "predictive_loop_async",
]
