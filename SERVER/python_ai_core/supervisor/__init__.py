"""
supervisor/__init__.py
----------------------
Public API untuk supervisor module.
"""
from .core import set_runtime_state, parse_rfc3339_or_unix, get_active_recovery_mode, get_active_consensus_pattern, NATS_URL
from .nats_bridge import NATSBridge
from .dispatcher import safe_dispatch, safe_dispatch_sync, safe_dispatch_with_cb, EngineCircuitBreaker

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
]
